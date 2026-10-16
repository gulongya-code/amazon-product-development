"""Market-owned synthetic examples using PDS production APIs, never PDS tests.

Imported only after explicit integration setup. The external checkout is a
versioned dependency; none of its test globals or machine paths are consumed.
"""

import importlib
from pathlib import Path


DATE = '2026-10-14'
WINDOW = dict(start_date=DATE, end_date=DATE, timezone='America/Los_Angeles', currency='USD')
MARKET = Path(__file__).resolve().parents[1]

DEPENDENCY = '''
import json
class Provider:
    def __init__(self, stage):
        self.stage = stage
        self.call_count = 0
        self.transport_diagnostic = dict(phase='NOT_CALLED', http_status=None)
    def __call__(self, request, configuration):
        self.call_count += 1
        if self.stage == 'FAIL_STAGE':
            raise ValueError('synthetic provider failure')
        text = json.loads(request)['input'][1]['content'][0]['text']
        contract_text, evidence_text = text.split('\\n\\nUNTRUSTED_EVIDENCE\\n', 1)
        answer = json.loads(contract_text.removeprefix('RESPONSE_SCHEMA\\n'))
        evidence = json.loads(evidence_text)
        for key in ('supporting', 'opposing', 'unknown'):
            if key in answer:
                answer[key]['claim'] = '明确标记的离线经营/市场证据解释'
        if self.stage == 'problem':
            answer['problem_present'] = True
            answer['business_question'] = (evidence['control'].get('business_question') or
                '同规格商品的报价是否会改变保持条件与商品检查的取舍？')
        elif self.stage == 'selection':
            answer['choice'] = 'NEW_RESEARCH'
            answer['research_type'] = 'offer_comparison'
            answer['expected_answer'] = '同规格同包装普通买家报价的可比性及限制'
            answer['evidence_requirement'] = '精确商品、窗口、来源、报价资格和反向证据'
            answer['reuse_request_ref'] = None
        elif self.stage == 'research':
            answer['findings'] = '合成研究发现：展示价差存在，但优惠资格未核实。'
            answer['limitations'] = ['合成来源仅用于接口测试，不能作经营证据']
        elif self.stage == 'feedback':
            answer['direction'] = 'DEFER'
            answer['explanation'] = '合成市场价差增加核查动机，但未知资格使投入判断暂缓。'
        self.transport_diagnostic = dict(phase='COMPLETE', http_status=200)
        return json.dumps(answer, ensure_ascii=False, separators=(',', ':')).encode('utf8')
def create_provider(stage, request):
    return Provider(stage)
'''


class NativeResearchCase:
    def __init__(self, pds_root):
        self.native = importlib.import_module('src.product_intelligence.native_market_flow')
        contracts = importlib.import_module('src.product_intelligence.contracts')
        observation = importlib.import_module('src.product_intelligence.daily_forward_observation')
        trigger = importlib.import_module('src.product_intelligence.operating_review_trigger')
        for module in (self.native, contracts, observation, trigger):
            if not Path(module.__file__).resolve().is_relative_to(pds_root):
                raise ValueError('Unexpected PDS module origin in integration setup')
        if self.native.ROOT != pds_root:
            raise ValueError('PDS production root does not match the pinned integration checkout')
        self.strict_json_load = contracts.strict_json_load
        self.canonical_bytes = contracts.canonical_bytes
        self.seal = observation.seal
        self.immutable_write = observation.immutable_write
        self.schema = trigger.SCHEMA

    def dependency(self, tmp_path, *, fail='no_stage'):
        path = tmp_path / 'dependency.py'
        path.write_text(DEPENDENCY.replace('FAIL_STAGE', fail), encoding='utf8')
        return path

    def source(self, tmp_path):
        identity = dict(product_id='SYNTHETIC-PRODUCT',
                        offer_key='TEST|US|seller_sku|SYNTHETIC-SKU',
                        sku='SYNTHETIC-SKU', asin='B000000099', provider_sid='TEST-SHOP')
        raw = tmp_path / 'raw.json'
        self.immutable_write(raw, dict(origin='SYNTHETIC_TEST', stock=100, sales=20))
        facts = dict(schema=self.schema, identity=identity,
            business_context=dict(primary_objective='验证有效成交与经营承接', operating_mode='GROWTH'),
            observations=dict(window=WINDOW, sales=20, units=2),
            decision_conditions=dict(profit_floor=None, incremental_fees=None),
            human_feedback=dict(scope='OFFLINE_TEST_ONLY'), limitations=['SYNTHETIC_TEST'],
            source_refs=[self.native.reference(raw)], data_date=DATE, valid_through='2026-10-16',
            review_after=None, blocked_reasons=[])
        control = dict(schema='pds-market-evaluation-task/v1', identity=identity, issue_state='PENDING',
            task_kind='USER_AUTHORIZED_EVALUATION', authorized_by='HUMAN', assessment_authorized=True,
            objective=facts['business_context']['primary_objective'], valid_through='2026-10-16',
            market_window=WINDOW, origin='SYNTHETIC_TEST', source_refs=[self.native.reference(raw)])
        self.immutable_write(tmp_path / 'facts.json', self.seal(facts))
        self.immutable_write(tmp_path / 'control.json', self.seal(control))

    def run(self, tmp_path, dependency):
        return self.native.run(tmp_path / 'facts.json', tmp_path / 'control.json', DATE,
                               tmp_path / 'flow', MARKET,
                               offline_dependency_path=dependency, allow_synthetic=True)

    def evidence(self, tmp_path, result):
        binding = self.native.read(result['return_binding_ref'])
        task = self.native.read(binding['task_ref'])
        raw = tmp_path / 'market-raw.json'
        self.immutable_write(raw, dict(origin='SYNTHETIC_TEST', same_spec=True, observed_item_price='10.00'))
        packet = self.seal(dict(schema='market-native-research-evidence/v1', task_ref=binding['task_ref'],
            identity=task['identity'], question=task['question'], expected_answer=task['expected_answer'],
            window=WINDOW, origin='SYNTHETIC_TEST', source_refs=[self.native.reference(raw)],
            methods=[self.native.reference(__file__)], facts=dict(observed_price='10.00'),
            qualification='SOURCE_BOUND_FOR_THIS_RESEARCH', data_date=DATE, valid_through='2026-10-16',
            limitations=['SYNTHETIC_TEST'], non_executable=True))
        self.immutable_write(tmp_path / 'market-evidence.json', packet)
        return tmp_path / 'flow/return.json', tmp_path / 'market-evidence.json'

    def tamper(self, path, **changes):
        value = self.strict_json_load(path)
        value = {key: item for key, item in value.items() if key != 'record_ref'}
        value.update(changes)
        path.write_bytes(self.canonical_bytes(self.seal(value)))

    @staticmethod
    def files(path):
        return {str(item): item.read_bytes() for item in path.rglob('*') if item.is_file()}
