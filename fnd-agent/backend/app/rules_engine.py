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
