"""One-shot native browser feasibility probe for the two authorized YPS offers.

This is source acquisition, not a price parser or business decision. A matched
guest delivery context still requires offer/pack/seller/discount qualification.
No personal browser profile, login, cart actions, checkout, retry or scheduler.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, parse_qs

from amazon_product_intelligence.ingestion.snapshot_writer import SnapshotWriter
from amazon_product_intelligence.schemas import APIResponse

ASINS = ('B0H5BWL6J2', 'B07XFCSRL5')
POSTCODE = '90001'
SP_STATUS = 'BUSINESS VALUE HUMAN REVIEW PENDING'


def classify(observation: dict) -> dict:
    """Qualify observed context only; missing/blocked evidence never means off-sale."""
    reasons = []
    if observation.get('error'):
        reasons.append(observation['error'])
    status = observation.get('http_status')
    if status is None or not 200 <= status < 300:
        reasons.append('HTTP_SUCCESS_NOT_OBSERVED')
    body = observation.get('body_text', '').lower()
    if any(x in body for x in ('enter the characters you see', 'robot check',
                               'sorry, we just need to make sure', 'verify you are human')):
        reasons.append('CHALLENGE_PAGE')
    parts = urlsplit(observation.get('final_url', ''))
    if (parts.hostname not in ('www.amazon.com', 'amazon.com')
            or not re.search(r'/dp/' + re.escape(observation['requested_asin']) + r'(?:/|$)', parts.path)):
        reasons.append('PRODUCT_URL_NOT_MATCHED')
    if observation.get('selected_asin') != observation['requested_asin']:
        reasons.append('SELECTED_ASIN_NOT_MATCHED')
    if not re.search(r'(?<!\d)90001(?!\d)', observation.get('delivery_text', '')):
        reasons.append('POSTCODE_NOT_OBSERVED')
    if not observation.get('isolated_guest_context') or not re.search(
            r'\bsign in\b', observation.get('account_text', ''), re.I):
        reasons.append('GUEST_CONTEXT_NOT_OBSERVED')
    lines = [line.strip() for line in observation.get('buybox_text', '').splitlines() if line.strip()]
    price = re.fullmatch(r'\$(\d+(?:,\d{3})*\.\d{2})', lines[0]) if lines else None
    # Only an exact first buybox price is projected. Other-seller minimums,
    # per-count prices, related products and Prime advertising are not quotes.
    price_amount = price.group(1).replace(',', '') if price and not reasons else None
    def following(label):
        matches = [i for i, text in enumerate(lines) if text == label]
        return lines[matches[0] + 1] if len(matches) == 1 and matches[0] + 1 < len(lines) else None
    offer = dict(displayed_price_amount=price_amount,
        displayed_currency_symbol='$' if price_amount else None,
        currency_code='UNKNOWN_NOT_EXPLICITLY_VERIFIED',
        seller_display_name=following('Sold by'), fulfillment_display_name=following('Ships from'),
        seller_matches_pds_own_offer='UNKNOWN', condition='UNKNOWN_NOT_EXPLICITLY_OBSERVED',
        selected_quantity=1 if 'Quantity:1' in lines else None,
        pack_claim=observation.get('title'), pack_qualification='TITLE_CLAIM_ONLY',
        availability_text=observation.get('availability_text'),
        add_to_cart_button=observation.get('cart_button_observation', 'UNKNOWN'),
        shipping_amount=None, shipping_status='UNKNOWN_FOR_SINGLE_PACK_NON_PRIME',
        delivery_terms=[text for text in lines if re.search(r'delivery|shipping|Prime', text, re.I)],
        applicable_discount=None, discount_status='UNKNOWN', checkout_total=None,
        qualification='PARTIAL_DISPLAY_OBSERVATION' if not reasons else 'CONTEXT_INVALID_DO_NOT_COMPARE')
    if not reasons:
        offer['seller_id'] = observation.get('seller_id')
        if price_amount and observation.get('offer_currency_code') == 'USD':
            offer['currency_code'] = 'USD'
        detail = observation.get('offer_details', {})
        parts = urlsplit(detail.get('final_url', ''))
        detail_ok = (not detail.get('error') and detail.get('http_status') == 200
            and parts.hostname in ('amazon.com', 'www.amazon.com')
            and re.search(r'/dp/' + re.escape(observation['requested_asin']) + r'(?:/|$)', parts.path)
            and re.search(r'(?<!\d)90001(?!\d)', detail.get('delivery_text', ''))
            and re.search(r'\bsign in\b', detail.get('account_text', ''), re.I)
            and not any(x in detail.get('body_text', '').lower() for x in
                ('robot check', 'verify you are human', 'enter the characters you see')))
        matches = []
        if detail_ok:
            for row in detail.get('rows', []):
                row_lines = [x.strip() for x in row['text'].splitlines() if x.strip()]
                prices = [x[1:] for x in row_lines if re.fullmatch(r'\$\d+\.\d{2}', x)]
                sellers = set()
                for link in row.get('links', []):
                    url = urlsplit(link.get('href') or '')
                    query = parse_qs(url.query)
                    if url.hostname not in (None, 'www.amazon.com', 'amazon.com'):
                        continue
                    if query.get('asin') == [observation['requested_asin']] and len(query.get('seller', [])) == 1:
                        sellers.add(query['seller'][0])
                if ('New' in row_lines and prices and prices[0] == price_amount
                        and len(sellers) == 1 and row.get('selector') == '#aod-pinned-offer'):
                    matches.append((row, next(iter(sellers))))
        if len(matches) == 1:
            row, seller_id = matches[0]
            # Conflicting primary and detail seller IDs cannot be merged.
            if not offer['seller_id'] or offer['seller_id'] == seller_id:
                offer.update(condition='NEW_EXPLICIT_OFFER_ROW', seller_id=seller_id,
                    condition_basis='MATCHED_PINNED_OFFER_ROW_PRICE_ASIN_CONTEXT',
                    offer_details_captured_at_utc=detail.get('captured_at_utc'),
                    offer_details_delivery_terms=[x.strip() for x in row['text'].splitlines()
                        if re.search(r'delivery|shipping|Prime', x, re.I)])
    return dict(status='CONTEXT_NOT_VERIFIED' if reasons else 'CONTEXT_OBSERVED_OFFER_UNVERIFIED',
        reasons=reasons, requested_buyer='NON_PRIME',
        observed_buyer='ISOLATED_SIGNED_OUT_GUEST' if not any('GUEST' in r for r in reasons) else 'UNKNOWN',
        offer_qualification='PARTIAL_OFFER_FIELDS_ONLY',
        purchasable='UNKNOWN', comparable_total=None, requested_currency='USD', observed_currency='UNKNOWN',
        offer_observation=offer, business_evidence_eligible=False, sp043b_status=SP_STATUS)


def _visible_text(page, selector):
    locator = page.locator(selector)
    for i in range(min(locator.count(), 8)):
        item = locator.nth(i)
        if item.is_visible():
            return item.inner_text(timeout=3000).strip()
    return ''


def _capture(page, observation):
    observation['final_url'] = page.url
    observation['body_text'] = page.locator('body').inner_text(timeout=5000)
    observation['delivery_text'] = _visible_text(page, '#glow-ingress-line2')
    observation['account_text'] = _visible_text(page, '#nav-link-accountList')
    observation['currency_preference_text'] = _visible_text(page, '#icp-touch-link-cop')
    selected = page.locator('input#ASIN')
    observation['selected_asin'] = selected.first.input_value() if selected.count() else None
    observation['title'] = _visible_text(page, '#productTitle')
    observation['buybox_text'] = _visible_text(page, '#desktop_buybox, #buybox')
    seller = page.locator('#sellerProfileTriggerId')
    visible_sellers = [seller.nth(i) for i in range(min(seller.count(), 8)) if seller.nth(i).is_visible()]
    observation['seller_href'] = visible_sellers[0].get_attribute('href') if len(visible_sellers) == 1 else None
    observation['seller_id'] = parse_qs(urlsplit(observation['seller_href'] or '').query).get('seller', [None])[0]
    currency = page.locator('input[name="items[0.base][customerVisiblePrice][currencyCode]"]')
    observation['offer_currency_code'] = currency.first.input_value() if currency.count() == 1 else None
    observation['availability_text'] = _visible_text(page, '#availability')
    cart = page.locator('#add-to-cart-button')
    observation['cart_button_observation'] = (
        'ENABLED_VISIBLE' if cart.count() == 1 and cart.is_visible() and cart.is_enabled()
        else 'NOT_OBSERVED_ENABLED')
    observation['cart_action_performed'] = False
    observation['captured_at_utc'] = datetime.now(timezone.utc).isoformat()


def collect(page, asin, directory, *, timeout_error):
    """Read one page, set delivery location through UI once, retain final evidence."""
    observation = dict(requested_asin=asin, requested_postcode=POSTCODE,
        isolated_guest_context=True, http_status=None, error=None,
        navigation_attempts=0, location_update_attempted=False)
    url = f'https://www.amazon.com/dp/{asin}'
    try:
        observation['navigation_attempts'] += 1
        response = page.goto(url, wait_until='domcontentloaded', timeout=30000)
        observation['http_status'] = response.status if response else None
        _capture(page, observation)
        initial = classify(observation)
        # Never attempt to work around a challenge, access denial or HTTP failure.
        if not any(x in initial['reasons'] for x in ('CHALLENGE_PAGE', 'HTTP_SUCCESS_NOT_OBSERVED')):
            if 'POSTCODE_NOT_OBSERVED' in initial['reasons']:
                location = page.locator('#nav-global-location-popover-link')
                if location.count() == 1 and location.is_visible():
                    observation['location_update_attempted'] = True
                    observation['location_step'] = 'OPEN_LOCATION'
                    location.click(timeout=5000)
                    observation['location_step'] = 'ENTER_POSTCODE'
                    page.locator('#GLUXZipUpdateInput').fill(POSTCODE, timeout=5000)
                    observation['location_step'] = 'APPLY_POSTCODE'
                    page.locator('#GLUXZipUpdate').click(timeout=5000)
                    # The location update is asynchronous. Navigating immediately
                    # can cancel it and silently restore the IP-derived location.
                    observation['location_step'] = 'WAIT_CONFIRMATION'
                    page.wait_for_function(r"""() => {
                        const location = document.querySelector('#glow-ingress-line2');
                        const close = [...document.querySelectorAll('#GLUXConfirmClose')]
                            .some(node => node.getClientRects().length > 0);
                        return /\b90001\b/.test(location?.textContent || '') ||
                            close;
                    }""", timeout=10000)
                    close = page.locator('#GLUXConfirmClose:visible')
                    if close.count():
                        observation['location_step'] = 'CONFIRM_LOCATION'
                        close.first.click(timeout=5000)
                        observation['location_step'] = 'WAIT_CONFIRMATION_CLOSED'
                        close.first.wait_for(state='hidden', timeout=10000)
                    # A single fresh navigation verifies the actual displayed context.
                    observation['location_step'] = 'VERIFY_FRESH_PAGE'
                    observation['navigation_attempts'] += 1
                    response = page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    observation['http_status'] = response.status if response else None
                    _capture(page, observation)
    except timeout_error:
        observation['error'] = 'PAGE_OR_LOCATION_TIMEOUT'
    except Exception:
        observation['error'] = 'BROWSER_READ_FAILED'
    # Capture whatever is actually visible on failure; never synthesize page fields.
    try:
        _capture(page, observation)
    except Exception:
        observation.setdefault('final_url', page.url)
        observation.setdefault('captured_at_utc', datetime.now(timezone.utc).isoformat())
    artifacts = []
    for name, action in (
        ('page.html', lambda p: p.write_text(page.content(), encoding='utf-8')),
        ('page.png', lambda p: page.screenshot(path=str(p), full_page=True, timeout=10000)),
    ):
        path = directory / name
        try:
            action(path)
            artifacts.append(dict(path=str(path.resolve()), sha256=sha256(path.read_bytes()).hexdigest()))
        except Exception:
            observation.setdefault('artifact_failures', []).append(name)
    observation['artifacts'] = artifacts
    return observation


def collect_details(page, asin, directory, *, timeout_error):
    """One read of Amazon's public offer-listing route; never click purchase controls.

    The new-condition query is a request, not proof that the returned offer is new.
    Preserve separate context and offer rows rather than merging sellers/prices.
    """
    detail = dict(requested_asin=asin, requested_condition='new', error=None,
                  http_status=None, rows=[], artifacts=[])
    try:
        response = page.goto(f'https://www.amazon.com/gp/offer-listing/{asin}/?condition=new',
                             wait_until='domcontentloaded', timeout=30000)
        detail.update(final_url=page.url, http_status=response.status if response else None,
                      delivery_text=_visible_text(page, '#glow-ingress-line2'),
                      account_text=_visible_text(page, '#nav-link-accountList'),
                      body_text=page.locator('body').inner_text(timeout=5000))
        if detail['http_status'] == 200 and not any(x in detail['body_text'].lower()
                for x in ('robot check', 'verify you are human', 'enter the characters you see')):
            more = page.locator('#aod-pinned-offer-show-more-link:visible')
            if more.count() == 1:
                more.click(timeout=5000)
                detail['expanded_offer_details'] = True
            shipping = page.locator('#aod-pinned-offer .aod-delivery-morelink:visible')
            if shipping.count() == 1:
                shipping.click(timeout=5000)
                detail['shipping_more_text'] = _visible_text(page, '.a-popover:visible')
                detail['shipping_more_clicked'] = True
            detail['body_text'] = page.locator('body').inner_text(timeout=5000)
        for selector in ('#aod-pinned-offer', '#aod-offer', '.olpOffer'):
            nodes = page.locator(selector)
            for i in range(min(nodes.count(), 10)):
                node = nodes.nth(i)
                if node.is_visible():
                    detail['rows'].append(dict(selector=selector, text=node.inner_text(),
                        links=node.locator('a[href]').evaluate_all('(nodes) => nodes.map(n => ({text:n.innerText, href:n.getAttribute("href")}))')))
    except timeout_error:
        detail['error'] = 'OFFER_DETAILS_TIMEOUT'
    except Exception:
        detail['error'] = 'OFFER_DETAILS_READ_FAILED'
    detail['captured_at_utc'] = datetime.now(timezone.utc).isoformat()
    for name, action in (
        ('offers.html', lambda p: p.write_text(page.content(), encoding='utf-8')),
        ('offers.png', lambda p: page.screenshot(path=str(p), full_page=True, timeout=10000)),
    ):
        path = directory / name
        try:
            action(path)
            detail['artifacts'].append(dict(path=str(path.resolve()), sha256=sha256(path.read_bytes()).hexdigest()))
        except Exception:
            detail.setdefault('artifact_failures', []).append(name)
    return detail


def run(output: Path, *, channel='msedge') -> dict:
    """Explicit invocation only. New output directory and fresh browser per run."""
    output = Path(output).absolute()
    if output != output.resolve() or output.exists():
        raise ValueError('Use a new output directory without symlink/junction redirection')
    if channel not in ('msedge', 'chrome'):
        raise ValueError('Unsupported browser channel')
    from playwright.sync_api import sync_playwright, TimeoutError as BrowserTimeout
    output.mkdir(parents=True, exist_ok=False)
    result = dict(schema='amazon-buyer-context-probe/v1', status='INCOMPLETE',
        scope=dict(asins=list(ASINS), postcode=POSTCODE, requested_buyer='NON_PRIME',
                   actual_session_policy='FRESH_SIGNED_OUT_GUEST_NO_PERSONAL_PROFILE'),
        started_at_utc=datetime.now(timezone.utc).isoformat(), observations=[],
        browser_channel=channel, playwright_version=version('playwright'),
        sorftime_requests=0, new_model_calls=0, cart_actions=0, purchases=0,
        automatic_scheduling=False, pds_submission=False, sp043b_status=SP_STATUS,
        consumer_ref=dict(path=str(Path(__file__).resolve()), sha256=sha256(Path(__file__).read_bytes()).hexdigest()))
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(channel=channel, headless=True)
            try:
                result['browser_version'] = browser.version
                for asin in ASINS:
                    # Keep per-product guest state isolated. No exported session state.
                    context = browser.new_context(locale='en-US', timezone_id='America/Los_Angeles')
                    try:
                        context.set_default_timeout(5000)
                        page = context.new_page()
                        directory = output / asin
                        directory.mkdir()
                        observation = collect(page, asin, directory, timeout_error=BrowserTimeout)
                        if not classify(observation)['reasons']:
                            observation['offer_details'] = collect_details(page, asin, directory, timeout_error=BrowserTimeout)
                        qualified = classify(observation)
                        # SnapshotWriter preserves JSON payloads; HTML/screenshots remain separate refs.
                        if observation['http_status'] is not None:
                            snapshot = SnapshotWriter(directory).write(APIResponse(
                                source='amazon_browser', status_code=observation['http_status'],
                                request_metadata=dict(asin=asin, postcode=POSTCODE, buyer='SIGNED_OUT_GUEST'),
                                payload=observation), snapshot_id='buyer_context')
                            snapshot_ref = dict(path=str(snapshot.resolve()), sha256=sha256(snapshot.read_bytes()).hexdigest())
                        else:
                            snapshot_ref = None  # No fabricated HTTP response code.
                        result['observations'].append(dict(asin=asin, observation=observation,
                            qualification=qualified, snapshot_ref=snapshot_ref))
                        print(f"{asin}: {qualified['status']}", flush=True)
                    finally:
                        context.close()
            finally:
                browser.close()
        if all(x['qualification']['status'] == 'CONTEXT_OBSERVED_OFFER_UNVERIFIED'
               for x in result['observations']) and len(result['observations']) == 2:
            result['status'] = 'CONTEXT_FEASIBILITY_OBSERVED_OFFER_VALIDATION_REQUIRED'
        else:
            result['status'] = 'SOURCE_CAPABILITY_NOT_PROVEN'
    except Exception:
        result['status'] = 'SOURCE_CAPABILITY_NOT_PROVEN'
        result['error'] = 'BROWSER_RUNTIME_FAILED'
    result['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
    with (output / 'result.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--channel', choices=('msedge', 'chrome'), default='msedge')
    args = parser.parse_args(argv)
    try:
        result = run(args.output, channel=args.channel)
    except (ValueError, OSError, ImportError):
        print('Probe not started: check optional buyer-probe dependency and fresh output path.')
        return 2
    print(result['status'])
    return 0 if result['status'] == 'CONTEXT_FEASIBILITY_OBSERVED_OFFER_VALIDATION_REQUIRED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
