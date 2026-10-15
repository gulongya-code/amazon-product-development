"""Native research production/completion and automatic PDS return. No acquisition.

The market producer reuses the existing PDS-configured model transport through a
CLI boundary. It never imports PDS business modules or creates a paid client.
Default production prepares a model job and remains pending. Offline dependency
injection stays SYNTHETIC_TEST at every boundary.
"""
from pathlib import Path
from datetime import date
from datetime import datetime
from zoneinfo import ZoneInfo
from hashlib import sha256
import json
import subprocess
import sys

from amazon_product_intelligence.market_pds_workflow import (
    load, verified, verify_record, digest, POLICY,
)
from amazon_product_intelligence.market_research_intake import receive
from amazon_product_intelligence.yps_competitive_difference import ref, save

ROOT = Path(__file__).resolve().parents[2]
MODEL_WORKER_TIMEOUT_SECONDS = 660  # Existing Provider read timeout 600s + bounded final validation/write time.


class CompletionFailure(ValueError):
    """Failure with invocation counts, without secret-bearing diagnostics."""
    def __init__(self, failure_type, new_provider_calls):
        super().__init__(failure_type)
        self.new_provider_calls = new_provider_calls


def counted(function, counter, *args, **kwargs):
    try:
        return function(*args, cost_counter=counter, **kwargs)
    except (ValueError, KeyError, TypeError, OSError) as error:
        inherited = getattr(error, 'new_provider_calls', 0)
        total = None if inherited is None else sum(counter) + inherited
        raise CompletionFailure(type(error).__name__, total) from None


def require(value, message):
    if not value:
        raise ValueError(message)


def sealed(value):
    return {**value, 'record_ref': digest(value)}


def write(path, value):
    path = Path(path)
    if path.exists():
        require(load(path) == value, 'Existing completion cannot be overwritten')
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        save(path, value)


def record(reference):
    return verify_record(verified(reference))


def check_refs(references):
    # readback.verified is a JSON reader; method/HTML files need byte hashes only.
    # Reuse the project's raw-file ref primitive, not another digest algorithm.
    for reference in references:
        path = Path(reference['path'])
        require(set(reference) == {'path', 'sha256'} and path.is_absolute()
            and path.absolute() == path.resolve() and not str(path).startswith(('\\\\', '//'))
            and ref(path) == reference, 'Source/method bytes changed or redirected')


def check_statements(answer, allowed_refs):
    for name in ('supporting', 'opposing', 'unknown'):
        item = answer[name]
        require(type(item) is dict and set(item) == {'claim', 'evidence_refs'}
            and type(item['claim']) is str and 0 < len(item['claim']) <= 2000
            and type(item['evidence_refs']) is list and item['evidence_refs']
            and len(item['evidence_refs']) == len(set(item['evidence_refs']))
            and set(item['evidence_refs']) <= allowed_refs, 'Bound balanced evidence statement differs')


def check_research_answer(answer, task, evidence):
    require(type(answer) is dict and set(answer) == {'input_ref', 'identity', 'task_id', 'question',
        'expected_answer', 'window', 'findings', 'supporting', 'opposing', 'unknown', 'limitations'}
        and answer['input_ref'] == evidence['record_ref'] and answer['identity'] == task['identity']
        and answer['task_id'] == task['task_id'] and answer['question'] == task['question']
        and answer['expected_answer'] == task['expected_answer'] and answer['window'] == evidence['window'],
        'Research complete answer contract/binding differs')
    require(type(answer['findings']) is str and 0 < len(answer['findings']) <= 4000
        and type(answer['limitations']) is list and answer['limitations']
        and all(type(x) is str and x for x in answer['limitations']), 'Research findings/limits missing')
    check_statements(answer, {'market'})


