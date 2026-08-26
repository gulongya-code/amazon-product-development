from __future__ import annotations

import json
from pathlib import Path

from amazon_product_intelligence.operator_template_contract import (
    TEMPLATE_CONTRACT_V1,
    TEMPLATE_SCHEMA_FINGERPRINT,
)


def test_checked_in_machine_schema_matches_runtime_contract():
    path = Path(
        "docs/contracts/MARKET_RESEARCH_WORKBOOK_TEMPLATE_CONTRACT_V1.schema.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    fingerprint = payload.pop("schema_fingerprint")
    assert payload == TEMPLATE_CONTRACT_V1.to_dict()
    assert fingerprint == TEMPLATE_SCHEMA_FINGERPRINT
