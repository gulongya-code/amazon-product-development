# SP-041S1 Private Calibration Asset Inventory V1.1

Status: **CALIBRATION_ASSETS_READY — PRIVATE SOURCE FILES EXTERNAL TO GIT**

## 1. Purpose

Record the privacy-safe inventory of real SellerSprite-style source assets made available for the remaining SP-041S1 multi-category calibration gate.

No source workbook bytes, ASINs, titles, brands, sellers, prices, raw rows or private absolute paths are stored in this repository.

## 2. Qualified calibration corpus

| Calibration ID | Public category label | Listings | Unique listing identities | Title coverage | Structured-detail coverage | Primary semantic stress pattern |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `CAL_SHOWER_CADDY` | Shower Caddy | 998 | 998 | 100.00% | 100.00% | installation / attachment / structural form |
| `CAL_DOG_WATER_BOTTLE` | Dog Water Bottle | 400 | 400 | 100.00% | 100.00% | capacity / portability / usage / operation |
| `CAL_VACUUM_FILTER` | Vacuum Filter | 300 | 300 | 100.00% | 100.00% | compatibility / replacement / accessory boundary |
| `CAL_FOOD_STORAGE_SET` | Food Storage Container Sets | 150 | 150 | 100.00% | 99.33% | size / material / quantity / set semantics |
| `CAL_AIR_FRYER_MIXED` | Air Fryer mixed market sample | 300 | 300 | 100.00% | 100.00% | capacity / operation / powered-product and accessory boundary |

Qualified corpus total: **2,148 listings**.

Aggregate inventory fingerprint over only the sanitized table above and stable calibration IDs:

`4f7490a64c7e00773038b799ea576556ea05d7a559368fd45484a8addfe2abee`

This fingerprint is not a hash of any private source file or raw row.

## 3. Excluded exploratory asset

A separate `Bundle` search export contains 300 listings spanning unrelated product categories. It is retained privately only as exploratory noise/boundary material and is **not** treated as one formal calibration category because `Bundle` is a product-role/composition concept rather than a coherent market category.

Decision: `EXCLUDED_FROM_FORMAL_CATEGORY_CORPUS`.

Bundle/set/quantity semantics will instead be calibrated inside coherent categories such as Food Storage Container Sets and through Product Role review.

## 4. Source suitability

All five qualified assets contain listing-grain buyer-facing Title evidence and SellerSprite structured `详细参数` evidence at sufficient coverage to execute the S1 evidence-source comparison runbook.

The corpus collectively covers the Issue #55 target patterns:

1. installation/structure-heavy products — covered;
2. capacity + operation products — covered;
3. compatibility/accessory/replacement-heavy products — covered;
4. powered/electronic operation products — covered, with mixed primary/accessory market noise intentionally retained for Product Role calibration;
5. size/material-heavy products — covered;
6. bundle/multipack/set semantics — covered within a coherent product category rather than a cross-category `Bundle` search pool.

## 5. Privacy boundary

The following remain private/external and must not be committed:

- original XLSX/CSV/ZIP files;
- ASIN lists;
- titles;
- brands/sellers;
- prices tied to listings;
- full `详细参数` strings;
- source workbook paths;
- raw category rows.

Repository output from calibration is limited to aggregate counts/rates, semantic-role coverage, relationship/conflict distributions, Product Role distributions, profile/version identifiers, methodology and operator-approved conclusions.

## 6. Current gate state

`PRIVATE_MULTI_CATEGORY_ASSETS_AVAILABLE = YES`

`FORMAL_CALIBRATION_CATEGORIES = 5`

`QUALIFIED_LISTINGS = 2148`

The prior S1 blocker `PRIVATE_MULTI_CATEGORY_CALIBRATION_REQUIRED` may now move from **asset unavailable** to **calibration execution pending**. SP-041S1 is not PASS until the evidence matrices, bounded review, cross-category synthesis and derived V2 acceptance gates are completed and validated.
