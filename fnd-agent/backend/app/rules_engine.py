from __future__ import annotations

from typing import Dict
from .models import ProductDetail, UsageCheckResponse


def build_spec_map(detail: ProductDetail) -> Dict[str, str]:
    """
    Turn list of ProductSpec into a dict:
      { 'bathroom floor use': 'Not Suitable for Bathroom Floor', ... }

    - lowercase keys
    - collapse whitespace
    - if we see the same key multiple times, keep the *shortest* value
      (tends to be the actual spec, not the giant marketing blob).
    """
    spec_map: Dict[str, str] = {}

    for spec in detail.specs:
        key = spec.spec_key.strip().lower()
        if not key:
            continue
        val = " ".join(spec.spec_value.split())  # collapse crazy whitespace

        existing = spec_map.get(key)
        if existing is None or len(val) < len(existing):
            spec_map[key] = val

    return spec_map


def check_bathroom_floor(detail: ProductDetail) -> UsageCheckResponse:
    """
    Rule:
    - If there is 'bathroom floor use':
        - contains 'not suitable'  -> ok = False
        - contains 'suitable'/'yes' -> ok = True
    - Otherwise fall back on water resistance / placement and return 'unknown/maybe'.
    """
    spec_map = build_spec_map(detail)
    supporting: Dict[str, str] = {}

    bf = spec_map.get("bathroom floor use", "")
    if bf:
        supporting["bathroom floor use"] = bf
        low = bf.lower()
        if "not suitable" in low:
            return UsageCheckResponse(
                sku=detail.product.sku,
                use_case="bathroom_floor",
                ok=False,
                confidence=0.95,
                reason="Spec 'Bathroom Floor Use' says 'Not Suitable for Bathroom Floor'.",
                supporting_specs=supporting,
            )
        if "suitable" in low or "yes" in low:
            return UsageCheckResponse(
                sku=detail.product.sku,
                use_case="bathroom_floor",
                ok=True,
                confidence=0.9,
                reason="Spec 'Bathroom Floor Use' indicates bathroom floor use is allowed.",
                supporting_specs=supporting,
            )

    water = spec_map.get("water resistance", "")
    placement = spec_map.get("placement location", "")
    if water:
        supporting["water resistance"] = water
    if placement:
        supporting["placement location"] = placement

    if water or placement:
        return UsageCheckResponse(
            sku=detail.product.sku,
            use_case="bathroom_floor",
            ok=None,
            confidence=0.6,
            reason="No explicit 'Bathroom Floor Use' spec. Product is water-resistant / has placement info, but bathroom floor suitability is not guaranteed.",
            supporting_specs=supporting,
        )

    return UsageCheckResponse(
        sku=detail.product.sku,
        use_case="bathroom_floor",
        ok=None,
        confidence=0.0,
        reason="No relevant specs found for bathroom floor usage.",
        supporting_specs=supporting,
    )

def check_shower_floor(detail: ProductDetail) -> UsageCheckResponse:
    spec_map = build_spec_map(detail)
    supporting = {}

    shower_surface = spec_map.get("shower surface", "")
    if shower_surface:
        supporting["shower surface"] = shower_surface
        low = shower_surface.lower()
        if "not suitable for shower floors" in low or "not suitable for shower floor" in low:
            return UsageCheckResponse(
                sku=detail.product.sku,
                use_case="shower_floor",
                ok=False,
                confidence=0.95,
                reason="Spec 'Shower Surface' explicitly says it is not suitable for shower floors.",
                supporting_specs=supporting,
            )
        if "suitable for shower floors" in low or "suitable for shower floor" in low:
            return UsageCheckResponse(
                sku=detail.product.sku,
                use_case="shower_floor",
                ok=True,
                confidence=0.9,
                reason="Spec 'Shower Surface' indicates it is suitable for shower floors.",
                supporting_specs=supporting,
            )

    dcof = spec_map.get("dcof value", "") or spec_map.get("dcof", "")
    if dcof:
        supporting["dcof"] = dcof

    return UsageCheckResponse(
        sku=detail.product.sku,
        use_case="shower_floor",
        ok=None,
        confidence=0.4,
        reason="No explicit shower floor spec. Check DCOF and manufacturer guidelines before using on shower floor.",
        supporting_specs=supporting,
    )


