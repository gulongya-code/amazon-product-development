"""File-only new-research intake. An accepted task is not completed research."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
from datetime import date

from amazon_product_intelligence.market_pds_workflow import load, verified, verify_record, digest, POLICY, FORMATS
from amazon_product_intelligence.yps_competitive_difference import ref, save

FIELDS={'schema','task_id','identity','context_ref','selection_ref','problem_ref','as_of_date',
        'question','objective','research_type','expected_answer','evidence_requirement','origin','policy','record_ref'}
ANSWER_FIELDS={'input_ref','identity','choice','research_type','reason','supporting','opposing','unknown',
               'changes_choice_if','expected_answer','evidence_requirement','reuse_request_ref'}


def check_existing_receipt(receipt,task,task_ref):
    if (receipt['schema']!='market-new-research-intake/v1'
        or receipt['task_ref']!=task_ref or receipt['status']!='ACCEPTED_PENDING_ANALYSIS'
        or any(receipt[k]!=task[k] for k in ('task_id','identity','context_ref','selection_ref','origin','policy'))
        or receipt['research_completed'] is not False or receipt['business_value_accepted'] is not False
        or receipt['new_provider_calls']!=0):
        raise ValueError('Existing intake differs or claims completed research')


def receive(task_path,output,*,allow_synthetic=False):
    task=verify_record(load(task_path))
    if set(task)!=FIELDS or task['schema']!='pds-market-new-research-task/v1' or task['policy']!=POLICY:
        raise ValueError('New market task contract differs')
    if not re.fullmatch(r'market-[0-9a-f]{24}',task['task_id']) or any(type(task['policy'][k]) is not bool
            for k in POLICY if k!='sp043b_status'):
        raise ValueError('Task identity or policy types differ')
    context=verify_record(verified(task['context_ref']))
    selection=verify_record(verified(task['selection_ref']))
    source=verify_record(verified(task['problem_ref']))
    if (set(context)!={'schema','problem_ref','identity','paths','values','review_trigger_ref','policy','record_ref'}
        or set(context['paths'])!={'identity','state','question','objective','data_date','valid_through'}
        or set(selection)!={'schema','origin','model_receipt_ref','answer','policy','record_ref'}
        or set(selection['answer'])!=ANSWER_FIELDS or selection['answer']['reuse_request_ref'] is not None):
        raise ValueError('Context or selection fields differ')
    if (context['policy']!=POLICY or selection['policy']!=POLICY
        or any(type(context['policy'][k]) is not bool or type(selection['policy'][k]) is not bool
               for k in POLICY if k!='sp043b_status')):
        raise ValueError('Context/selection policy differs')
    for value in (context['values']['data_date'],task['as_of_date'],context['values']['valid_through']):
        if date.fromisoformat(value).isoformat()!=value:
            raise ValueError('Invalid evaluation or validity date')
    for field in ('question','objective','expected_answer','evidence_requirement'):
        if type(task[field]) is not str or not 0<len(task[field])<=2000:
            raise ValueError('Task question or expected evidence is missing')
    if (context['schema']!='pds-market-selection-context/v1'
        or context['problem_ref']!=task['problem_ref'] or context['identity']!=task['identity']
        or context['values']['state']!='OPEN' or context['values']['question']!=task['question']
        or context['values']['objective']!=task['objective']
        or not context['values']['data_date']<=task['as_of_date']<=context['values']['valid_through']
        or selection['schema']!='pds-market-tool-selection/v1' or selection['policy']!=POLICY
        or selection['answer']['input_ref']!=context['record_ref'] or selection['origin']!=task['origin']
        or selection['answer']['identity']!=task['identity'] or selection['answer']['choice']!='NEW_RESEARCH'
        or selection['answer']['research_type']!=task['research_type'] or task['research_type'] not in FORMATS
        or selection['answer']['expected_answer']!=task['expected_answer']
        or selection['answer']['evidence_requirement']!=task['evidence_requirement']):
        raise ValueError('Task is not bound to an eligible open problem and new-research choice')
    if task['origin']=='SYNTHETIC_TEST':
        if not allow_synthetic or selection['model_receipt_ref'] is not None:
            raise ValueError('Synthetic task is refused by default')
    elif task['origin']=='PROJECT_PDS_LLM':
        proof=verify_record(verified(selection['model_receipt_ref']))
        if (proof['status']!='ANALYSIS_COMPLETED' or proof['origin']!='PROJECT_PDS_LLM'
            or proof['input_ref']!=context['record_ref'] or proof['proposal']!=selection['answer']
            or proof['provider_calls']!=1 or proof['transport']['phase']!='COMPLETE'
            or proof['transport']['http_status']!=200):
            raise ValueError('Model proof does not establish this selection')
    else:
        raise ValueError('Unknown selection origin')
    # Rebind every projected context field to the original source, including
    # state. A sealed projection cannot silently change CLOSED into OPEN.
    for name,path in context['paths'].items():
        value=source
        for part in path.split('/')[1:] if path else []:
            part=part.replace('~1','/').replace('~0','~')
            value=value[int(part)] if type(value) is list and part.isdecimal() else value[part]
        expected=context['identity'] if name=='identity' else context['values'][name]
        if name=='state':
            value='OPEN' if value in ('OPEN','PENDING') else value
        if value!=expected:
            raise ValueError('Context differs from original problem values')
    for reference in source.get('source_refs',[]):
        if ref(reference['path'])['sha256']!=reference['sha256']:
            raise ValueError('Original problem evidence changed')
    task_ref=ref(task_path)
    output=Path(output)
    if output.exists():
        old=verify_record(load(output))
        check_existing_receipt(old,task,task_ref)
        return old
    result=dict(schema='market-new-research-intake/v1',status='ACCEPTED_PENDING_ANALYSIS',
        task_id=task['task_id'],identity=task['identity'],task_ref=task_ref,
        context_ref=task['context_ref'],selection_ref=task['selection_ref'],origin=task['origin'],
        received_at_utc=datetime.now(timezone.utc).isoformat(),
        pending_reason='NEW_RESEARCH_REQUIRES_SEPARATE_EVIDENCE_AND_ANALYSIS_AUTHORIZATION',
        new_provider_calls=0,research_completed=False,business_value_accepted=False,
        policy=dict(POLICY))
    result['record_ref']=digest(result)
    output.parent.mkdir(parents=True,exist_ok=True);save(output,result)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--allow-synthetic',action='store_true')
    args=parser.parse_args(argv)
    try:
        result=receive(args.task,args.output,allow_synthetic=args.allow_synthetic)
    except (ValueError,KeyError,TypeError,OSError,IndexError) as error:
        print(str(type(error).__name__)+': MARKET_INTAKE_REJECTED');return 1
    print(result['status']);return 0


if __name__=='__main__':
    raise SystemExit(main())
