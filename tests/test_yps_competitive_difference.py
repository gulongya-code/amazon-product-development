import pytest
from amazon_product_intelligence.yps_competitive_difference import Reviews, variant_scope, section


@pytest.mark.parametrize('text,expected',[
    ('Size: 1 Inch Style: Pack of 2','EXACT_SIZE_PACK_CLAIM'),
    ('Size: 1/2 Inch Style: Pack of 2','OTHER_SIZE'),
    ('Size: 1 Inch Style: Pack of 1','OTHER_PACK'),
    ('Size: 1 Inch','SIZE_MATCH_PACK_UNSTATED'),
    ('Style: Pack of 2','UNKNOWN_VARIANT'),
    ('','UNKNOWN_VARIANT'),
    ('Size: 11 Inch Style: Pack of 2','OTHER_SIZE')])
def test_variant_scope(text,expected):
    assert variant_scope(text)==expected


def test_scoped_review_excludes_profiles_and_duplicate_hidden_copy():
    p=Reviews();p.feed('''<div data-hook="review" id="R1"><img src="x">
    <span class="profile">Private Name</span><span data-hook="reviewTitle">Title</span>
    <span data-hook="review-date">Reviewed October 1</span>
    <a data-hook="format-strip">Size: 1 Inch</a>
    <span data-hook="reviewText">Good <b>valve</b></span>
    <span data-hook="reviewTitle">Title</span><a data-hook="format-strip">Size: 1 Inch</a>
    <span data-hook="reviewText">Good <b>valve</b></span></div>''')
    assert len(p.rows)==1
    r=p.rows[0]
    assert r['title']=='Title' and r['text']=='Good valve'
    assert r['variant_scope']=='SIZE_MATCH_PACK_UNSTATED'
    assert 'Private Name' not in str(r)


def test_missing_review_text_fails():
    with pytest.raises(ValueError,match='Incomplete'):
        Reviews().feed('<div data-hook="review"><span data-hook="review-date">date</span></div>')


def test_missing_page_section_is_not_absence_of_feature():
    with pytest.raises(ValueError):section('title only','About this item','details')


@pytest.mark.parametrize('field,bad',[
    ('origin','CODEX_SKILL_REVIEW'),('provider_calls',0),('non_executable',False),
    ('identity',{'asin':'OTHER'}),('status','ANALYSIS_FAILED')])
def test_readback_rejects_unqualified_pds(field,bad,tmp_path,monkeypatch):
    from amazon_product_intelligence import yps_competitive_difference as m
    packet=tmp_path/'packet.json';receipt=tmp_path/'receipt.json';evidence=tmp_path/'evidence.json'
    identity={'asin':'B0H5BWL6J2'}
    reference={'path':str(packet),'sha256':'digest'}
    market={'identity':identity,'sp043b_status':m.SP_STATUS}
    inputs={'record_ref':'input','market_result_ref':reference,'identity':identity,'source_refs':[]}
    result={'kind':'PDS_YPS_COMPETITIVE_REVIEW','status':'ANALYSIS_COMPLETED',
        'origin':'PROJECT_PDS_LLM','provider_calls':1,'market_result_ref':reference,
        'evidence_ref':{'path':str(evidence),'sha256':'e'},'input_ref':'input','identity':identity,
        'transport':{'phase':'COMPLETE','http_status':200},'non_executable':True,
        'constraints':{'automatic_scheduling':False,'execution_authorized':False,'sp043b_status':m.SP_STATUS},
        'proposal':{'consumed_evidence_ids':['E1','E2','E3','E4','E5','P1','P2'],'profit_check_status':'CLOSED'}}
    result[field]=bad
    def fake_read(path,digest):return {str(packet):market,str(receipt):result,str(evidence):inputs}[str(path)]
    monkeypatch.setattr(m,'read_verified',fake_read)
    with pytest.raises(ValueError,match='not qualified'):
        m.readback(receipt,'r',packet,tmp_path/'readback.json')
    assert not (tmp_path/'readback.json').exists()