def checked_binding(binding_path, allow_synthetic):
    binding = verify_record(load(binding_path))
    require(binding['schema'] == 'pds-native-market-return-binding/v1' and binding['policy'] == POLICY,
            'Native return binding/version differs')
    require(not binding['synthetic'] or allow_synthetic, 'Synthetic task refused')
    flow = record(binding['flow_ref'])
    require(flow['schema'] == 'pds-native-market-flow/v1' and flow['pds_root'] == binding['pds_root']
        and flow['market_root'] == str(ROOT) and flow['offline_dependency_ref'] == binding['offline_dependency_ref'],
        'Return flow/dependency/root differs')
    task = record(binding['task_ref'])
    require(task['identity'] == binding['identity'], 'Binding task identity differs')
    intake = receive(binding['task_ref']['path'], binding['intake_ref']['path'], allow_synthetic=allow_synthetic)
    require(ref(binding['intake_ref']['path']) == binding['intake_ref'], 'Pending intake changed')
    require(intake['task_ref'] == binding['task_ref'], 'Intake belongs to another task')
    source = record(flow['source_ref'])
    problem = record(task['problem_ref'])
    require((problem.get('source_ref') == flow['source_ref'] or task['problem_ref'] == source['control_ref'])
        and source['status'] == 'ELIGIBLE'
        and source['identity'] == task['identity'] and problem['business_question'] == task['question'],
        'Original native operating problem differs')
    for reference in flow['methods'] + source['source_refs']:
        check_refs([reference])
    return binding, flow, source, task


def check_evidence(path, binding, source, task, allow_synthetic):
    evidence = verify_record(load(path))
    require(evidence['schema'] == 'market-native-research-evidence/v1'
        and evidence['task_ref'] == binding['task_ref'] and evidence['identity'] == task['identity']
        and evidence['question'] == task['question'] and evidence['expected_answer'] == task['expected_answer']
        and evidence['window'] == source['market_window'] and evidence['source_refs'] and evidence['methods'],
        'Research evidence task/identity/question/window/source differs')
    require(evidence['origin'] in ('REAL_PROJECT_EVIDENCE', 'SYNTHETIC_TEST')
        and (evidence['origin'] != 'SYNTHETIC_TEST' or allow_synthetic), 'Research source nature unknown or synthetic refused')
    require(not binding['synthetic'] or evidence['origin'] == 'SYNTHETIC_TEST', 'Synthetic research task promoted to real')
    require(evidence.get('qualification') == 'SOURCE_BOUND_FOR_THIS_RESEARCH'
        and evidence.get('data_date') == evidence['window']['end_date']
        and evidence.get('valid_through') is not None and evidence['data_date'] <= evidence['valid_through'],
        'Research dates/qualification unknown')
    for value in [evidence['data_date'], evidence['valid_through'], *[evidence['window'][k]
            for k in ('start_date', 'end_date')]]:
        require(date.fromisoformat(value).isoformat() == value, 'Research dates invalid')
    require(evidence.get('non_executable') is True and isinstance(evidence.get('facts'), dict)
        and evidence['facts'] and isinstance(evidence.get('limitations'), list), 'Research content or non-execution missing')
    for reference in evidence['source_refs'] + evidence['methods']:
        check_refs([reference])
    return evidence


