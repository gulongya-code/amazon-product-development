"""Explicit 08 market sampling and guest offer capture; no operations or schedule."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess

from amazon_product_intelligence import buyer_context_probe as browser_probe
from amazon_product_intelligence.yps_competitive_difference import ref, save

OUT=Path('C:/amazon_private/08_market_offer_20261013')
OWN='B0FL7CM2FL'
CATALOG=Path('C:/Users/Administrator/daily_data_auto_entry/input/mapping/All_Listings_Report.txt')
CLI=Path.home()/'AppData/Roaming/npm/node_modules/sorftime-cli/dist/index.js'
QUERIES=['3/8 inch 304 stainless steel mini ball valve female male NPT 2 pack',
         '3/8 stainless steel mini ball valve 2pcs female male']
MAX_REQUESTS=8


def call(endpoint, params, name, cost):
    """Reserve before calling, never retry a used slot or print credentials."""
    if endpoint not in ('ProductSearchFromName','ProductRequest'):raise ValueError('Read-only endpoints only')
    slots=list(OUT.glob('api_*.slot.json'))
    used=sum(json.loads(p.read_text(encoding='utf8'))['reserved_requests'] for p in slots)
    if used+cost>MAX_REQUESTS:raise ValueError('Request cap reached')
    save(OUT/f'api_{name}.slot.json',dict(endpoint=endpoint,params=params,reserved_requests=cost,
        started_at_utc=datetime.now(timezone.utc).isoformat(),retries=0))
    record=dict(endpoint=endpoint,params=params,status='FAILED',request_consumed=None,request_left=None)
    try:
        completed=subprocess.run(['node',str(CLI),'api',endpoint,json.dumps(params),'--domain','1'],
            capture_output=True,timeout=90,encoding='utf8',check=False)
        if completed.returncode!=0:raise ValueError('CLI unsuccessful')
        raw=json.loads(completed.stdout)
        save(OUT/f'api_{name}.json',raw)
        record.update(code=raw.get('Code',raw.get('code')),request_consumed=raw.get('RequestConsumed'),
            request_left=raw.get('RequestLeft'),raw_ref=ref(OUT/f'api_{name}.json'))
        if record['code']!=0:raise ValueError('Provider unsuccessful')
        record['status']='COMPLETE'
    except Exception as exc:record['failure_code']=type(exc).__name__
    record['finished_at_utc']=datetime.now(timezone.utc).isoformat()
    save(OUT/f'api_{name}.receipt.json',record)
    print(json.dumps(record,ensure_ascii=False),flush=True)
    return record


def own_asins():
    with CATALOG.open(encoding='utf-8-sig',newline='') as f:
        return set(re.findall(r'\bB0[A-Z0-9]{8}\b',f.read()))


def search(index):
    return call('ProductSearchFromName',dict(Name=QUERIES[index],PageIndex=1),f'search_{index}',2)


def details(asin):
    if not re.fullmatch(r'B0[A-Z0-9]{8}',asin) or asin in own_asins():raise ValueError('External ASIN required')
    return call('ProductRequest',dict(asin=asin),asin,1)


def capture(asins, name):
    if not asins or len(asins)>5 or len(asins)!=len(set(asins)):raise ValueError('At most five explicit products')
    if any(not re.fullmatch(r'B0[A-Z0-9]{8}',a) for a in asins):raise ValueError('Invalid ASIN')
    if any(a!=OWN and a in own_asins() for a in asins):raise ValueError('Own-catalog competitor excluded')
    if not re.fullmatch(r'[a-z0-9_]+',name):raise ValueError('Local output name required')
    discovered=set()
    for path in OUT.glob('api_B0*.json'):
        data=json.loads(path.read_text(encoding='utf8')).get('Data',{})
        if isinstance(data,dict):discovered.update(data.get('VariationASIN') or [])
    for a in asins:
        if a!=OWN and not (OUT/f'api_{a}.json').is_file() and a not in discovered:
            raise ValueError('Previously inspected detail or explicit child required')
    directory=OUT/name
    directory.mkdir(exist_ok=False)
    from playwright.sync_api import sync_playwright, TimeoutError
    result=dict(schema='08-guest-offer-capture/v1',asin=OWN,postcode='90001',
        buyer='FRESH_SIGNED_OUT_GUEST_NOT_VERIFIED_ACCOUNT_ELIGIBILITY',observations=[],
        cart_actions=0,purchases=0,automatic_scheduling=False,sp043b_status=browser_probe.SP_STATUS,
        method_refs=[ref(__file__),ref(browser_probe.__file__)],own_catalog_ref=ref(CATALOG))
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(channel='msedge',headless=True)
        try:
            for asin in asins:
                d=directory/asin;d.mkdir()
                context=browser.new_context(locale='en-US',timezone_id='America/Los_Angeles')
                try:
                    page=context.new_page();context.set_default_timeout(5000)
                    o=browser_probe.collect(page,asin,d,timeout_error=TimeoutError)
                    # Extract only own product areas; no coupon claiming or checkout.
                    promotions=[]
                    if not browser_probe.classify(o)['reasons']:
                        for selector in ('#promoPriceBlockMessage_feature_div','#couponFeature',
                            '#vpcButton_feature_div','#promoPriceBlockMessage', '#dealBadge_feature_div',
                            '#corePriceDisplay_desktop_feature_div','#quantityDiscountTable_feature_div'):
                            value=browser_probe._visible_text(page,selector)
                            if value:promotions.append(dict(selector=selector,text=value))
                        o['offer_details']=browser_probe.collect_details(page,asin,d,timeout_error=TimeoutError)
                    result['observations'].append(dict(asin=asin,observation=o,
                        qualification=browser_probe.classify(o),promotion_observations=promotions,
                        coupon_application='NOT_ATTEMPTED',discount_eligibility='UNKNOWN',
                        normal_price_history='UNKNOWN_SNAPSHOT_IS_NOT_REGULAR_PRICE_HISTORY',
                        business_tier_access='UNAVAILABLE_IN_GUEST_SESSION'))
                    print(asin+': '+result['observations'][-1]['qualification']['status'],flush=True)
                finally:context.close()
        finally:browser.close()
    result['finished_at_utc']=datetime.now(timezone.utc).isoformat();save(directory/'result.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    s=sub.add_parser('search');s.add_argument('--index',type=int,choices=[0,1],required=True)
    d=sub.add_parser('detail');d.add_argument('--asin',required=True)
    c=sub.add_parser('capture');c.add_argument('--asins',nargs='+',required=True);c.add_argument('--name',required=True)
    a=p.parse_args()
    if a.action=='search':search(a.index)
    elif a.action=='detail':details(a.asin)
    else:capture(a.asins,a.name)


if __name__=='__main__':main()
