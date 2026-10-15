"""Task-driven retained-evidence handoff to PDS; no acquisition or model calls."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys

from amazon_product_intelligence.pds_market_readback import read_verified
from amazon_product_intelligence.yps_competitive_difference import ref, save

SP_STATUS = 'BUSINESS VALUE HUMAN REVIEW PENDING'
POLICY = dict(new_paid_calls=False, scheduled_collection=False,
              execution_authorized=False, sp043b_status=SP_STATUS)
FORMATS = {
    'competitive_difference': ('yps-competitive-difference/v1',
                              'PDS_YPS_COMPETITIVE_REVIEW', 'market_result_ref'),
    'offer_comparison': ('08-market-offer-evidence/v1',
                         'PDS_08_MARKET_REVIEW', 'market_ref'),
    'native_offer_review': ('amazon-buyer-context-probe/v1',
                            'YPS_MARKET_OFFER_PROJECT_REVIEW', 'market_result_ref'),
}
TASK_FIELDS = {'schema', 'task_id', 'research_type', 'identity', 'market_ref',
               'receipt_ref', 'pds_context_ref', 'policy'}


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode('utf8')).hexdigest()


def load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON')))


def original_time(receipt):
    return receipt.get('generated_at_utc') or receipt['finished_at_utc']


def verify_record(value):
    if value.get('record_ref') != digest({k: v for k, v in value.items() if k != 'record_ref'}):
        raise ValueError('Record content changed')
    return value


def verified(reference):
    if not isinstance(reference, dict) or set(reference) != {'path', 'sha256'}:
        raise ValueError('Invalid file reference')
    path = Path(reference['path'])
    if not path.is_absolute() or not re.fullmatch(r'[0-9a-f]{64}', reference['sha256']):
        raise ValueError('Absolute reference and SHA256 required')
    read_verified(path, reference['sha256'])
    return load(path)


def validate(task):
    if (set(task) != TASK_FIELDS or task['schema'] != 'market-pds-task/v1'
            or not isinstance(task['task_id'], str)
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', task['task_id'])
            or task['policy'] != POLICY or task['research_type'] not in FORMATS
            or any(type(task['policy'][k]) is not bool for k in POLICY if k != 'sp043b_status')):
        raise ValueError('Unsupported task or policy')
    schema, kind, market_key = FORMATS[task['research_type']]
    market = verified(task['market_ref'])
    receipt = verified(task['receipt_ref'])
    context = verified(task['pds_context_ref'])
    native = task['research_type'] == 'native_offer_review'
    identity = context['identity']
    if not isinstance(identity, dict) or not identity.get('asin') or not identity.get('sku'):
        raise ValueError('SKU and ASIN identity required')
    identities_ok = (identity == task['identity'] and
                     (market['scope']['asins'][0] == identity['asin']
                      and market['observations'][0]['asin'] == identity['asin'] if native else
                      all(v['identity'] == identity for v in (market, receipt))))
    if (market['schema'] != schema or receipt['kind'] != kind
            or receipt[market_key] != task['market_ref']
            or receipt['evidence_ref'] != task['pds_context_ref']
            or context[market_key] != task['market_ref']
            or not identities_ok):
        raise ValueError('Task identity, scope or evidence differs from retained PDS input')
    origin = 'PROJECT_PROVIDER_ANALYSIS' if native else 'PROJECT_PDS_LLM'
    if (receipt['status'] != 'ANALYSIS_COMPLETED' or receipt['origin'] != origin
            or receipt['provider_calls'] != 1 or receipt['transport']['phase'] != 'COMPLETE'
            or receipt['transport']['http_status'] != 200):
        raise ValueError('A successful existing PDS analysis is required; no new calls allowed')
    for group in (market.get('source_refs', []), context['source_refs']):
        for source in group:
            path = Path(source['path'])
            if (not path.is_absolute() or path.absolute() != path.resolve()
                    or str(path).startswith(('\\\\', '//'))
                    or sha256(path.read_bytes()).hexdigest() != source['sha256']):
                raise ValueError('Referenced evidence changed: ' + str(path))
    return market, receipt, context


def make_task(task_id, research_type, packet, receipt):
    review = load(receipt)
    context = verified(review['evidence_ref'])
    task = dict(schema='market-pds-task/v1', task_id=task_id, research_type=research_type,
                identity=context['identity'], market_ref=ref(packet), receipt_ref=ref(receipt),
                pds_context_ref=review['evidence_ref'], policy=POLICY)
    validate(task)
    return task


def invoke_pds(pds_root, python, request, output):
    bridge = Path(pds_root).resolve() / 'tools/run_market_research_handoff.py'
    if not bridge.is_file():
        raise ValueError('PDS retained-evidence consumer is unavailable')
    completed = subprocess.run([str(python), '-B', '-X', 'utf8', str(bridge),
                                '--request', str(request), '--output', str(output)],
                               cwd=str(Path(pds_root).resolve()), capture_output=True,
                               encoding='utf8', timeout=60, check=False)
    if completed.returncode != 0 or not Path(output).is_file():
        raise ValueError('PDS rejected the handoff; no automatic model fallback')


def check_response(task, fingerprint, response, receipt):
    verify_record(response)
    if (response['schema'] != 'pds-market-handoff-response/v1'
            or response['status'] != 'EXISTING_ANALYSIS_CONSUMED'
            or response['task_fingerprint'] != fingerprint
            or response['task_id'] != task['task_id']
            or response['policy'] != POLICY or response['new_provider_calls'] != 0
            or response['evidence_refreshed'] is not False
            or response['business_value_accepted'] is not False
            or response['proposal'] != receipt['proposal']
            or response['original_analysis_at_utc'] != original_time(receipt)
            or any(response[k] != task[k] for k in ('research_type', 'identity',
                   'market_ref', 'receipt_ref', 'pds_context_ref'))):
        raise ValueError('PDS response does not match this task and original analysis')


def run(task_path, output_root, pds_root, python=sys.executable):
    task = load(task_path)
    try:
        market, receipt, context = validate(task)
    except FileNotFoundError:
        return dict(status='INSUFFICIENT_EVIDENCE', reason='REQUIRED_LOCAL_FILE_MISSING',
                    new_provider_calls=0, policy=POLICY)
    fingerprint = digest(task)
    methods = [ref(__file__), ref(Path(pds_root).resolve() / 'tools/run_market_research_handoff.py')]
    directory = Path(output_root).resolve() / (task['task_id'] + '-' + fingerprint[:16])
    result_path = directory / 'result.json'
    if result_path.is_file():
        result = verify_record(load(result_path))
        if result['task_fingerprint'] != fingerprint or result['status'] != 'COMPLETED':
            raise ValueError('Existing workflow result differs')
        if result['methods'] != methods:
            return dict(status='NEEDS_REVIEW', reason='WORKFLOW_METHOD_CHANGED',
                        task_id=task['task_id'], new_provider_calls=0, policy=POLICY)
        for artifact in result['artifacts']:
            path = Path(artifact['path'])
            if not path.is_relative_to(directory) or sha256(path.read_bytes()).hexdigest() != artifact['sha256']:
                raise ValueError('Workflow artifact changed')
        response = verified(result['response_ref'])
        check_response(task, fingerprint, response, receipt)
        return {**result, 'invocation_status': 'REUSED_COMPLETED_WORKFLOW'}
    if directory.exists():
        # A partial run never retries itself, even if a consumer failed.
        return dict(status='NEEDS_REVIEW', reason='INCOMPLETE_RUN_REQUIRES_REVIEW',
                    task_id=task['task_id'], task_fingerprint=fingerprint,
                    new_provider_calls=0, policy=POLICY)
    directory.mkdir(parents=True)
    stage = 'PREPARE_HANDOFF'
    try:
        save(directory / 'task.json', task)
        # Preserve the exact packet bytes; receipt bindings still refer to the
        # original immutable packet, not a newly generated market observation.
        with (directory / 'market_evidence.json').open('xb') as stream:
            stream.write(Path(task['market_ref']['path']).read_bytes())
        request = {**task, 'schema': 'market-pds-handoff/v1', 'task_fingerprint': fingerprint}
        request_path = directory / 'handoff.json'
        response_path = directory / 'pds_response.json'
        save(request_path, request)
        stage = 'PDS_CONSUME'
        invoke_pds(pds_root, python, request_path, response_path)
        # Recheck sources after the other process, before publishing success.
        _, receipt, _ = validate(task)
        response = load(response_path)
        stage = 'READ_BACK'
        check_response(task, fingerprint, response, receipt)
        readback = dict(schema='market-pds-workflow-readback/v1',
                        status='PDS_ANALYSIS_READ_BACK', task_id=task['task_id'],
                        task_fingerprint=fingerprint, identity=task['identity'],
                        response_ref=ref(response_path), original_receipt_ref=task['receipt_ref'],
                        actual_pds_analysis=response['proposal'],
                        original_analysis_at_utc=response['original_analysis_at_utc'],
                        analytical_consumption_confirmed=True, business_value_accepted=False,
                        evidence_refreshed=False, non_executable=True, sp043b_status=SP_STATUS)
        save(directory / 'readback.json', readback)
        report = ('# 市场研究与 PDS 自动交接结果\n\n'
                  + '任务：' + task['task_id'] + '\n\n'
                  + '状态：已完成交接与回读，复用历史 PDS 分析。\n\n'
                  + '原分析时间（UTC）：' + original_time(receipt) + '\n\n'
                  + 'PDS 原结论：' + (receipt['proposal']['recommendation']['reason']
                     if isinstance(receipt['proposal']['recommendation'], dict)
                     else receipt['proposal']['recommendation']) + '\n\n'
                  + '本次未刷新市场证据、未生成新的经营判断；付费调用 0，未启用定时采集。\n\n'
                  + '业务价值未自动验收。SP-043B 继续待验收。\n')
        (directory / 'REPORT.md').write_text(report, encoding='utf8')
        result = dict(schema='market-pds-workflow-result/v1', status='COMPLETED',
                      task_id=task['task_id'], task_fingerprint=fingerprint,
                      completed_at_utc=datetime.now(timezone.utc).isoformat(),
                      analysis_mode='REUSE_EXISTING_PROJECT_PDS_ANALYSIS',
                      methods=methods,
                      response_ref=ref(response_path), new_provider_calls=0,
                      evidence_refreshed=False, business_value_accepted=False, policy=POLICY,
                      artifacts=[ref(directory / name) for name in ('task.json', 'market_evidence.json',
                                 'handoff.json', 'pds_response.json', 'readback.json', 'REPORT.md')])
        result['record_ref'] = digest(result)
        save(result_path, result)
        return {**result, 'invocation_status': 'WORKFLOW_COMPLETED'}
    except (ValueError, KeyError, TypeError, OSError, subprocess.TimeoutExpired) as error:
        failure = dict(status='FAILED', failed_stage=stage, failure_type=type(error).__name__,
                       task_id=task['task_id'], task_fingerprint=fingerprint,
                       new_provider_calls=0, policy=POLICY)
        save(directory / 'failure.json', failure)
        return failure


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init', help='bind a task to a retained packet and successful PDS receipt')
    init.add_argument('--task-id', required=True)
    init.add_argument('--research-type', choices=tuple(FORMATS), required=True)
    init.add_argument('--packet', type=Path, required=True)
    init.add_argument('--receipt', type=Path, required=True)
    init.add_argument('--task-file', type=Path, required=True)
    execute = sub.add_parser('run', help='automatically hand off and read back; never call a model')
    execute.add_argument('--task-file', type=Path, required=True)
    execute.add_argument('--output-root', type=Path, required=True)
    execute.add_argument('--pds-root', type=Path, required=True)
    execute.add_argument('--pds-python', type=Path, default=Path(sys.executable))
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            task = make_task(args.task_id, args.research_type, args.packet, args.receipt)
            save(args.task_file, task)
            result = dict(status='TASK_PREPARED', task_id=args.task_id)
        else:
            result = run(args.task_file, args.output_root, args.pds_root, args.pds_python)
    except (ValueError, KeyError, TypeError, OSError) as error:
        result = dict(status='REJECTED', reason=str(error), failure_type=type(error).__name__,
                      new_provider_calls=0)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0 if result['status'] in ('TASK_PREPARED', 'COMPLETED') else 1


if __name__ == '__main__':
    raise SystemExit(main())