def invocation(binding, flow, arguments, *, allow_synthetic, authorization_path=None, runner=None,
        inject_offline_dependency=True, cost_counter=None):
    """Reuse the established separate-process handoff pattern, without shell/retry."""
    root = Path(binding['pds_root']).resolve()
    script = root/'tools/run_native_market_flow.py'
    require(ref(script) in flow['methods'], 'PDS consumer script not bound to the original flow')
    command = [sys.executable, '-B', '-X', 'utf8', str(script), *map(str, arguments)]
    if allow_synthetic:
        command.append('--allow-synthetic')
    if binding['offline_dependency_ref'] and inject_offline_dependency:
        require(allow_synthetic, 'Offline dependency refused')
        dependency = binding['offline_dependency_ref']
        check_refs([dependency])
        command += ['--offline-dependency', dependency['path']]
    if authorization_path:
        command += ['--authorization', str(Path(authorization_path).resolve())]
    try:
        result = (runner or subprocess.run)(command, cwd=str(root), capture_output=True,
            text=True, encoding='utf8', timeout=MODEL_WORKER_TIMEOUT_SECONDS, check=False)
    except subprocess.TimeoutExpired:
        raise CompletionFailure('WORKER_TIMEOUT_COUNT_UNKNOWN', None) from None
    except OSError:
        raise CompletionFailure('WORKER_CONNECTION_LOST_COUNT_UNKNOWN', None) from None
    # Never print subprocess diagnostics: a live producer may contain secrets.
    # Stdout contributes only invocation statistics. Business results/proof are
    # reconstructed from bound files below; success text alone is never enough.
    try:
        stats = json.loads(result.stdout)
        if type(stats.get('new_provider_calls')) is not int or stats['new_provider_calls'] < 0:
            raise ValueError('count unavailable')
    except (ValueError, TypeError, AttributeError):
        raise CompletionFailure('INVOCATION_COUNT_UNAVAILABLE', None) from None
    if cost_counter is not None:
        cost_counter.append(stats['new_provider_calls'])
    require(result.returncode == 0 or stats.get('status') in ('ANALYSIS_FAILED', 'NEEDS_REVIEW'),
        'PDS native stage rejected; no automatic retry')
    return stats['new_provider_calls']


def produce(*args, **kwargs):
    return counted(_produce, [], *args, **kwargs)


def _produce(binding_path, evidence_path, output, as_of_date, *, allow_synthetic=False,
        authorization_path=None, runner=None, defer_pds_review=False, cost_counter):
    """Production hook: analyze source evidence, then complete and return automatically.

    Success proof is written by the actual project producer, never by this hook.
    Default (no authorization/dependency) prepares research input and stays pending.
    """
    binding, flow, source, task = checked_binding(binding_path, allow_synthetic)
    evidence = check_evidence(evidence_path, binding, source, task, allow_synthetic)
    require(source['data_date'] <= as_of_date <= source['valid_through']
        and evidence['data_date'] <= as_of_date <= evidence['valid_through'], 'Research production source expired')
    output = Path(output).resolve()
    if (output/'uncertain-model-dispatch.json').exists():
        uncertain = verify_record(load(output/'uncertain-model-dispatch.json'))
        require(uncertain['binding_ref'] == ref(binding_path) and uncertain['evidence_ref'] == ref(evidence_path),
            'Uncertain dispatch belongs to another research source')
        return dict(status='NEEDS_REVIEW', research_completed=False, new_provider_calls=0,
            prior_provider_calls=None, prior_slot_state='DISPATCHED_OUTCOME_UNKNOWN_NO_RETRY')
    if (output/'failed-model-dispatch.json').exists():
        failed = verify_record(load(output/'failed-model-dispatch.json'))
        require(failed['binding_ref'] == ref(binding_path) and failed['evidence_ref'] == ref(evidence_path),
            'Failed dispatch belongs to another research source')
        return dict(status='ANALYSIS_FAILED', research_completed=False, new_provider_calls=0)
    if (output/'result.json').exists():
        return complete(binding_path, evidence_path, output/'model/receipt.json', output, as_of_date,
            allow_synthetic=allow_synthetic, authorization_path=authorization_path, runner=runner,
            defer_pds_review=defer_pds_review)
    receipt_path = output/'model/receipt.json'
    if receipt_path.exists():
        cached = verify_record(load(receipt_path))
        if cached['status'] == 'ANALYSIS_FAILED':
            job, attempt = record(cached['job_ref']), record(cached['attempt_ref'])
            require(cached['stage'] == job['stage'] == 'research' and job['flow_ref'] == binding['flow_ref']
                and job['input_ref'] == cached['input_ref'] == evidence['record_ref']
                and cached['identity'] == task['identity'] and job['methods'] == flow['methods']
                and attempt['job_ref'] == cached['job_ref'] and attempt['origin'] == cached['origin'],
                'Failed research slot/input binding differs')
            check_refs(job['methods'] + job['source_refs'] + [job['request_ref']])
            return dict(status='ANALYSIS_FAILED', research_completed=False, new_provider_calls=0)
    # The PDS model worker owns its immutable attempt and prevents retries.
    try:
        calls = invocation(binding, flow, ['research', '--binding', binding_path, '--evidence', evidence_path,
            '--output-directory', output/'model', '--as-of-date', as_of_date],
            allow_synthetic=allow_synthetic, authorization_path=authorization_path, runner=runner,
            cost_counter=cost_counter)
    except CompletionFailure as error:
        if error.new_provider_calls is None:
            write(output/'uncertain-model-dispatch.json', sealed(dict(binding_ref=ref(binding_path),
                evidence_ref=ref(evidence_path), provider_calls=None,
                slot_state='DISPATCHED_OUTCOME_UNKNOWN_NO_RETRY', automatic_retry=False)))
        raise
    if not receipt_path.exists():
        if calls:
            write(output/'failed-model-dispatch.json', sealed(dict(binding_ref=ref(binding_path),
                evidence_ref=ref(evidence_path), original_provider_calls=calls, receipt_available=False)))
            return dict(status='ANALYSIS_FAILED', research_completed=False, new_provider_calls=calls)
        return dict(status='WAITING_FOR_NEW_ANALYSIS', research_completed=False,
            new_provider_calls=calls, model_job_ref=ref(output/'model/job.json'))
    proof = verify_record(load(receipt_path))
    if proof['status'] != 'ANALYSIS_COMPLETED':
        return dict(status='ANALYSIS_FAILED', research_completed=False, new_provider_calls=calls)
    result = complete(binding_path, evidence_path, receipt_path, output, as_of_date,
        allow_synthetic=allow_synthetic, authorization_path=authorization_path, runner=runner,
        defer_pds_review=defer_pds_review)
    result['new_provider_calls'] += calls
    return result


