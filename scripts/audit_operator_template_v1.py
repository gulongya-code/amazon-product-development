"""Emit a sanitized, deterministic audit of a private Operator Template V1."""

from __future__ import annotations

import argparse

from amazon_product_intelligence.contracts import canonical_json
from amazon_product_intelligence.operator_template_contract import (
    audit_workbook,
    validate_workbook_audit,
    workbook_audit_fingerprint,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read an XLSX without formula evaluation or data-row emission and "
            "print its deterministic Operator Template V1 audit."
        )
    )
    parser.add_argument("--workbook", required=True)
    parser.add_argument(
        "--validate",
        action="store_true",
        help="fail closed unless sheets, visibility, headers and dependencies match",
    )
    args = parser.parse_args()

    snapshot = audit_workbook(args.workbook)
    if args.validate:
        validate_workbook_audit(snapshot)
    payload = snapshot.to_dict()
    payload["audit_fingerprint"] = workbook_audit_fingerprint(snapshot)
    print(canonical_json(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
