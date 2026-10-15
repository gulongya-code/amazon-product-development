"""Qualify exact 08 offers from native captures, preserving coupon uncertainty."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from html.parser import HTMLParser
from pathlib import Path
import re

from amazon_product_intelligence import offer08_probe as probe
from amazon_product_intelligence import buyer_context_probe as buyer
from amazon_product_intelligence.yps_competitive_difference import ref, save, section
from amazon_product_intelligence.pds_market_readback import read_verified

IDENTITY=dict(sid=9226,sku='08-P6IV-FTMZ',asin=probe.OWN)


class CurrencyFields(HTMLParser):
    def __init__(self):super().__init__();self.values=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='input' and a.get('name')=='items[0.base][customerVisiblePrice][currencyCode]':
            self.values.append(a.get('value'))


def qualify(item):
    original=item['observation'];o=dict(original)
    # The accordion labels the primary offer Buy New, ahead of its price.
    # Never scan for the lowest dollar value or normalize a Used heading.
    if o.get('buybox_text','').startswith('Buy New\n'):
        o['buybox_text']=o['buybox_text'][len('Buy New\n'):]
    htmls=[r for r in o.get('artifacts',[]) if Path(r['path']).name=='page.html']
    currency_basis='ORIGINAL_CAPTURE'
    if len(htmls)==1:
        r=htmls[0]
        if ref(r['path'])['sha256']!=r['sha256']:raise ValueError('Page changed')
        fields=CurrencyFields();fields.feed(Path(r['path']).read_text(encoding='utf8'))
        if fields.values and set(fields.values)=={'USD'}:
            o['offer_currency_code']='USD';currency_basis='ALL_RETAINED_PURCHASE_CURRENCY_FIELDS_EXPLICIT_USD'
    q=buyer.classify(o);offer=q['offer_observation']
    title=o.get('title','');lower=title.lower()
    spec=dict(size=bool(re.search(r'(?<!\d)3/8',lower)),material=bool(re.search(r'304\s+(?:stainless steel|ss)',lower)),
        ends=bool(re.search(r'(?:female\s*[x×]\s*male|male\s*[x×]\s*female)',lower)),
        thread='npt' in lower,mini='mini' in lower,ball_valve='ball valve' in lower,
        pack=bool(re.search(r'\b2\s*pack\b',lower)))
    compatible=all(spec.values())
    eligible=bool(not q['reasons'] and compatible and offer['condition']=='NEW_EXPLICIT_OFFER_ROW'
        and offer['currency_code']=='USD' and offer['displayed_price_amount'])
    promo=[p for p in item['promotion_observations'] if 'promoPrice' in p['selector'] or 'coupon' in p['selector'].lower()]
    # Scope is the selected product's promotion widget, never variant swatches.
    texts=' '.join(p['text'] for p in promo)
    rates=re.findall(r'Apply\s+(\d+(?:\.\d+)?)%\s+coupon',texts,re.I)
    rate=Decimal(rates[0])/100 if len(rates)==1 and Decimal(rates[0])<100 else None
    price=Decimal(offer['displayed_price_amount']) if eligible else None
    conditional=str(price*(1-rate)) if price is not None and rate is not None else None
    try:bullets=section(o.get('body_text',''),'About this item\n','› See more product details',1000)
    except ValueError:bullets=None
    return dict(asin=item['asin'],url=o.get('final_url'),captured_at_utc=o.get('captured_at_utc'),
        title=title,spec_checks=spec,same_spec_claims=compatible,
        qualification='CURRENT_NEW_ITEM_PRICE_OBSERVED' if eligible else 'NOT_QUALIFIED_FOR_PRICE_COMPARISON',
        failure_reasons=q['reasons'],source_claims_only=True,bullet_claims=bullets,
        item_price_usd=str(price) if price is not None else None,currency_basis=currency_basis,
        per_valve_price_unrounded_usd=str(price/2) if price is not None else None,
        pack_count_claim=2 if compatible else None,condition=offer['condition'],seller_id=offer.get('seller_id'),
        seller=offer['seller_display_name'],fulfillment=offer['fulfillment_display_name'],
        availability=offer['availability_text'],cart_button=offer['add_to_cart_button'],
        promotion_widgets=promo,coupon_display_status='PERCENT_COUPON_DISPLAYED' if rate is not None else 'NO_COUPON_OBSERVED_IN_CAPTURED_WIDGETS_NOT_PROOF_OF_ABSENCE',
        advertised_coupon_rate=str(rate) if rate is not None else None,
        coupon_eligibility='UNKNOWN_NOT_SIGNED_IN_NOT_CLAIMED_NOT_CHECKED_OUT',
        actually_available_discounted_price=None,conditional_coupon_item_price_unrounded_usd=conditional,
        coupon_math_basis='DISPLAYED_PERCENT_ONLY_CONDITIONAL_NOT_REDEEMED_NOT_ROUNDING_VERIFIED',
        regular_price_history='UNKNOWN_CURRENT_DISPLAY_IS_NOT_HISTORICAL_REGULAR_PRICE',
        shipping_usd=None,landed_total=None,b2b_quote='UNKNOWN_GUEST_SESSION',
        customer_quality_warning=('Frequently returned item' in o.get('body_text','')),
        warning_scope='PAGE_DISPLAY_ONLY_NOT_VERIFIED_CHILD_RETURN_RATE',
        visible_offer=q)


def build():
    sources=[];products=[]
    for name in ('own_live','competitor_live','competitor2_live'):
        path=probe.OUT/name/'result.json';raw=json.loads(path.read_text(encoding='utf8'))
        if raw['cart_actions']!=0 or raw['purchases']!=0 or raw['automatic_scheduling'] is not False:
            raise ValueError('Forbidden action in capture')
        sources.append(ref(path));sources.append(raw['own_catalog_ref'])
        for method in raw['method_refs']:
            if ref(method['path'])['sha256']==method['sha256']:sources.append(method)
            else:
                copies=[p for p in probe.OUT.glob('capture_method_v*.py') if ref(p)['sha256']==method['sha256']]
                if len(copies)!=1:raise ValueError('Capture method version missing')
                sources.append(ref(copies[0]))
        for item in raw['observations']:
            o=item['observation']
            sources.extend(o.get('artifacts',[]));sources.extend(o.get('offer_details',{}).get('artifacts',[]))
            products.append(qualify(item))
    receipts=[];search=[];details=[]
    for p in sorted(probe.OUT.glob('api_*.receipt.json')):
        r=json.loads(p.read_text(encoding='utf8'));receipts.append(r);sources.append(ref(p))
        if r.get('raw_ref'):
            data=read_verified(r['raw_ref']['path'],r['raw_ref']['sha256']);sources.append(r['raw_ref'])
            if r['endpoint']=='ProductSearchFromName':search.extend(data['Data'])
            else:details.append(dict(asin=r['params']['asin'],data=data['Data']))
    consumed=sum(r['request_consumed'] for r in receipts if isinstance(r['request_consumed'],int))
    if any(r['status']!='COMPLETE' for r in receipts) or consumed>8:raise ValueError('Incomplete or over-budget API ledger')
    for r in sources:
        if ref(r['path'])['sha256']!=r['sha256']:raise ValueError('Source changed')
    own_catalog=probe.own_asins()
    if len(products)!=3 or products[0]['asin']!=probe.OWN or any(p['asin'] in own_catalog for p in products[1:]):
        raise ValueError('Product identity mismatch')
    qualified=[p for p in products[1:] if p['qualification']=='CURRENT_NEW_ITEM_PRICE_OBSERVED']
    comparisons=[]
    if products[0]['item_price_usd'] is not None:
        price=Decimal(products[0]['item_price_usd'])
        for p in qualified:
            other=Decimal(p['item_price_usd'])
            comparisons.append(dict(asin=p['asin'],own_minus_competitor_item_price_usd=str(price-other),
                own_premium_to_competitor_percent=str(((price/other)-1)*100),
                own_hypothetical_5pct_coupon_price=str(price*Decimal('.95')),
                own_5pct_price_minus_competitor_undiscounted=str(price*Decimal('.95')-other),
                basis='ITEM_PRICE_ONLY_NO_SHIPPING_NO_CAUSAL_OR_MARKET_WIDE_INFERENCE'))
    return dict(schema='08-market-offer-evidence/v1',identity=IDENTITY,generated_at_utc=datetime.now(timezone.utc).isoformat(),
        source_refs=sources,method_refs=[ref(__file__),ref(buyer.__file__)],
        facts=dict(E1=products,E2=dict(search_rows=len(search),unique_search_asins=len({r['Asin'] for r in search}),
            own_catalog_exclusions=sorted({r['Asin'] for r in search if r['Asin'] in own_catalog}),
            inspected_details=details,qualified_external_count=len(qualified),exhaustive=False),E3=comparisons,
            E4=dict(unknown=['Logged-in ordinary buyer coupon eligibility and stacking',
                'Single-pack freight, taxes, checkout total and coupon rounding',
                'Competitor B2B and volume tiers','Regular-price history and representative market distribution',
                'Current 08 profit, inventory permission, causal effect of discounts on conversion']),
            E5=dict(sorftime_requests_consumed=consumed,last_reported_request_left=max(receipts,key=lambda r:r['finished_at_utc'])['request_left'],receipts=receipts)),
        cart_actions=0,purchases=0,automatic_scheduling=False,non_executable=True,sp043b_status=buyer.SP_STATUS)


def readback(receipt,digest,output):
    r=read_verified(receipt,digest);m=read_verified(r['market_ref']['path'],r['market_ref']['sha256'])
    e=read_verified(r['evidence_ref']['path'],r['evidence_ref']['sha256'])
    if (r['kind']!='PDS_08_MARKET_REVIEW' or r['status']!='ANALYSIS_COMPLETED' or r['origin']!='PROJECT_PDS_LLM'
        or r['provider_calls']!=1 or r['transport']['phase']!='COMPLETE' or r['transport']['http_status']!=200
        or r['identity']!=IDENTITY or m['identity']!=IDENTITY or e['identity']!=IDENTITY
        or r['input_ref']!=e['record_ref'] or e['market_ref']!=r['market_ref']
        or r['non_executable'] is not True or r['constraints']['automatic_scheduling'] is not False
        or r['constraints']['execution_authorized'] is not False or r['constraints']['sp043b_status']!=buyer.SP_STATUS):
        raise ValueError('PDS receipt not qualified')
    for f in e['source_refs']:
        if ref(f['path'])['sha256']!=f['sha256']:raise ValueError('PDS source changed')
    value=dict(status='PDS_ANALYSIS_READ_BACK',receipt_ref=ref(receipt),market_ref=r['market_ref'],
        actual_pds_conclusion=r['proposal'],business_value_accepted=False,non_executable=True,sp043b_status=buyer.SP_STATUS)
    save(output,value);return value


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['build','readback']);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--receipt',type=Path);p.add_argument('--receipt-sha256');a=p.parse_args()
    if a.action=='build':save(a.output,build());print('EVIDENCE_PREPARED')
    else:print(readback(a.receipt,a.receipt_sha256,a.output)['status'])


if __name__=='__main__':main()
