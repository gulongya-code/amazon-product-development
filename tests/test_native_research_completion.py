"""Independent market-side contract tests; all sources/dependencies are offline."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.native_research_case import DATE
from amazon_product_intelligence import native_research_completion as completion

pytestmark = pytest.mark.native_integration


def pending(tmp_path, native_case):
    native_case.source(tmp_path)
    return native_case.evidence(tmp_path, native_case.run(tmp_path, native_case.dependency(tmp_path)))


def test_pending_synthetic_intake_is_not_research_completion(tmp_path, native_case):
    binding,market=pending(tmp_path, native_case)
    b=native_case.native.read(native_case.native.reference(binding))
    intake=native_case.native.read(b['intake_ref'])
    assert intake['status']=='ACCEPTED_PENDING_ANALYSIS' and intake['research_completed'] is False
    with pytest.raises(ValueError):
        completion.produce(binding,market,tmp_path/'research',DATE)
    assert not (tmp_path/'research/result.json').exists()


def test_actual_two_process_completion_and_readback_are_repeatable(tmp_path, native_case):
    binding,market=pending(tmp_path, native_case)
    first=completion.produce(binding,market,tmp_path/'research',DATE,allow_synthetic=True)
    assert first['status']=='RESEARCH_CONSUMED_AND_PDS_REVIEWED'
    before=native_case.files(tmp_path)
    again=completion.produce(binding,market,tmp_path/'research',DATE,allow_synthetic=True,
        runner=lambda *a,**k:pytest.fail('Repeated completion worker invoked'))
    assert again['feedback_ref']==first['feedback_ref'] and again['new_provider_calls']==0
    assert before==native_case.files(tmp_path)


def test_nonzero_failed_worker_keeps_reported_call_count_and_does_not_retry(tmp_path,capsys,monkeypatch, native_case):
    # Fee-count interface simulation only: the fake worker reports one call but
    # makes zero actual model/HTTP calls and intentionally has no successful proof.
    binding,market=pending(tmp_path, native_case);calls=[]
    def failed_worker(*args,**kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1,stdout='{"status":"ANALYSIS_FAILED","new_provider_calls":1}',stderr='secret diagnostic excluded')
    monkeypatch.setattr(completion.subprocess,'run',failed_worker)
    args=['produce','--binding',str(binding),'--evidence',str(market),'--output',str(tmp_path/'research'),
        '--as-of-date',DATE,'--allow-synthetic']
    assert completion.main(args)==1
    output=capsys.readouterr().out
    assert '"new_provider_calls": 1' in output and 'secret' not in output
    first_failure=native_case.strict_json_load(tmp_path/'research/failed-model-dispatch.json')
    assert first_failure['original_provider_calls']==1 and len(calls)==1
    before=native_case.files(tmp_path)
    result=completion.produce(binding,market,tmp_path/'research',DATE,allow_synthetic=True,
        runner=lambda *a,**k:pytest.fail('Failure retried'))
    assert result['status']=='ANALYSIS_FAILED' and result['new_provider_calls']==0
    assert before==native_case.files(tmp_path)


def test_failed_research_provider_has_no_second_invocation(tmp_path, native_case):
    native_case.source(tmp_path);binding,market=native_case.evidence(tmp_path,native_case.run(tmp_path,native_case.dependency(tmp_path,fail='research')))
    first=completion.produce(binding,market,tmp_path/'research',DATE,allow_synthetic=True)
    assert first['status']=='ANALYSIS_FAILED'
    before=native_case.files(tmp_path)
    assert completion.produce(binding,market,tmp_path/'research',DATE,allow_synthetic=True,
        runner=lambda *a,**k:pytest.fail('Failed provider retried'))==first
    assert before==native_case.files(tmp_path)


@pytest.mark.parametrize('change',[dict(origin='PROJECT_PDS_LLM'),dict(task_id='OTHER'),
    dict(window=dict(start_date='2026-10-13',end_date=DATE,timezone='America/Los_Angeles',currency='USD'))])
def test_result_proof_wrong_origin_task_or_window_rejected(tmp_path,change, native_case):
    binding,market=pending(tmp_path, native_case)
    completion.produce(binding,market,tmp_path/'research',DATE,allow_synthetic=True,defer_pds_review=True)
    proof_path=tmp_path/'research/model/receipt.json'
    if 'origin' in change:
        native_case.tamper(proof_path,**change)
    else:
        value=native_case.strict_json_load(proof_path)
        answer=dict(value['proposal']);answer.update(change)
        raw=Path(value['response_ref']['path']);raw.write_bytes(native_case.canonical_bytes(answer))
        native_case.tamper(proof_path,proposal=answer,response_ref=native_case.native.reference(raw))
    with pytest.raises(ValueError):
        completion.complete(binding,market,proof_path,tmp_path/'research',DATE,allow_synthetic=True)


def test_expired_return_is_not_completed_using_an_old_task_date(tmp_path, native_case):
    binding,market=pending(tmp_path, native_case)
    completion.produce(binding,market,tmp_path/'research',DATE,allow_synthetic=True,defer_pds_review=True)
    with pytest.raises(ValueError):
        completion.complete(binding,market,tmp_path/'research/model/receipt.json',tmp_path/'research',
            '2026-10-17',allow_synthetic=True)


def test_market_cache_revalidates_pds_body_input_and_model_proof(tmp_path, native_case):
    binding,market=pending(tmp_path, native_case)
    completion.produce(binding,market,tmp_path/'research',DATE,allow_synthetic=True)
    path=tmp_path/'flow/feedback/model/receipt.json'
    native_case.tamper(path,stage='research')
    with pytest.raises(ValueError):
        completion.produce(binding,market,tmp_path/'research',DATE,allow_synthetic=True)


def test_return_failure_does_not_automatically_repeat_callback(tmp_path, native_case):
    binding,market=pending(tmp_path, native_case);calls=[]
    actual=completion.subprocess.run
    def worker(command,**kwargs):
        if 'feedback' in command:
            calls.append(command)
            return SimpleNamespace(returncode=1,stdout='{"status":"NEEDS_REVIEW","new_provider_calls":0}',stderr='')
        return actual(command,**kwargs)
    with pytest.raises(ValueError):
        completion.produce(binding,market,tmp_path/'research',DATE,allow_synthetic=True,runner=worker)
    with pytest.raises(ValueError):
        completion.produce(binding,market,tmp_path/'research',DATE,allow_synthetic=True,
            runner=lambda *a,**k:pytest.fail('Failed return was repeated'))
    assert len(calls)==1


@pytest.mark.parametrize('failure',['timeout','lost'])
def test_model_worker_timeout_alignment_unknown_count_and_no_retry(tmp_path,failure, native_case):
    import subprocess
    binding,market=pending(tmp_path, native_case);seen=[]
    def disconnected(command,**kwargs):
        seen.append(kwargs['timeout'])
        if failure=='timeout':
            raise subprocess.TimeoutExpired(command,kwargs['timeout'],output='suppressed diagnostic')
        raise OSError('connection lost; suppressed diagnostic')
    with pytest.raises(completion.CompletionFailure) as error:
        completion.produce(binding,market,tmp_path/'research',DATE,allow_synthetic=True,runner=disconnected)
    assert seen==[660] and error.value.new_provider_calls is None
    marker=native_case.strict_json_load(tmp_path/'research/uncertain-model-dispatch.json')
    assert marker['provider_calls'] is None and marker['automatic_retry'] is False
    before=native_case.files(tmp_path)
    repeat=completion.produce(binding,market,tmp_path/'research',DATE,allow_synthetic=True,
        runner=lambda *a,**k:pytest.fail('Unknown paid slot retried'))
    assert repeat['status']=='NEEDS_REVIEW' and repeat['new_provider_calls']==0 and repeat['prior_provider_calls'] is None
    assert before==native_case.files(tmp_path)
