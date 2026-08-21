"""Declarative Attribute Dimension Registry V0.1.

Extraction engines consume this registry; they must not duplicate these value
or unit policies in extractor code.
"""

from amazon_product_intelligence.contracts import Unit, deterministic_id

from .models import (
    AllowedAttributeValue,
    AttributeCardinality,
    AttributeDimension,
    AttributeDimensionDefinition,
    AttributeDimensionRegistry,
    AttributeNormalizationRuleType,
    AttributeUnitRule,
    AttributeValueNormalizationRule,
)


ATTRIBUTE_TAXONOMY_VERSION = "product-attribute-taxonomy-v0.1"


def _unit(dimension: str, code: str, system: str) -> Unit:
    return Unit(dimension=dimension, unit_code=code, unit_system=system)


def _unit_rule(
    quantity_dimension: str,
    canonical: Unit,
    *accepted: Unit,
) -> AttributeUnitRule:
    return AttributeUnitRule(
        quantity_dimension=quantity_dimension,
        canonical_unit=canonical,
        accepted_units=(canonical, *accepted),
    )


def _definition(
    dimension: AttributeDimension,
    definition: str,
    cardinality: AttributeCardinality,
    *,
    allowed_values: tuple[AllowedAttributeValue, ...] = (),
    rules: tuple[AttributeValueNormalizationRule, ...] = (),
    unit_rules: tuple[AttributeUnitRule, ...] = (),
) -> AttributeDimensionDefinition:
    return AttributeDimensionDefinition(
        dimension=dimension,
        definition=definition,
        cardinality=cardinality,
        open_value_set=True,
        allowed_values=allowed_values,
        value_normalization_rules=rules,
        unit_rules=unit_rules,
    )


