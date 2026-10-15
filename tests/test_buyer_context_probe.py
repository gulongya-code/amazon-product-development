"""Synthetic page observations test eligibility, never live market facts."""
from copy import deepcopy
from pathlib import Path

import pytest

from amazon_product_intelligence.buyer_context_probe import classify, run


@pytest.fixture
def observation():
    return dict(requested_asin='B0H5BWL6J2', final_url='https://www.amazon.com/dp/B0H5BWL6J2',
        http_status=200, selected_asin='B0H5BWL6J2', body_text='Synthetic product page',
        delivery_text='Los Angeles 90001', account_text='Hello, sign in',
        isolated_guest_context=True, error=None)


def test_matched_context_is_not_a_qualified_offer_or_purchase(observation):
    value = classify(observation)
    assert value['status'] == 'CONTEXT_OBSERVED_OFFER_UNVERIFIED'
    assert value['business_evidence_eligible'] is False
    assert value['purchasable'] == 'UNKNOWN'
    assert value['comparable_total'] is None
    assert value['observed_buyer'] == 'ISOLATED_SIGNED_OUT_GUEST'


@pytest.mark.parametrize(('key', 'value', 'reason'), [
    ('http_status', 503, 'HTTP_SUCCESS_NOT_OBSERVED'),
    ('http_status', None, 'HTTP_SUCCESS_NOT_OBSERVED'),
    ('body_text', 'Enter the characters you see', 'CHALLENGE_PAGE'),
    ('body_text', 'Verify you are human', 'CHALLENGE_PAGE'),
    ('final_url', 'https://www.amazon.com/ap/signin', 'PRODUCT_URL_NOT_MATCHED'),
    ('final_url', 'https://example.com/dp/B0H5BWL6J2', 'PRODUCT_URL_NOT_MATCHED'),
    ('selected_asin', 'B07XFCSRL5', 'SELECTED_ASIN_NOT_MATCHED'),
    ('selected_asin', None, 'SELECTED_ASIN_NOT_MATCHED'),
    ('delivery_text', '900010', 'POSTCODE_NOT_OBSERVED'),
    ('delivery_text', '90002', 'POSTCODE_NOT_OBSERVED'),
    ('delivery_text', '', 'POSTCODE_NOT_OBSERVED'),
    ('account_text', 'Hello, Alice', 'GUEST_CONTEXT_NOT_OBSERVED'),
    ('isolated_guest_context', False, 'GUEST_CONTEXT_NOT_OBSERVED'),
    ('error', 'PAGE_OR_LOCATION_TIMEOUT', 'PAGE_OR_LOCATION_TIMEOUT'),
])
def test_failure_never_becomes_matching_context_or_off_sale(observation, key, value, reason):
    observation[key] = value
    result = classify(observation)
    assert result['status'] == 'CONTEXT_NOT_VERIFIED'
    assert reason in result['reasons']
    assert result['purchasable'] == 'UNKNOWN'
    assert result['comparable_total'] is None


def test_qualifier_is_deterministic_and_does_not_modify_source(observation):
    before = deepcopy(observation)
    assert classify(observation) == classify(observation)
    assert observation == before


def test_conditional_free_shipping_cannot_become_zero_or_a_checkout_total(observation):
    observation['buybox_text'] = ('$23.99\n$12.00 per count\n'
        'FREE delivery on orders shipped by Amazon over $35\n'
        'Prime members get FREE delivery\nQuantity:1\nShips from\nAmazon\nSold by\nTest seller')
    offer = classify(observation)['offer_observation']
    assert offer['displayed_price_amount'] == '23.99'
    assert offer['seller_display_name'] == 'Test seller'
    assert offer['shipping_amount'] is offer['checkout_total'] is offer['applicable_discount'] is None
    assert offer['condition'] == 'UNKNOWN_NOT_EXPLICITLY_OBSERVED'
    assert offer['seller_matches_pds_own_offer'] == 'UNKNOWN'
    assert len(offer['delivery_terms']) == 2


@pytest.mark.parametrize('text', ['HKD188.26', 'Used & new from $19.95', '$12.00 per count', ''])
def test_foreign_currency_mixed_condition_and_unit_price_not_projected(observation, text):
    observation['buybox_text'] = text
    assert classify(observation)['offer_observation']['displayed_price_amount'] is None


def test_wrong_postcode_cannot_emit_price_even_with_valid_looking_buybox(observation):
    observation.update(delivery_text='Hong Kong', buybox_text='$23.99')
    assert classify(observation)['offer_observation']['displayed_price_amount'] is None


def test_existing_output_is_rejected_before_browser_import_or_launch(tmp_path):
    sentinel = tmp_path/'result.json'
    sentinel.write_text('preserved', encoding='utf-8')
    with pytest.raises(ValueError, match='new output directory'):
        run(tmp_path)
    assert sentinel.read_text(encoding='utf-8') == 'preserved'


def test_unrecognized_browser_is_rejected_before_import_or_launch(tmp_path):
    with pytest.raises(ValueError, match='Unsupported browser'):
        run(tmp_path/'new', channel='unknown')
    assert not (tmp_path/'new').exists()


def detailed(observation):
    observation.update(buybox_text='$23.99\nQuantity:1', offer_currency_code='USD',
        offer_details=dict(final_url=observation['final_url'], http_status=200,
            delivery_text='Los Angeles 90001', account_text='Hello, sign in',
            body_text='Synthetic New offer', rows=[dict(selector='#aod-pinned-offer',
                text='New\n$23.99\nFREE delivery on orders over $35',
                links=[dict(href='/gp/aag/main?seller=TEST&asin=B0H5BWL6J2')])]))
    return observation


def test_new_condition_and_seller_are_bound_to_matching_offer(observation):
    offer = classify(detailed(observation))['offer_observation']
    assert offer['condition'] == 'NEW_EXPLICIT_OFFER_ROW'
    assert offer['seller_id'] == 'TEST'
    assert offer['currency_code'] == 'USD'
    assert offer['shipping_amount'] is None


@pytest.mark.parametrize('mutation', ['postcode','condition','price','seller_conflict','wrong_asin','challenge','duplicate'])
def test_details_cannot_upgrade_different_or_ambiguous_offer(observation, mutation):
    detailed(observation)
    detail = observation['offer_details']; row = detail['rows'][0]
    if mutation == 'postcode': detail['delivery_text'] = 'Hong Kong'
    elif mutation == 'condition': row['text'] = row['text'].replace('New', 'Used - Like New')
    elif mutation == 'price': row['text'] = row['text'].replace('23.99','19.95')
    elif mutation == 'seller_conflict': observation['seller_id'] = 'OTHER'
    elif mutation == 'wrong_asin': row['links'][0]['href'] = '/gp/aag/main?seller=TEST&asin=OTHER'
    elif mutation == 'challenge': detail['body_text'] = 'Robot check'
    elif mutation == 'duplicate': detail['rows'].append(deepcopy(row))
    assert classify(observation)['offer_observation']['condition'] == 'UNKNOWN_NOT_EXPLICITLY_OBSERVED'
