"""Read a hash-bound PDS project review of the exact native market capture.

File-only receipt consumption. No sibling code import, model, browser or scheduler.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from amazon_product_intelligence.buyer_context_probe import SP_STATUS


def read_verified(path, digest):
    path = Path(path).absolute()
    if path != path.resolve() or str(path).startswith(('\\\\','//')):
        raise ValueError('Only local files without redirection are supported')
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != digest:
        raise ValueError('Source SHA mismatch')
    return json.loads(raw)


def consume(receipt, receipt_sha, market_result, output):
    output = Path(output).absolute()
    if output != output.resolve() or output.exists():
        raise ValueError('Use a fresh readback output')
    review = read_verified(receipt, receipt_sha)
    source_ref = review['market_result_ref']
    if Path(source_ref['path']).resolve() != Path(market_result).resolve():
        raise ValueError('PDS reviewed a different market result')
    source = read_verified(market_result, source_ref['sha256'])
    evidence = read_verified(review['evidence_ref']['path'], review['evidence_ref']['sha256'])
    if (review['kind'] != 'YPS_MARKET_OFFER_PROJECT_REVIEW'
            or review['status'] != 'ANALYSIS_COMPLETED' or review['origin'] != 'PROJECT_PROVIDER_ANALYSIS'
            or review['provider_calls'] != 1 or review['transport']['phase'] != 'COMPLETE'
            or review['transport']['http_status'] != 200
            or review['input_ref'] != evidence['record_ref']
            or review['proposal']['input_ref'] != evidence['record_ref']
            or evidence['market_result_ref'] != source_ref
            or review['non_executable'] is not True or review['formal_state_changed'] is not False
            or review['automatic_scheduling'] is not False or review['purchases'] != 0
            or review['sp043b_status'] != SP_STATUS or source['sp043b_status'] != SP_STATUS
            or set(review['proposal']['original_claim_review']) != {'M1','M2','M3','M4','M5'}):
        raise ValueError('PDS analysis or non-execution boundary not verified')
    # All evidence files are checked again; a receipt alone is not source closure.
    for ref in evidence['source_refs']:
        path = Path(ref['path'])
        if str(path).startswith(('\\\\','//')) or path.absolute() != path.resolve():
            raise ValueError('Local evidence required')
        if sha256(path.read_bytes()).hexdigest() != ref['sha256']:
            raise ValueError('PDS evidence changed')
    record = dict(schema='market-pds-offer-readback/v1', status='PDS_ANALYSIS_READ_BACK',
        consumed_at_utc=datetime.now(timezone.utc).isoformat(),
        receipt_ref=dict(path=str(Path(receipt).resolve()), sha256=receipt_sha),
        market_result_ref=source_ref, pds_input_ref=evidence['record_ref'],
        actual_claim_review=review['proposal']['original_claim_review'],
        recommendation=review['proposal']['recommendation'],
        remaining_gap_action=review['proposal']['remaining_gap_action'],
        analytical_consumption_confirmed=True, business_value_accepted=False,
        non_executable=True, sp043b_status=SP_STATUS)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf8') as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--receipt-sha256', required=True)
    parser.add_argument('--market-result', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(consume(args.receipt, args.receipt_sha256, args.market_result, args.output)['status'])


if __name__ == '__main__':
    main()
