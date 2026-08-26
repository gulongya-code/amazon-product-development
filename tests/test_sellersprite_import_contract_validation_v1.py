from __future__ import annotations

import pytest

from amazon_product_intelligence.sellersprite_import import ImportContext


@pytest.mark.parametrize("imported_at", ["not-a-time", "2026-08-26T12:00:00"])
def test_import_context_requires_timezone_aware_rfc3339(imported_at: str) -> None:
    with pytest.raises(ValueError, match="imported_at"):
        ImportContext(
            marketplace="US",
            category="synthetic-category",
            imported_at=imported_at,
        )


def test_import_context_rejects_non_iso_observed_date() -> None:
    with pytest.raises(ValueError, match="observed_date"):
        ImportContext(
            marketplace="US",
            category="synthetic-category",
            imported_at="2026-08-26T12:00:00Z",
            observed_date="08/26/2026",
        )