def check_operating_feedback(feedback, result_ref, binding, flow, task, as_of_date):
    require(feedback['schema'] == 'pds-native-market-feedback-result/v1'
        and feedback['research_result_ref'] == result_ref and feedback['task_ref'] == binding['task_ref']
        and feedback['identity'] == task['identity'] and feedback['origin'] in ('PROJECT_PDS_LLM', 'SYNTHETIC_TEST')
        and feedback['market_findings'] == record(result_ref)['analysis'], 'Cached PDS feedback binding differs')
    if feedback['operating_reassessment'] is None:
        require(feedback['current_business_direction'] == 'NOT_REEVALUATED'
            and feedback['status'] in ('RESEARCH_CONSUMED_NEEDS_PDS_REVIEW', 'RESEARCH_CONSUMED_REVIEW_FAILED'),
            'Unreviewed feedback claims a direction')
        if feedback['reassessment_receipt_ref']:
            proof = record(feedback['reassessment_receipt_ref'])
            require(proof['status'] == 'ANALYSIS_FAILED', 'Pending review cites successful proof')
        return
    proof = record(feedback['reassessment_receipt_ref'])
    job, attempt = record(proof['job_ref']), record(proof['attempt_ref'])
    require(job['stage'] == proof['stage'] == 'feedback' and job['flow_ref'] == binding['flow_ref']
        and job['methods'] == flow['methods'] and job['model'] == proof['model']
        and job['identity'] == proof['identity'] == task['identity']
        and proof['origin'] == attempt['origin'] == feedback['origin']
        and attempt['job_ref'] == proof['job_ref'] and attempt['max_calls'] == 1 and attempt['retries'] == 0
        and proof['status'] == 'ANALYSIS_COMPLETED' and proof['provider_calls'] == 1
        and proof['transport']['phase'] == 'COMPLETE' and proof['transport']['http_status'] == 200,
        'Cached PDS reassessment production proof differs')
    require((proof['execution_mode'] == 'OFFLINE_DEPENDENCY') == (proof['origin'] == 'SYNTHETIC_TEST'),
        'Cached PDS reassessment provenance differs')
    if proof['origin'] == 'SYNTHETIC_TEST':
        require(attempt['authorization_ref'] is None and attempt['offline_dependency_ref'] == flow['offline_dependency_ref'],
            'Cached PDS offline dependency differs')
    else:
        auth = record(attempt['authorization_ref'])
        original_execution_day = datetime.fromisoformat(attempt['executed_at_utc']).astimezone(
            ZoneInfo(auth['timezone'])).date().isoformat()
        require(auth['source_ref'] == flow['source_ref'] and auth['identity'] == task['identity']
            and auth['model'] == proof['model'] and auth['stage_limits'].get('feedback') == 1
            and auth['authorized_by'] == 'HUMAN' and auth['live_model_authorized'] is True
            and auth['cost_status'] == 'EXPLICITLY_APPROVED' and auth['retries'] == 0
            and auth['valid_from'] <= original_execution_day <= auth['valid_through']
            and attempt['offline_dependency_ref'] is None,
            'Cached PDS model approval differs')
        for reference in auth['source_refs']:
            check_refs([reference])
    for reference in job['source_refs'] + job['methods'] + [job['request_ref'], proof['response_ref']]:
        check_refs([reference])
    require(sha256(Path(job['request_ref']['path']).read_bytes()).hexdigest() == job['request_sha256'] == proof['request_sha256'],
        'Cached PDS request differs')
    input_ref = job['source_refs'][0]
    input_value = record(input_ref)
    require(job['source_refs'][1:] == [result_ref, ref(Path(binding['flow_ref']['path']).parent/'return.json')]
        and input_value['research_result_ref'] == result_ref and input_value['identity'] == task['identity']
        and input_value['original_question'] == task['question'] and input_value['findings'] == feedback['market_findings']
        and job['input_ref'] == proof['input_ref'] == input_value['record_ref'], 'Cached PDS evidence input differs')
    answer = verified(proof['response_ref'])
    require(answer == proof['proposal'] == feedback['operating_reassessment']
        and set(answer) == {'input_ref', 'identity', 'direction', 'explanation', 'supporting', 'opposing', 'unknown', 'changes_choice_if'}
        and answer['input_ref'] == input_value['record_ref'] and answer['identity'] == task['identity']
        and answer['direction'] in ('KEEP', 'REVISE_CANDIDATE', 'DEFER'), 'Cached PDS review raw answer differs')
    check_statements(answer, {'research', 'facts'})
    for key in ('explanation', 'changes_choice_if'):
        require(type(answer[key]) is str and 0 < len(answer[key]) <= 2000, 'Cached PDS review explanation missing')