def check_shower_wall(detail: ProductDetail) -> UsageCheckResponse:
    spec_map = build_spec_map(detail)
    supporting = {}

    shower_surface = spec_map.get("shower surface", "")
    if shower_surface:
        supporting["shower surface"] = shower_surface
        low = shower_surface.lower()
        if "suitable for shower walls" in low or "yes" in low:
            return UsageCheckResponse(
                sku=detail.product.sku,
                use_case="shower_wall",
                ok=True,
                confidence=0.9,
                reason="Spec 'Shower Surface' indicates it is suitable for shower walls.",
                supporting_specs=supporting,
            )
        if "not suitable for shower walls" in low:
            return UsageCheckResponse(
                sku=detail.product.sku,
                use_case="shower_wall",
                ok=False,
                confidence=0.95,
                reason="Spec 'Shower Surface' explicitly says it is not suitable for shower walls.",
                supporting_specs=supporting,
            )

    return UsageCheckResponse(
        sku=detail.product.sku,
        use_case="shower_wall",
        ok=None,
        confidence=0.4,
        reason="No explicit shower wall spec found. Likely okay for walls if the product is rated for wet areas, but verify with full specs.",
        supporting_specs=supporting,
    )


def check_fireplace_surround(detail: ProductDetail) -> UsageCheckResponse:
    spec_map = build_spec_map(detail)
    supporting = {}

    fp = spec_map.get("fireplace surround use", "")
    if fp:
        supporting["fireplace surround use"] = fp
        low = fp.lower()
        if "yes" in low or "suitable" in low:
            return UsageCheckResponse(
                sku=detail.product.sku,
                use_case="fireplace_surround",
                ok=True,
                confidence=0.9,
                reason="Spec 'Fireplace Surround Use' indicates it is suitable around fireplaces.",
                supporting_specs=supporting,
            )
        if "no" in low or "not suitable" in low:
            return UsageCheckResponse(
                sku=detail.product.sku,
                use_case="fireplace_surround",
                ok=False,
                confidence=0.95,
                reason="Spec 'Fireplace Surround Use' indicates it is not suitable around fireplaces.",
                supporting_specs=supporting,
            )

    return UsageCheckResponse(
        sku=detail.product.sku,
        use_case="fireplace_surround",
        ok=None,
        confidence=0.3,
        reason="No explicit fireplace surround spec found. Check heat tolerance and manufacturer documentation.",
        supporting_specs=supporting,
    )


def check_radiant_heat(detail: ProductDetail) -> UsageCheckResponse:
    spec_map = build_spec_map(detail)
    supporting = {}

    rh = spec_map.get("radiant heat compatible", "") or spec_map.get(
        "radiant heat compatibility", ""
    )
    if rh:
        supporting["radiant heat compatible"] = rh
        low = rh.lower()
        if "yes" in low or "compatible" in low:
            return UsageCheckResponse(
                sku=detail.product.sku,
                use_case="radiant_heat",
                ok=True,
                confidence=0.9,
                reason="Spec indicates compatibility with radiant heat.",
                supporting_specs=supporting,
            )
        if "no" in low or "not compatible" in low:
            return UsageCheckResponse(
                sku=detail.product.sku,
                use_case="radiant_heat",
                ok=False,
                confidence=0.95,
                reason="Spec indicates this product is not compatible with radiant heat.",
                supporting_specs=supporting,
            )

    return UsageCheckResponse(
        sku=detail.product.sku,
        use_case="radiant_heat",
        ok=None,
        confidence=0.3,
        reason="No explicit radiant heat spec found. Check system and manufacturer guidelines.",
        supporting_specs=supporting,
    )