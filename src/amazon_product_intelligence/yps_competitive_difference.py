"""Explicit file-only YPS competitive evidence extraction and PDS readback.

No source calls. Retained page claims and displayed reviews are not lab evidence.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re

from amazon_product_intelligence.buyer_context_probe import ASINS, SP_STATUS, classify
from amazon_product_intelligence.pds_market_readback import read_verified

BASE = Path('C:/amazon_private/yps_market_evidence_preparation_20261013/'
            '01a132e0-df6c-7581-88d4-e436e1cb0700')
SOURCE = BASE/'offer_completion_20261013/live_final/result.json'
# Full digest pinned to the already-consumed market capture.
SOURCE_SHA = '9e21091635246dacc898699a8e6ae91a56ea355a90fda1434474c283a36bf89c'
QUALIFICATION = BASE/'round2/YPS_第二轮核验依据.json'
QUALIFICATION_SHA = '41d2313a6a0a8b39de4cdb2af79efed94d352e6ce57f6110756aabdf91c20939'


def ref(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=sha256(path.read_bytes()).hexdigest())


def save(path, value):
    with Path(path).open('x', encoding='utf8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


class Reviews(HTMLParser):
    """Extract scoped Amazon review hooks; deliberately omit reviewer profiles."""
    HOOKS = {'reviewTitle':'title', 'review-title':'title', 'review-date':'date',
             'reviewText':'text', 'review-body':'text', 'format-strip':'variant',
             'review-star-rating':'rating', 'avp-badge':'verified_purchase',
             'vine-review-badge':'vine'}
    VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[]; self.current=None; self.rows=[]; self.depth=None

    def handle_starttag(self, tag, attrs):
        a=dict(attrs); hook=a.get('data-hook')
        if hook=='review':
            if self.current is not None: raise ValueError('Nested review')
            self.current={'review_id':a.get('id','UNKNOWN')}; self.depth=len(self.stack)
        key=self.HOOKS.get(hook)
        if self.current is not None and key:
            if key in self.current:key=None
            else:self.current[key]=[]
        if tag not in self.VOID:self.stack.append((tag,key))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag,attrs)
        if tag not in self.VOID:self.handle_endtag(tag)

    def handle_data(self, data):
        if self.current is not None:
            keys={key for _,key in self.stack[self.depth:] if key}
            for key in keys:self.current[key].append(data)

    def handle_endtag(self, tag):
        matches=[i for i,(name,_) in enumerate(self.stack) if name==tag]
        if not matches:return
        index=matches[-1];del self.stack[index:]
        if self.current is not None and index<=self.depth:
            row={k:re.sub(r'\s+',' ',' '.join(v)).strip() if isinstance(v,list) else v
                 for k,v in self.current.items()}
            if not row.get('text') or not row.get('date'):raise ValueError('Incomplete review')
            row['variant_scope']=variant_scope(row.get('variant',''))
            row['claim_status']='INDIVIDUAL_REVIEW_NOT_VERIFIED_PRODUCT_PERFORMANCE'
            self.rows.append(row);self.current=None;self.depth=None


def variant_scope(text):
    size=re.search(r'Size:\s*(.*?)\s*(?=Style:|Color:|$)',text,re.I)
    if not size:return 'UNKNOWN_VARIANT'
    if re.sub(r'\s+',' ',size.group(1)).strip().lower()!='1 inch':return 'OTHER_SIZE'
    pack=re.search(r'Style:\s*Pack of\s*(\d+)',text,re.I)
    if not pack:return 'SIZE_MATCH_PACK_UNSTATED'
    return 'EXACT_SIZE_PACK_CLAIM' if pack.group(1)=='2' else 'OTHER_PACK'


def section(text, start, end, offset=0):
    a=text.find(start,offset);b=text.find(end,a+len(start)) if a>=0 else -1
    if a<0 or b<0:raise ValueError('Required page section absent')
    return text[a+len(start):b].strip()


def extract():
    source=read_verified(SOURCE,SOURCE_SHA)
    old=read_verified(QUALIFICATION,QUALIFICATION_SHA)
    if (source['sp043b_status']!=SP_STATUS or source['cart_actions']!=0
            or source['purchases']!=0 or source['automatic_scheduling'] is not False
            or tuple(x['asin'] for x in source['observations'])!=ASINS):
        raise ValueError('Capture scope changed')
    sources=[ref(SOURCE),ref(QUALIFICATION)]
    for row in old['qualification']:
        read_verified(row['source_file'],row['raw_sha256'])
        sources.append(dict(path=row['source_file'],sha256=row['raw_sha256']))
    own=Path(old['qualification'][0]['own_catalog_source'])
    if ref(own)['sha256']!=old['qualification'][0]['own_catalog_sha256']:
        raise ValueError('Own catalog changed')
    sources.append(ref(own))
    direct=[r for r in old['qualification'] if r['decision']=='DIRECT_COMPARABLE_AT_LISTING_CLAIM_LEVEL'
            and not r['own_catalog_match']]
    if [r['asin'] for r in direct]!=[ASINS[1]] or ASINS[1] in own.read_text(encoding='utf-8-sig'):
        raise ValueError('Direct competitor scope differs')
    products=[]
    for item in source['observations']:
        o=item['observation']
        if classify(o)['reasons']:raise ValueError('Retained buyer context failed')
        for artifact in [item['snapshot_ref'],*o['artifacts']]:
            if ref(artifact['path'])['sha256']!=artifact['sha256']:raise ValueError('Artifact changed')
            sources.append(artifact)
        html=next(r for r in o['artifacts'] if Path(r['path']).name=='page.html')
        parser=Reviews();parser.feed(Path(html['path']).read_text(encoding='utf8'));parser.close()
        if parser.current is not None or not parser.rows:raise ValueError('Review extraction incomplete')
        body=o['body_text']
        bullets=section(body,'About this item\n','› See more product details',1000)
        ratings=section(body,'Customer reviews\n','How customer reviews and ratings work')
        products.append(dict(asin=item['asin'],captured_at_utc=o['captured_at_utc'],url=o['final_url'],
            title=o['title'],bullet_claims=bullets.splitlines(),
            ratings_display=ratings,ratings_scope='PAGE_AGGREGATE_NOT_CHILD_EXCLUSIVE_NOT_WRITTEN_REVIEW_COUNT',
            displayed_reviews=parser.rows,review_scope='DISPLAYED_TOP_REVIEWS_ONLY_NON_RANDOM_INCOMPLETE',
            partial_offer=item['qualification']['offer_observation']))
    prices=[p['partial_offer'] for p in products]
    difference=(str(Decimal(prices[0]['displayed_price_amount'])-Decimal(prices[1]['displayed_price_amount']))
                if all(p['currency_code']=='USD' for p in prices) else None)
    identity_keys=('product_id','offer_key','shop_id','marketplace','sku','asin')
    return dict(schema='yps-competitive-difference/v1',
        identity={k:old['identity'][k] for k in identity_keys},
        provider_identity={k:v for k,v in old['identity'].items() if k not in identity_keys},
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
        evidence_timing='REANALYSIS_OF_RETAINED_2026_10_13_CAPTURE_NOT_A_NEW_LIVE_CHECK',
        source_refs=sources,method_ref=ref(__file__),
        facts=dict(E1=dict(products=products,authority='PAGE_CLAIMS_AND_REVIEW_OPINIONS_ONLY'),
            E2=dict(prior_search=old['search'],direct_samples=direct,external_direct_count=len(direct),
                excluded_or_alternative=[r for r in old['qualification'] if r not in direct],
                exhaustive=False,new_search=False),
            E3=dict(yps_minus_dernord_item_price_usd=difference,landed_price_difference=None,
                basis='RETAINED_EXPLICIT_NEW_OFFER_ITEM_PRICES_ONLY',shipping_followup=False),
            E4=dict(unknown=['Exact-child review distribution and verified defect rates',
                'Physical bore dimensions, flow coefficients, certified performance and serviceability',
                'Conversion impact of page text, review volume, price or product fit',
                'Representative competitor coverage beyond one direct sample',
                'Historical page versions and applicability during the profit/ad windows',
                'Single-pack freight, tax, applicable discounts and checkout total']),
            E5=dict(pack_conflict=direct[0]['spec_fields']['conflicting_field'],
                same_spec_qualification='AT_LISTING_CLAIM_LEVEL_NOT_PHYSICAL_VERIFICATION')),
        new_source_calls=0,sorftime_requests_consumed=0,market_model_calls=0,
        non_executable=True,automatic_scheduling=False,sp043b_status=SP_STATUS)


def readback(receipt, digest, packet, output):
    review=read_verified(receipt,digest)
    market=read_verified(packet,review['market_result_ref']['sha256'])
    evidence=read_verified(review['evidence_ref']['path'],review['evidence_ref']['sha256'])
    if (Path(review['market_result_ref']['path']).resolve()!=Path(packet).resolve()
            or review['kind']!='PDS_YPS_COMPETITIVE_REVIEW' or review['status']!='ANALYSIS_COMPLETED'
            or review['origin']!='PROJECT_PDS_LLM' or review['provider_calls']!=1
            or review['transport']['phase']!='COMPLETE' or review['transport']['http_status']!=200
            or review['input_ref']!=evidence['record_ref']
            or evidence['market_result_ref']!=review['market_result_ref']
            or review['identity']!=market['identity'] or evidence['identity']!=market['identity']
            or set(review['proposal']['consumed_evidence_ids'])!={'E1','E2','E3','E4','E5','P1','P2'}
            or review['proposal']['profit_check_status']!='CLOSED'
            or review['non_executable'] is not True or review['constraints']['automatic_scheduling'] is not False
            or review['constraints']['execution_authorized'] is not False
            or review['constraints']['sp043b_status']!=SP_STATUS or market['sp043b_status']!=SP_STATUS):
        raise ValueError('PDS receipt not qualified')
    for r in evidence['source_refs']:
        if ref(r['path'])['sha256']!=r['sha256']:raise ValueError('PDS source changed')
    value=dict(status='PDS_ANALYSIS_READ_BACK',market_result_ref=ref(packet),receipt_ref=ref(receipt),
        actual_pds_analysis=review['proposal'],analytical_consumption_confirmed=True,
        business_value_accepted=False,non_executable=True,sp043b_status=SP_STATUS)
    save(output,value);return value


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['extract','readback'])
    p.add_argument('--output',type=Path,required=True);p.add_argument('--receipt',type=Path)
    p.add_argument('--receipt-sha256');p.add_argument('--packet',type=Path);a=p.parse_args()
    if a.action=='extract':save(a.output,extract());print('RETAINED_COMPETITIVE_EVIDENCE_EXTRACTED')
    else:print(readback(a.receipt,a.receipt_sha256,a.packet,a.output)['status'])


if __name__=='__main__':main()
