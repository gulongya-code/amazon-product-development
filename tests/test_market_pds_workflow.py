"""Synthetic workflow contracts; real local replays are documented separately."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from amazon_product_intelligence import market_pds_workflow as workflow


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf8')
    return workflow.ref(path)


def case(tmp_path, research_type='offer_comparison', asin='B000000001'):
    (tmp_path / 'tools').mkdir(exist_ok=True)
    (tmp_path / 'tools/run_market_research_handoff.py').write_text('synthetic consumer method', encoding='utf8')
    schema, kind, key = workflow.FORMATS[research_type]
    identity = dict(asin=asin, sku='TEST-SKU')
    source = tmp_path / 'source.txt'
    source.write_text('synthetic evidence', encoding='utf8')
    packet = dict(schema=schema, identity=identity, source_refs=[workflow.ref(source)],
                  non_executable=True, sp043b_status=workflow.SP_STATUS)
    if research_type == 'native_offer_review':
        packet['scope'] = dict(asins=[asin])
        packet['observations'] = [dict(asin=asin)]
    market_ref = write(tmp_path / 'market.json', packet)
    context = dict(identity=identity, record_ref='test-context', source_refs=[workflow.ref(source)],
                   **{key: market_ref})
    context_ref = write(tmp_path / 'context.json', context)
    receipt = dict(kind=kind, identity=identity, evidence_ref=context_ref, input_ref='test-context',
                   status='ANALYSIS_COMPLETED', origin='PROJECT_PDS_LLM', provider_calls=1,
                   transport=dict(phase='COMPLETE', http_status=200),
                   proposal=dict(recommendation='Synthetic retained recommendation'),
                   generated_at_utc='2026-10-13T00:00:00+00:00', **{key: market_ref})
    if research_type == 'native_offer_review':
        receipt['origin'] = 'PROJECT_PROVIDER_ANALYSIS'
    receipt_path = tmp_path / 'receipt.json'
    write(receipt_path, receipt)
    task = workflow.make_task('test-task', research_type, tmp_path / 'market.json', receipt_path)
    task_path = tmp_path / 'task.json'
    write(task_path, task)
    return task_path, task, source


def consumer(monkeypatch, calls):
    def invoke(root, python, request_path, output):
        calls.append(str(request_path))
        request = workflow.load(request_path)
        receipt = workflow.verified(request['receipt_ref'])
        response = dict(schema='pds-market-handoff-response/v1', status='EXISTING_ANALYSIS_CONSUMED',
                        **{k: request[k] for k in ('task_id', 'task_fingerprint', 'research_type',
                           'identity', 'market_ref', 'receipt_ref', 'pds_context_ref', 'policy')},
                        new_provider_calls=0, evidence_refreshed=False, business_value_accepted=False,
                        original_analysis_at_utc=workflow.original_time(receipt), proposal=receipt['proposal'])
        response['record_ref'] = workflow.digest(response)
        workflow.save(output, response)
    monkeypatch.setattr(workflow, 'invoke_pds', invoke)


@pytest.mark.parametrize('research_type', tuple(workflow.FORMATS))
def test_full_workflow_and_repeat_skip_consumer(tmp_path, monkeypatch, research_type):
    task_path, task, _ = case(tmp_path, research_type)
    calls = []
    consumer(monkeypatch, calls)
    first = workflow.run(task_path, tmp_path / 'runs', tmp_path)
    second = workflow.run(task_path, tmp_path / 'runs', tmp_path)
    assert first['status'] == 'COMPLETED'
    assert second['invocation_status'] == 'REUSED_COMPLETED_WORKFLOW'
    assert len(calls) == 1 and first['new_provider_calls'] == 0
    assert first['business_value_accepted'] is False
    assert first['policy']['sp043b_status'] == workflow.SP_STATUS


def test_another_sku_uses_same_configurable_entry(tmp_path, monkeypatch):
    task_path, _, _ = case(tmp_path, asin='B000000099')
    consumer(monkeypatch, [])
    assert workflow.run(task_path, tmp_path / 'runs', tmp_path)['status'] == 'COMPLETED'


def test_changed_source_rejects_even_completed_cache(tmp_path, monkeypatch):
    task_path, _, source = case(tmp_path)
    calls = []
    consumer(monkeypatch, calls)
    workflow.run(task_path, tmp_path / 'runs', tmp_path)
    source.write_text('changed evidence', encoding='utf8')
    with pytest.raises(ValueError, match='evidence changed'):
        workflow.run(task_path, tmp_path / 'runs', tmp_path)
    assert len(calls) == 1


def test_missing_evidence_is_insufficient_not_normal(tmp_path, monkeypatch):
    task_path, _, source = case(tmp_path)
    monkeypatch.setattr(workflow, 'invoke_pds', lambda *a: pytest.fail('Consumer called'))
    source.unlink()
    assert workflow.run(task_path, tmp_path / 'runs', tmp_path)['status'] == 'INSUFFICIENT_EVIDENCE'


@pytest.mark.parametrize('field,value', [('new_paid_calls', True), ('scheduled_collection', True),
    ('execution_authorized', True), ('new_paid_calls', 0), ('sp043b_status', 'ACCEPTED')])
def test_expanded_policy_rejected_before_consumer(tmp_path, monkeypatch, field, value):
    task_path, task, _ = case(tmp_path)
    task['policy'] = deepcopy(task['policy'])
    task['policy'][field] = value
    write(task_path, task)
    monkeypatch.setattr(workflow, 'invoke_pds', lambda *a: pytest.fail('Consumer called'))
    with pytest.raises(ValueError, match='policy'):
        workflow.run(task_path, tmp_path / 'runs', tmp_path)


@pytest.mark.parametrize('field,value', [('origin', 'CODEX_SESSION'), ('status', 'ANALYSIS_FAILED'),
                                       ('provider_calls', 0)])
def test_invalid_receipt_never_falls_back_to_model(tmp_path, monkeypatch, field, value):
    task_path, task, _ = case(tmp_path)
    receipt = workflow.load(task['receipt_ref']['path'])
    receipt[field] = value
    task['receipt_ref'] = write(Path(task['receipt_ref']['path']), receipt)
    write(task_path, task)
    monkeypatch.setattr(workflow, 'invoke_pds', lambda *a: pytest.fail('Consumer called'))
    with pytest.raises(ValueError, match='existing PDS analysis'):
        workflow.run(task_path, tmp_path / 'runs', tmp_path)


def test_new_market_packet_cannot_use_old_analysis(tmp_path):
    task_path, task, _ = case(tmp_path)
    packet = workflow.load(task['market_ref']['path'])
    packet['new_dimension'] = 'new evidence requires a new review'
    task['market_ref'] = write(Path(task['market_ref']['path']), packet)
    write(task_path, task)
    with pytest.raises(ValueError, match='differs'):
        workflow.run(task_path, tmp_path / 'runs', tmp_path)


def test_failure_is_recorded_and_not_retried(tmp_path, monkeypatch):
    task_path, _, _ = case(tmp_path)
    calls = []
    def reject(*args):
        calls.append(1)
        raise ValueError('Rejected by PDS')
    monkeypatch.setattr(workflow, 'invoke_pds', reject)
    first = workflow.run(task_path, tmp_path / 'runs', tmp_path)
    second = workflow.run(task_path, tmp_path / 'runs', tmp_path)
    assert first['status'] == 'FAILED' and first['failed_stage'] == 'PDS_CONSUME'
    assert second['status'] == 'NEEDS_REVIEW' and len(calls) == 1


def test_wrong_response_is_not_success(tmp_path, monkeypatch):
    task_path, _, _ = case(tmp_path)
    consumer(monkeypatch, [])
    original = workflow.invoke_pds
    def wrong(*args):
        original(*args)
        response = workflow.load(args[-1])
        response['task_id'] = 'different-task'
        response['record_ref'] = workflow.digest({k: v for k, v in response.items() if k != 'record_ref'})
        write(args[-1], response)
    monkeypatch.setattr(workflow, 'invoke_pds', wrong)
    result = workflow.run(task_path, tmp_path / 'runs', tmp_path)
    assert result['status'] == 'FAILED' and result['failed_stage'] == 'READ_BACK'


def test_corrupted_output_cannot_be_reused(tmp_path, monkeypatch):
    task_path, _, _ = case(tmp_path)
    consumer(monkeypatch, [])
    result = workflow.run(task_path, tmp_path / 'runs', tmp_path)
    Path(result['artifacts'][-1]['path']).write_text('altered', encoding='utf8')
    with pytest.raises(ValueError, match='artifact changed'):
        workflow.run(task_path, tmp_path / 'runs', tmp_path)


def test_method_change_does_not_reuse_or_retry_old_workflow(tmp_path, monkeypatch):
    task_path, _, _ = case(tmp_path)
    calls = []
    consumer(monkeypatch, calls)
    workflow.run(task_path, tmp_path / 'runs', tmp_path)
    (tmp_path / 'tools/run_market_research_handoff.py').write_text('changed method', encoding='utf8')
    assert workflow.run(task_path, tmp_path / 'runs', tmp_path)['reason'] == 'WORKFLOW_METHOD_CHANGED'
    assert len(calls) == 1


def test_duplicate_task_keys_rejected(tmp_path):
    path = tmp_path / 'bad.json'
    path.write_text('{"task_id":"a","task_id":"b"}', encoding='utf8')
    with pytest.raises(ValueError, match='Duplicate'):
        workflow.load(path)
