"""Synthetic new-request acceptance; pending is never analysis or business proof."""
from copy import deepcopy
import json

import pytest
from amazon_product_intelligence import market_research_intake as intake
from amazon_product_intelligence.market_pds_workflow import digest, load, POLICY
from amazon_product_intelligence.yps_competitive_difference import ref


def write(path,value):
    value={k:v for k,v in value.items() if k!='record_ref'}
    value['record_ref']=digest(value)
    path.write_text(json.dumps(value,ensure_ascii=False),encoding='utf8')
    return ref(path)


def case(tmp_path):
    identity=dict(sku='TEST-SKU',asin='B000000099')
    source=dict(identity=identity,issue_state='OPEN',business_question='Synthetic price question',
                objective='Synthetic profit goal',data_date='2026-10-14',valid_through='2026-10-16',source_refs=[])
    source_ref=write(tmp_path/'problem.json',source)
    paths=dict(identity='/identity',state='/issue_state',question='/business_question',objective='/objective',
               data_date='/data_date',valid_through='/valid_through')
    context=dict(schema='pds-market-selection-context/v1',identity=identity,problem_ref=source_ref,paths=paths,
                 values=dict(state='OPEN',question=source['business_question'],objective=source['objective'],
                             data_date=source['data_date'],valid_through=source['valid_through']),
                 review_trigger_ref=None,policy=deepcopy(POLICY))
    context_ref=write(tmp_path/'context.json',context)
    row=dict(claim='Synthetic evidence',evidence_refs=['problem'])
    answer=dict(input_ref=load(tmp_path/'context.json')['record_ref'],identity=identity,choice='NEW_RESEARCH',
                research_type='offer_comparison',reason='Synthetic reason',supporting=row,opposing=row,unknown=row,
                changes_choice_if='Independent new evidence',expected_answer='Synthetic comparison',
                evidence_requirement='Synthetic same-spec evidence',reuse_request_ref=None)
    selection=dict(schema='pds-market-tool-selection/v1',origin='SYNTHETIC_TEST',model_receipt_ref=None,
                   answer=answer,policy=deepcopy(POLICY))
    selection_ref=write(tmp_path/'selection.json',selection)
    task=dict(schema='pds-market-new-research-task/v1',task_id='market-'+'a'*24,identity=identity,
              context_ref=context_ref,selection_ref=selection_ref,problem_ref=source_ref,as_of_date='2026-10-14',
              question=source['business_question'],objective=source['objective'],research_type='offer_comparison',
              expected_answer=answer['expected_answer'],evidence_requirement=answer['evidence_requirement'],
              origin='SYNTHETIC_TEST',policy=deepcopy(POLICY))
    path=tmp_path/'task.json';write(path,task)
    return path,task


def test_new_task_is_pending_without_historical_receipt_and_repeat_unchanged(tmp_path):
    path,task=case(tmp_path);out=tmp_path/'intake.json'
    first=intake.receive(path,out,allow_synthetic=True);before=out.read_bytes()
    second=intake.receive(path,out,allow_synthetic=True)
    assert first==second and out.read_bytes()==before
    assert first['research_completed'] is False and first['business_value_accepted'] is False
    assert first['new_provider_calls']==0 and 'receipt_ref' not in task


def test_synthetic_tasks_refused_by_default(tmp_path):
    path,_=case(tmp_path)
    with pytest.raises(ValueError,match='Synthetic'):intake.receive(path,tmp_path/'intake.json')


@pytest.mark.parametrize('field,value',[('question','Another question'),('identity',dict(sku='OTHER')),
    ('research_type','unsupported'),('origin','CODEX_SESSION'),('expected_answer','A different answer')])
def test_mismatched_task_cannot_get_receipt(tmp_path,field,value):
    path,task=case(tmp_path);task[field]=value;write(path,task)
    with pytest.raises(ValueError):intake.receive(path,tmp_path/'intake.json',allow_synthetic=True)
    assert not (tmp_path/'intake.json').exists()


@pytest.mark.parametrize('value',[True,0])
def test_paid_or_nonboolean_policy_refused(tmp_path,value):
    path,task=case(tmp_path);task['policy']['new_paid_calls']=value;write(path,task)
    with pytest.raises(ValueError):intake.receive(path,tmp_path/'intake.json',allow_synthetic=True)


def test_resealed_open_projection_cannot_hide_closed_original_issue(tmp_path):
    path,task=case(tmp_path)
    source=load(tmp_path/'problem.json');source['issue_state']='CLOSED'
    task['problem_ref']=write(tmp_path/'problem.json',source)
    context=load(tmp_path/'context.json');context['problem_ref']=task['problem_ref']
    task['context_ref']=write(tmp_path/'context.json',context)
    selection=load(tmp_path/'selection.json');selection['answer']['input_ref']=load(tmp_path/'context.json')['record_ref']
    task['selection_ref']=write(tmp_path/'selection.json',selection);write(path,task)
    with pytest.raises(ValueError,match='original problem'):
        intake.receive(path,tmp_path/'intake.json',allow_synthetic=True)


def test_changed_original_evidence_rejected(tmp_path):
    path,_=case(tmp_path)
    (tmp_path/'problem.json').write_text('{}',encoding='utf8')
    with pytest.raises(ValueError):intake.receive(path,tmp_path/'intake.json',allow_synthetic=True)


@pytest.mark.parametrize('date',['2026-10-20','2026-01-01','2026-1-1'])
def test_invalid_or_out_of_window_date_refused(tmp_path,date):
    path,task=case(tmp_path);task['as_of_date']=date;write(path,task)
    with pytest.raises(ValueError):intake.receive(path,tmp_path/'intake.json',allow_synthetic=True)


def test_cached_acceptance_cannot_claim_research_complete(tmp_path):
    path,_=case(tmp_path);out=tmp_path/'intake.json'
    intake.receive(path,out,allow_synthetic=True)
    old=load(out);old['research_completed']=True;write(out,old)
    with pytest.raises(ValueError,match='completed'):intake.receive(path,out,allow_synthetic=True)