def publish_readback(output, feedback_path, binding_path, result_ref, task, proof, *, initial=False):
    feedback = record(ref(feedback_path))
    response = sealed(dict(schema='market-native-pds-return/v1', research_result_ref=result_ref,
        binding_ref=ref(binding_path), task_ref=verify_record(load(binding_path))['task_ref'],
        feedback_ref=ref(feedback_path), status=feedback['status'], origin=proof['origin'],
        new_provider_calls=0, business_value_accepted=False))
    response_path = output/'returns'/response['record_ref'][:16]/'pds-response.json'
    write(response_path, response)
    readback = sealed(dict(schema='market-native-completion-readback/v1', status='PDS_RESEARCH_FEEDBACK_READ_BACK',
        result_ref=result_ref, response_ref=ref(response_path), feedback_ref=ref(feedback_path),
        identity=task['identity'], origin=proof['origin']))
    write(response_path.parent/'readback.json', readback)
    if initial:
        write(output/'pds-response.json', response)
        # The old pending revision remains immutable after a later authorized review.
        write(output/'readback.json', readback)
    return ref(feedback_path)


def complete(*args, **kwargs):
    return counted(_complete, [], *args, **kwargs)


def _complete(binding_path, evidence_path, analysis_receipt_path, output, as_of_date, *,
        allow_synthetic=False, authorization_path=None, runner=None, defer_pds_review=False, cost_counter):
    binding, flow, source, task = checked_binding(binding_path, allow_synthetic)
    evidence = check_evidence(evidence_path, binding, source, task, allow_synthetic)
    require(source['data_date'] <= as_of_date <= source['valid_through']
        and evidence['data_date'] <= as_of_date <= evidence['valid_through'], 'Research completion source expired')
    proof = verify_record(load(analysis_receipt_path))
    job, attempt = record(proof['job_ref']), record(proof['attempt_ref'])
    require(proof['schema'] == 'pds-native-market-model-receipt/v1' and proof['stage'] == 'research'
        and proof['status'] == 'ANALYSIS_COMPLETED' and proof['input_ref'] == evidence['record_ref']
        and proof['identity'] == task['identity'] and proof['provider_calls'] == 1
        and proof['transport']['phase'] == 'COMPLETE' and proof['transport']['http_status'] == 200
        and job['flow_ref'] == binding['flow_ref'] and job['input_ref'] == evidence['record_ref']
        and job['stage'] == 'research' and job['request_sha256'] == proof['request_sha256']
        and attempt['job_ref'] == proof['job_ref'] and attempt['origin'] == proof['origin'],
        'Research producer receipt does not prove this successful analysis')
    require(proof['origin'] in ('PROJECT_PDS_LLM', 'SYNTHETIC_TEST')
        and (proof['origin'] != 'SYNTHETIC_TEST' or allow_synthetic)
        and (not binding['synthetic'] or proof['origin'] == 'SYNTHETIC_TEST'), 'Research origin differs or was promoted')
    require((proof['execution_mode'] == 'OFFLINE_DEPENDENCY') == (proof['origin'] == 'SYNTHETIC_TEST'),
        'Research execution provenance differs')
    for reference in job['source_refs'] + job['methods'] + [proof['response_ref']]:
        check_refs([reference])
    answer = verified(proof['response_ref'])
    check_research_answer(answer, task, evidence)
    require(answer == proof['proposal'] and answer['identity'] == task['identity']
        and answer['task_id'] == task['task_id'] and answer['question'] == task['question']
        and answer['expected_answer'] == task['expected_answer'] and answer['window'] == source['market_window'],
        'Research raw answer task/question/window differs')
    output = Path(output).resolve()
    result = sealed(dict(schema='market-native-research-result/v1', status='ANALYSIS_COMPLETED',
        binding_ref=ref(binding_path), task_ref=binding['task_ref'], identity=task['identity'],
        question=task['question'], expected_answer=task['expected_answer'], window=source['market_window'],
        evidence_ref=ref(evidence_path), analysis_receipt_ref=ref(analysis_receipt_path),
        analysis=answer, origin=proof['origin'], research_completed=True, business_value_accepted=False,
        methods=[ref(__file__), ref(ROOT/'scripts/run_native_research_completion.py')], policy=dict(POLICY)))
    write(output/'result.json', result)
    result_ref = ref(output/'result.json')
    response_path = output/'pds-response.json'
    if response_path.exists():
        response = verify_record(load(response_path))
        require(response['research_result_ref'] == ref(output/'result.json'), 'Cached PDS return belongs to another result')
        readback = verify_record(load(output/'readback.json'))
        revision_response = output/'returns'/response['record_ref'][:16]/'pds-response.json'
        require(readback['response_ref'] == ref(revision_response)
            and record(readback['response_ref']) == response
            and readback['result_ref'] == ref(output/'result.json'),
            'Cached completion readback differs')
        feedback_path = Path(response['feedback_ref']['path'])
        completed_path = Path(binding['flow_ref']['path']).parent/'feedback/result.json'
        if completed_path.exists():
            completed_feedback = verify_record(load(completed_path))
            feedback_path = completed_path.parent/'revisions'/completed_feedback['record_ref'][:16]/'result.json'
            require(record(ref(feedback_path)) == completed_feedback, 'Completed PDS revision differs')
        feedback = record(ref(feedback_path))
        check_operating_feedback(feedback, result_ref, binding, flow, task, as_of_date)
        can_resume = feedback['status'] == 'RESEARCH_CONSUMED_NEEDS_PDS_REVIEW' and not defer_pds_review and (
            authorization_path is not None or (allow_synthetic and binding['offline_dependency_ref'] is not None))
        if not can_resume:
            feedback_ref = publish_readback(output, feedback_path, binding_path, result_ref, task, proof)
            return dict(status=feedback['status'], result_ref=result_ref,
                feedback_ref=feedback_ref, invocation_status='REUSED_COMPLETED_RETURN', new_provider_calls=0)
    approval_key = ref(authorization_path)['sha256'] if authorization_path else (
        'offline-feedback' if allow_synthetic and not defer_pds_review else 'received-no-review')
    attempt_path = output/('return-attempt-'+digest(approval_key)[:16]+'.json')
    require(not attempt_path.exists(), 'Failed/incomplete return needs review; no automatic retry')
    write(attempt_path, sealed(dict(result_ref=ref(output/'result.json'),
        binding_ref=ref(binding_path), consumer_method=ref(Path(binding['pds_root'])/'tools/run_native_market_flow.py'))))
    # PDS consumes findings and produces a separately proven operating review.
    calls = invocation(binding, flow, ['feedback', '--binding', binding_path, '--result', output/'result.json',
        '--as-of-date', as_of_date], allow_synthetic=allow_synthetic,
        authorization_path=authorization_path, runner=runner, inject_offline_dependency=not defer_pds_review,
        cost_counter=cost_counter)
    # Derive the feedback path from the original bound flow, not stdout.
    feedback_root = Path(binding['flow_ref']['path']).parent/'feedback'
    candidates = list((feedback_root/'revisions').glob('*/result.json'))
    feedback = None
    for path in candidates:
        value = verify_record(load(path))
        if value['research_result_ref'] == ref(output/'result.json'):
            if feedback is None or value['operating_reassessment'] is not None:
                feedback = value
                feedback_path = path
    require(feedback is not None and feedback['identity'] == task['identity'] and feedback['market_findings'] == answer,
        'PDS did not consume the bound research findings')
    check_operating_feedback(feedback, result_ref, binding, flow, task, as_of_date)
    feedback_ref = publish_readback(output, feedback_path, binding_path, result_ref, task, proof,
        initial=not response_path.exists())
    return dict(status=feedback['status'], result_ref=ref(output/'result.json'), feedback_ref=ref(feedback_path),
        invocation_status='RESEARCH_COMPLETED_RETURNED_AND_CONSUMED', new_provider_calls=calls)


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['produce', 'complete'])
    for name in ('binding', 'evidence', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--analysis-receipt', type=Path)
    parser.add_argument('--as-of-date', required=True)
    parser.add_argument('--authorization', type=Path)
    parser.add_argument('--allow-synthetic', action='store_true')
    parser.add_argument('--defer-pds-review', action='store_true')
    args = parser.parse_args(argv)
    try:
        options = dict(allow_synthetic=args.allow_synthetic, authorization_path=args.authorization,
            defer_pds_review=args.defer_pds_review)
        if args.command == 'produce':
            result = produce(args.binding, args.evidence, args.output, args.as_of_date, **options)
        else:
            require(args.analysis_receipt is not None, 'Completion needs its own analysis receipt')
            result = complete(args.binding, args.evidence, args.analysis_receipt, args.output, args.as_of_date, **options)
    except (ValueError, KeyError, TypeError, OSError) as error:
        result = dict(status='NEEDS_REVIEW', failure_type=type(error).__name__, research_completed=False,
            new_provider_calls=getattr(error, 'new_provider_calls', 0))
        if result['new_provider_calls'] is None:
            result['slot_state'] = 'DISPATCHED_OUTCOME_UNKNOWN_NO_RETRY'
    import json
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if result['status'] in ('NEEDS_REVIEW', 'ANALYSIS_FAILED') else 0
