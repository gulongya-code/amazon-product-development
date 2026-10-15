from copy import deepcopy
import json
import pytest
from amazon_product_intelligence.offer08_evidence import qualify, CurrencyFields
from amazon_product_intelligence import offer08_probe as probe


def item():
    asin='B0FL7CM2FL'
    o=dict(requested_asin=asin,selected_asin=asin,final_url=f'https://www.amazon.com/dp/{asin}',
        http_status=200,error=None,body_text='Synthetic page',delivery_text='Los Angeles 90001',
        account_text='Hello, sign in',isolated_guest_context=True,
        title='2 Pack 3/8 Mini Ball Valve 304 Stainless Steel NPT Female x Male',
        buybox_text='Buy New\n$14.89\nShips from\nAmazon\nSold by\nOwn seller\nQuantity:1\nUsed - Like New\n$9.00',
        offer_currency_code='USD',seller_id='SELLER',availability_text='In Stock',artifacts=[])
    o['offer_details']=dict(http_status=200,error=None,final_url=o['final_url'],delivery_text=o['delivery_text'],account_text=o['account_text'],body_text='Offer New',
        rows=[dict(selector='#aod-pinned-offer',text='New\n$14.89',links=[dict(href=f'/gp/aag?asin={asin}&seller=SELLER')])])
    return dict(asin=asin,observation=o,promotion_observations=[dict(selector='#promoPriceBlockMessage_feature_div',text='Apply 5% coupon Terms')])


def test_new_price_and_coupon_are_separate_from_used_and_eligibility():
    source=item();before=deepcopy(source);r=qualify(source)
    assert r['item_price_usd']=='14.89'
    assert r['conditional_coupon_item_price_unrounded_usd']=='14.1455'
    assert r['actually_available_discounted_price'] is None and r['shipping_usd'] is None
    assert source==before


@pytest.mark.parametrize('key,value',[
    ('delivery_text','Macao'),('selected_asin','B000000000'),('error','PAGE_OR_LOCATION_TIMEOUT'),
    ('offer_currency_code','HKD'),('buybox_text','Used - Like New\n$9.00'),
    ('title','2 Pack 1/2 Mini Ball Valve 304 Stainless Steel NPT Female x Male'),
    ('title','2 Pack 3/8 Mini Ball Valve Brass NPT Female x Male'),
    ('title','4 Pack 3/8 Mini Ball Valve 304 Stainless Steel NPT Female x Male')])
def test_unqualified_price_is_unknown(key,value):
    source=item();source['observation'][key]=value
    assert qualify(source)['item_price_usd'] is None


def test_other_variant_discount_is_not_selected_coupon():
    source=item();source['promotion_observations']=[]
    source['observation']['body_text']='Other size 10% off'
    assert qualify(source)['advertised_coupon_rate'] is None


def test_conflicting_currency_fields_not_unified():
    p=CurrencyFields();p.feed('<input name="items[0.base][customerVisiblePrice][currencyCode]" value="USD"><input name="items[0.base][customerVisiblePrice][currencyCode]" value="HKD">')
    assert set(p.values)!={'USD'}


def test_budget_cap_blocks_before_network(tmp_path,monkeypatch):
    monkeypatch.setattr(probe,'OUT',tmp_path)
    (tmp_path/'api_prior.slot.json').write_text(json.dumps(dict(reserved_requests=8)))
    monkeypatch.setattr(probe.subprocess,'run',lambda *a,**k:pytest.fail('Network attempted'))
    with pytest.raises(ValueError,match='cap'):probe.call('ProductRequest',{'asin':'B0GCHJCFJW'},'new',1)


def test_used_slot_blocks_before_network(tmp_path,monkeypatch):
    monkeypatch.setattr(probe,'OUT',tmp_path)
    (tmp_path/'api_same.slot.json').write_text(json.dumps(dict(reserved_requests=1)))
    monkeypatch.setattr(probe.subprocess,'run',lambda *a,**k:pytest.fail('Network attempted'))
    with pytest.raises(FileExistsError):probe.call('ProductRequest',{'asin':'B0GCHJCFJW'},'same',1)