def build_attribute_dimension_registry_v0_1() -> AttributeDimensionRegistry:
    """Return the immutable default registry for the V0.1 contract."""

    plastic = AllowedAttributeValue(
        value_id="material.plastic",
        display_value="Plastic",
        aliases=("plastic",),
    )
    stainless = AllowedAttributeValue(
        value_id="material.stainless_steel",
        display_value="Stainless Steel",
        aliases=("stainless steel", "stainless-steel"),
    )
    silicone = AllowedAttributeValue(
        value_id="material.silicone",
        display_value="Silicone",
        aliases=("silicone",),
    )
    leakproof = AllowedAttributeValue(
        value_id="feature.leakproof",
        display_value="Leakproof",
        aliases=("leakproof", "leak-proof", "leak proof"),
    )
    portable = AllowedAttributeValue(
        value_id="feature.portable",
        display_value="Portable",
        aliases=("portable",),
    )
    foldable = AllowedAttributeValue(
        value_id="feature.foldable",
        display_value="Foldable",
        aliases=("foldable",),
    )
    hiking = AllowedAttributeValue(
        value_id="use_case.hiking",
        display_value="Hiking",
        aliases=("hiking",),
    )
    travel = AllowedAttributeValue(
        value_id="use_case.travel",
        display_value="Travel",
        aliases=("travel", "travelling", "traveling"),
    )

    volume_l = _unit("VOLUME", "L", "SI")
    mass_g = _unit("MASS", "g", "SI")
    length_cm = _unit("LENGTH", "cm", "SI")
    count = _unit("COUNT", "COUNT", "DOMAIN")

    definitions = (
        _definition(
            AttributeDimension.PRODUCT_TYPE,
            "The canonical kind of product represented by this profile.",
            AttributeCardinality.SINGLE,
        ),
        _definition(
            AttributeDimension.MATERIAL,
            "Materials explicitly used in the product or its relevant components.",
            AttributeCardinality.MULTI,
            allowed_values=(plastic, stainless, silicone),
            rules=(
                AttributeValueNormalizationRule(
                    rule_id="material.alias.plastic.v0.1",
                    rule_type=AttributeNormalizationRuleType.ALIAS,
                    source_values=plastic.aliases,
                    target_value_id=plastic.value_id,
                ),
                AttributeValueNormalizationRule(
                    rule_id="material.alias.stainless-steel.v0.1",
                    rule_type=AttributeNormalizationRuleType.ALIAS,
                    source_values=stainless.aliases,
                    target_value_id=stainless.value_id,
                ),
                AttributeValueNormalizationRule(
                    rule_id="material.alias.silicone.v0.1",
                    rule_type=AttributeNormalizationRuleType.ALIAS,
                    source_values=silicone.aliases,
                    target_value_id=silicone.value_id,
                ),
            ),
        ),
        _definition(
            AttributeDimension.COLOR,
            "An explicitly evidenced product color or provider-declared color label.",
            AttributeCardinality.MULTI,
        ),
        _definition(
            AttributeDimension.CAPACITY,
            "A supported amount of volume, mass, or count that the product can contain or process.",
            AttributeCardinality.MULTI,
            unit_rules=(
                _unit_rule(
                    "VOLUME",
                    volume_l,
                    _unit("VOLUME", "mL", "SI"),
                    _unit("VOLUME", "fl_oz", "US_CUSTOMARY"),
                ),
                _unit_rule(
                    "MASS",
                    mass_g,
                    _unit("MASS", "kg", "SI"),
                    _unit("MASS", "oz", "US_CUSTOMARY"),
                    _unit("MASS", "lb", "US_CUSTOMARY"),
                ),
            ),
        ),
        _definition(
            AttributeDimension.DIMENSION,
            "A structured physical dimension such as length, width, height, or diameter.",
            AttributeCardinality.SINGLE,
            unit_rules=(
                _unit_rule(
                    "LENGTH",
                    length_cm,
                    _unit("LENGTH", "mm", "SI"),
                    _unit("LENGTH", "m", "SI"),
                    _unit("LENGTH", "in", "US_CUSTOMARY"),
                    _unit("LENGTH", "ft", "US_CUSTOMARY"),
                ),
            ),
        ),
        _definition(
            AttributeDimension.SIZE,
            "A named, ordinal, or provider-declared product size distinct from capacity.",
            AttributeCardinality.MULTI,
        ),
        _definition(
            AttributeDimension.STRUCTURE,
            "Physical construction or configuration characteristics of the product.",
            AttributeCardinality.MULTI,
        ),
        _definition(
            AttributeDimension.FEATURE,
            "Functional or differentiating capabilities explicitly supported by evidence.",
            AttributeCardinality.MULTI,
            allowed_values=(leakproof, portable, foldable),
            rules=(
                AttributeValueNormalizationRule(
                    rule_id="feature.alias.leakproof.v0.1",
                    rule_type=AttributeNormalizationRuleType.ALIAS,
                    source_values=leakproof.aliases,
                    target_value_id=leakproof.value_id,
                ),
                AttributeValueNormalizationRule(
                    rule_id="feature.alias.portable.v0.1",
                    rule_type=AttributeNormalizationRuleType.ALIAS,
                    source_values=portable.aliases,
                    target_value_id=portable.value_id,
                ),
                AttributeValueNormalizationRule(
                    rule_id="feature.alias.foldable.v0.1",
                    rule_type=AttributeNormalizationRuleType.ALIAS,
                    source_values=foldable.aliases,
                    target_value_id=foldable.value_id,
                ),
            ),
        ),
        _definition(
            AttributeDimension.OPERATION_METHOD,
            "How the buyer operates, powers, controls, opens, closes, or installs the product.",
            AttributeCardinality.MULTI,
        ),
        _definition(
            AttributeDimension.COMPATIBILITY,
            "Products, systems, models, environments, or standards with which the product works.",
            AttributeCardinality.MULTI,
        ),
        _definition(
            AttributeDimension.PACKAGE_QUANTITY,
            "The explicitly evidenced count of saleable or included units in the package.",
            AttributeCardinality.SINGLE,
            unit_rules=(
                _unit_rule(
                    "COUNT",
                    count,
                    _unit("COUNT", "units", "DOMAIN"),
                    _unit("COUNT", "pieces", "DOMAIN"),
                    _unit("COUNT", "pairs", "DOMAIN"),
                ),
            ),
        ),
        _definition(
            AttributeDimension.AUDIENCE,
            "An explicitly evidenced intended user group; not a demographic guess.",
            AttributeCardinality.MULTI,
        ),
        _definition(
            AttributeDimension.USE_CASE,
            "An explicitly evidenced situation or job in which the product is used.",
            AttributeCardinality.MULTI,
            allowed_values=(hiking, travel),
            rules=(
                AttributeValueNormalizationRule(
                    rule_id="use-case.alias.hiking.v0.1",
                    rule_type=AttributeNormalizationRuleType.ALIAS,
                    source_values=hiking.aliases,
                    target_value_id=hiking.value_id,
                ),
                AttributeValueNormalizationRule(
                    rule_id="use-case.alias.travel.v0.1",
                    rule_type=AttributeNormalizationRuleType.ALIAS,
                    source_values=travel.aliases,
                    target_value_id=travel.value_id,
                ),
            ),
        ),
        _definition(
            AttributeDimension.PROBLEM_SOLVED,
            "A buyer problem the product explicitly claims or demonstrates that it addresses.",
            AttributeCardinality.MULTI,
        ),
        _definition(
            AttributeDimension.PRICE_BAND,
            "A versioned market-relative price segment derived from comparable price evidence.",
            AttributeCardinality.SINGLE,
        ),
    )
    definitions = tuple(sorted(definitions, key=lambda item: item.dimension.value))
    payload = {
        "taxonomy_version": ATTRIBUTE_TAXONOMY_VERSION,
        "dimensions": [item.to_dict() for item in definitions],
    }
    return AttributeDimensionRegistry(
        registry_id=deterministic_id("attribute-registry", payload),
        taxonomy_version=ATTRIBUTE_TAXONOMY_VERSION,
        dimensions=definitions,
    )


ATTRIBUTE_DIMENSION_REGISTRY_V0_1 = build_attribute_dimension_registry_v0_1()


__all__ = (
    "ATTRIBUTE_TAXONOMY_VERSION",
    "ATTRIBUTE_DIMENSION_REGISTRY_V0_1",
    "build_attribute_dimension_registry_v0_1",
)
