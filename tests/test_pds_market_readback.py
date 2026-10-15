"""Receipt identity and origin checks, with synthetic local files only."""
from hashlib import sha256
import json
import pytest
from amazon_product_intelligence.pds_market_readback import consume, SP_STATUS


def write(path,value):
    path.write_text(json.dumps(value),encoding='utf8')
    return dict(path=str(path),sha256=sha256(path.read_bytes()).hexdigest())


def case(tmp_path,**changes):
    source=write(tmp_path/'market.json',dict(sp043b_status=SP_STATUS))
    evidence=write(tmp_path/'evidence.json',dict(record_ref='test',market_result_ref=source,source_refs=[source]))
    value=dict(kind='YPS_MARKET_OFFER_PROJECT_REVIEW',status='ANALYSIS_COMPLETED',
        origin='PROJECT_PROVIDER_ANALYSIS',provider_calls=1,
        transport=dict(phase='COMPLETE',http_status=200),input_ref='test',
        proposal=dict(input_ref='test',original_claim_review={k:{} for k in ['M1','M2','M3','M4','M5']},
            recommendation={},remaining_gap_action={}),evidence_ref=evidence,market_result_ref=source,
        non_executable=True,formal_state_changed=False,automatic_scheduling=False,purchases=0,sp043b_status=SP_STATUS)
    value.update(changes)
    return write(tmp_path/'review.json',value),source


def test_matching_native_review_is_read_back_without_acceptance(tmp_path):
    receipt,source=case(tmp_path)
    result=consume(receipt['path'],receipt['sha256'],source['path'],tmp_path/'out.json')
    assert result['analytical_consumption_confirmed'] is True
    assert result['business_value_accepted'] is False


@pytest.mark.parametrize('changes',[dict(origin='CODEX_SKILL_REVIEW'),dict(status='ANALYSIS_FAILED'),
    dict(provider_calls=0),dict(automatic_scheduling=True),dict(sp043b_status='ACCEPTED')])
def test_failed_or_session_or_executing_receipt_not_native_completion(tmp_path,changes):
    receipt,source=case(tmp_path,**changes)
    with pytest.raises(ValueError):consume(receipt['path'],receipt['sha256'],source['path'],tmp_path/'out.json')
    assert not (tmp_path/'out.json').exists()


def test_changed_source_cannot_reuse_receipt(tmp_path):
    receipt,source=case(tmp_path)
    write(tmp_path/'market.json',dict(sp043b_status='changed'))
    with pytest.raises(ValueError):consume(receipt['path'],receipt['sha256'],source['path'],tmp_path/'out.json')
