from __future__ import annotations

import re
from typing import Dict, Optional

from .models import ProductDetail, UsageCheckResponse, UseCase


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


def _extract_float(raw: str) -> Optional[float]:
    if not raw:
        return None
    normalized = raw.replace(",", " ")
    match = re.search(r"-?\d+(?:\.\d+)?", normalized)
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None
    return None


def _contains_any(raw: str, *keywords: str) -> bool:
    if not raw:
        return False
    low = raw.lower()
    return any(keyword in low for keyword in keywords)


def _mk_response(
    detail: ProductDetail,
    use_case: UseCase,
    ok,
    confidence: float,
    reason: str,
    supporting_specs: Dict[str, str],
) -> UsageCheckResponse:
    return UsageCheckResponse(
        sku=detail.product.sku,
        use_case=use_case,
        ok=ok,
        confidence=confidence,
        reason=reason,
        supporting_specs=supporting_specs,
    )


def check_bathroom_floor(detail: ProductDetail) -> UsageCheckResponse:
    spec_map = build_spec_map(detail)
    supporting: Dict[str, str] = {}

    bf = spec_map.get("bathroom floor use", "")
    if bf:
        supporting["bathroom floor use"] = bf
        low = bf.lower()
        if "not suitable" in low:
            return _mk_response(
                detail,
                UseCase.bathroom_floor,
                ok=False,
                confidence=0.95,
                reason="Spec 'Bathroom Floor Use' says 'Not Suitable for Bathroom Floor'.",
                supporting_specs=supporting,
            )
        if "suitable" in low or "yes" in low:
            return _mk_response(
                detail,
                UseCase.bathroom_floor,
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
        return _mk_response(
            detail,
            UseCase.bathroom_floor,
            ok=None,
            confidence=0.6,
            reason="No explicit 'Bathroom Floor Use' spec. Product is water-resistant / has placement info, but bathroom floor suitability isn’t guaranteed.",
            supporting_specs=supporting,
        )

    return _mk_response(
        detail,
        UseCase.bathroom_floor,
        ok=None,
        confidence=0.0,
        reason="No relevant specs found for bathroom floor usage.",
        supporting_specs=supporting,
    )


def check_shower_floor(detail: ProductDetail) -> UsageCheckResponse:
    spec_map = build_spec_map(detail)
    supporting: Dict[str, str] = {}

    shower_surface = spec_map.get("shower surface", "")
    if shower_surface:
        supporting["shower surface"] = shower_surface
        low = shower_surface.lower()
        if "not suitable for shower floors" in low or "not suitable for shower floor" in low:
            return _mk_response(
                detail,
                UseCase.shower_floor,
                ok=False,
                confidence=0.95,
                reason="Spec 'Shower Surface' explicitly says it is not suitable for shower floors.",
                supporting_specs=supporting,
            )
        if "suitable for shower floors" in low or "suitable for shower floor" in low:
            return _mk_response(
                detail,
                UseCase.shower_floor,
                ok=True,
                confidence=0.9,
                reason="Spec 'Shower Surface' indicates it is suitable for shower floors.",
                supporting_specs=supporting,
            )

    dcof = spec_map.get("dcof value", "") or spec_map.get("dcof", "")
    if dcof:
        supporting["dcof"] = dcof

    return _mk_response(
        detail,
        UseCase.shower_floor,
        ok=None,
        confidence=0.4,
        reason="No explicit shower floor spec. Check DCOF and manufacturer guidelines before using on a shower floor.",
        supporting_specs=supporting,
    )


def check_shower_wall(detail: ProductDetail) -> UsageCheckResponse:
    spec_map = build_spec_map(detail)
    supporting: Dict[str, str] = {}

    shower_surface = spec_map.get("shower surface", "")
    if shower_surface:
        supporting["shower surface"] = shower_surface
        low = shower_surface.lower()
        if "suitable for shower walls" in low:
            return _mk_response(
                detail,
                UseCase.shower_wall,
                ok=True,
                confidence=0.9,
                reason="Spec 'Shower Surface' indicates it is suitable for shower walls.",
                supporting_specs=supporting,
            )
        if "not suitable for shower walls" in low:
            return _mk_response(
                detail,
                UseCase.shower_wall,
                ok=False,
                confidence=0.95,
                reason="Spec 'Shower Surface' explicitly says it is not suitable for shower walls.",
                supporting_specs=supporting,
            )

    return _mk_response(
        detail,
        UseCase.shower_wall,
        ok=None,
        confidence=0.4,
        reason="No explicit shower wall spec found. Likely okay for many tiles rated for wet walls, but verify with full specs.",
        supporting_specs=supporting,
    )


def check_fireplace_surround(detail: ProductDetail) -> UsageCheckResponse:
    spec_map = build_spec_map(detail)
    supporting: Dict[str, str] = {}

    fp = spec_map.get("fireplace surround use", "")
    if fp:
        supporting["fireplace surround use"] = fp
        low = fp.lower()
        if "yes" in low or "suitable" in low:
            return _mk_response(
                detail,
                UseCase.fireplace_surround,
                ok=True,
                confidence=0.9,
                reason="Spec 'Fireplace Surround Use' indicates it is suitable around fireplaces.",
                supporting_specs=supporting,
            )
        if "no" in low or "not suitable" in low:
            return _mk_response(
                detail,
                UseCase.fireplace_surround,
                ok=False,
                confidence=0.95,
                reason="Spec 'Fireplace Surround Use' indicates it is not suitable around fireplaces.",
                supporting_specs=supporting,
            )

    return _mk_response(
        detail,
        UseCase.fireplace_surround,
        ok=None,
        confidence=0.3,
        reason="No explicit fireplace surround spec found. Check heat tolerance and manufacturer documentation.",
        supporting_specs=supporting,
    )


def check_radiant_heat(detail: ProductDetail) -> UsageCheckResponse:
    spec_map = build_spec_map(detail)
    supporting: Dict[str, str] = {}

    rh = spec_map.get("radiant heat compatible", "") or spec_map.get(
        "radiant heat compatibility", ""
    )
    if rh:
        supporting["radiant heat compatible"] = rh
        low = rh.lower()
        if "yes" in low or "compatible" in low:
            return _mk_response(
                detail,
                UseCase.radiant_heat,
                ok=True,
                confidence=0.9,
                reason="Spec indicates compatibility with radiant heat.",
                supporting_specs=supporting,
            )
        if "no" in low or "not compatible" in low:
            return _mk_response(
                detail,
                UseCase.radiant_heat,
                ok=False,
                confidence=0.95,
                reason="Spec indicates this product is not compatible with radiant heat.",
                supporting_specs=supporting,
            )

    return _mk_response(
        detail,
        UseCase.radiant_heat,
        ok=None,
        confidence=0.3,
        reason="No explicit radiant heat spec found. Check system and manufacturer guidelines.",
        supporting_specs=supporting,
    )


def check_outdoor_patio(detail: ProductDetail) -> UsageCheckResponse:
    spec_map = build_spec_map(detail)
    supporting: Dict[str, str] = {}

    placement = spec_map.get("placement location", "")
    frost = spec_map.get("frost resistance", "")
    water_absorption = spec_map.get("water absorption", "")
    water_resistance = spec_map.get("water resistance", "")

    if placement:
        supporting["placement location"] = placement
        if "indoor only" in placement.lower():
            return _mk_response(
                detail,
                UseCase.outdoor_patio,
                ok=False,
                confidence=0.9,
                reason="Placement spec restricts this product to indoor installations.",
                supporting_specs=supporting,
            )

    if frost:
        supporting["frost resistance"] = frost
        if _contains_any(frost, "no", "not resistant"):
            return _mk_response(
                detail,
                UseCase.outdoor_patio,
                ok=False,
                confidence=0.9,
                reason="Spec 'Frost Resistance' indicates the material is not frost resistant.",
                supporting_specs=supporting,
            )

    if water_absorption:
        supporting["water absorption"] = water_absorption

    freeze_ready = False
    if placement and "outdoor" in placement.lower():
        freeze_ready = True
    if frost and _contains_any(frost, "yes", "resistant", "rated"):
        freeze_ready = True

    water_abs_val = _extract_float(water_absorption)
    if water_abs_val is not None and water_abs_val <= 0.5:
        freeze_ready = True

    if freeze_ready:
        return _mk_response(
            detail,
            UseCase.outdoor_patio,
            ok=True,
            confidence=0.85,
            reason="Specs indicate outdoor placement and freeze-thaw readiness, suitable for patios.",
            supporting_specs=supporting,
        )

    if water_resistance:
        supporting["water resistance"] = water_resistance
        if _contains_any(
            water_resistance,
            "not water",
            "not resistant",
            "not recommended",
            "no ",
        ):
            return _mk_response(
                detail,
                UseCase.outdoor_patio,
                ok=False,
                confidence=0.8,
                reason="Water-resistance spec warns against exposure, so an uncovered patio is risky.",
                supporting_specs=supporting,
            )

    return _mk_response(
        detail,
        UseCase.outdoor_patio,
        ok=None,
        confidence=0.4,
        reason="Outdoor placement or freeze-thaw data not found. Verify frost resistance before patio use.",
        supporting_specs=supporting,
    )


def check_pool_deck(detail: ProductDetail) -> UsageCheckResponse:
    spec_map = build_spec_map(detail)
    supporting: Dict[str, str] = {}

    placement = spec_map.get("placement location", "")
    dcof = spec_map.get("dcof value", "") or spec_map.get("dcof", "")
    water_resistance = spec_map.get("water resistance", "")

    if placement:
        supporting["placement location"] = placement
        if "outdoor" not in placement.lower():
            return _mk_response(
                detail,
                UseCase.pool_deck,
                ok=False,
                confidence=0.85,
                reason="Spec does not list outdoor placement, so a pool deck installation is not recommended.",
                supporting_specs=supporting,
            )

    if water_resistance:
        supporting["water resistance"] = water_resistance
        if _contains_any(water_resistance, "not water", "not resistant"):
            return _mk_response(
                detail,
                UseCase.pool_deck,
                ok=False,
                confidence=0.95,
                reason="Spec indicates the product is not water resistant; standing water from a pool deck would damage it.",
                supporting_specs=supporting,
            )

    if dcof:
        supporting["dcof"] = dcof
        dcof_value = _extract_float(dcof)
        if dcof_value is not None:
            if dcof_value >= 0.42:
                return _mk_response(
                    detail,
                    UseCase.pool_deck,
                    ok=True,
                    confidence=0.9,
                    reason="DCOF rating meets wet-area slip guidance (>= 0.42) and product is rated for outdoor use.",
                    supporting_specs=supporting,
                )
            return _mk_response(
                detail,
                UseCase.pool_deck,
                ok=False,
                confidence=0.85,
                reason="DCOF rating below 0.42 indicates the surface may be too slippery for a pool deck.",
                supporting_specs=supporting,
            )

    return _mk_response(
        detail,
        UseCase.pool_deck,
        ok=None,
        confidence=0.4,
        reason="Missing slip or water-resistance data. Confirm outdoor slip rating before installing near pools.",
        supporting_specs=supporting,
    )


def check_kitchen_backsplash(detail: ProductDetail) -> UsageCheckResponse:
    spec_map = build_spec_map(detail)
    supporting: Dict[str, str] = {}

    install = spec_map.get("installation options", "")
    placement = spec_map.get("placement location", "")
    water_resistance = spec_map.get("water resistance", "")

    if install:
        supporting["installation options"] = install
        if "floor only" in install.lower():
            return _mk_response(
                detail,
                UseCase.kitchen_backsplash,
                ok=False,
                confidence=0.95,
                reason="Installation options list floor-only coverage, so mounting on a backsplash is not supported.",
                supporting_specs=supporting,
            )

    if placement:
        supporting["placement location"] = placement

    if install and "wall" in install.lower():
        if placement and "outdoor" in placement.lower():
            return _mk_response(
                detail,
                UseCase.kitchen_backsplash,
                ok=True,
                confidence=0.75,
                reason="Spec lists wall installation; ensure finish suits kitchen cleaning needs.",
                supporting_specs=supporting,
            )
        return _mk_response(
            detail,
            UseCase.kitchen_backsplash,
            ok=True,
            confidence=0.85,
            reason="Installation options explicitly allow wall applications, so a backsplash is supported.",
            supporting_specs=supporting,
        )

    if water_resistance:
        supporting["water resistance"] = water_resistance
        if _contains_any(water_resistance, "not water", "not resistant"):
            return _mk_response(
                detail,
                UseCase.kitchen_backsplash,
                ok=False,
                confidence=0.8,
                reason="Spec warns the finish is not water resistant — repeated cleaning would damage it.",
                supporting_specs=supporting,
            )

    return _mk_response(
        detail,
        UseCase.kitchen_backsplash,
        ok=None,
        confidence=0.4,
        reason="Wall/backsplash install data not found. Verify with manufacturer literature before proceeding.",
        supporting_specs=supporting,
    )


def check_commercial_heavy_floor(detail: ProductDetail) -> UsageCheckResponse:
    spec_map = build_spec_map(detail)
    supporting: Dict[str, str] = {}

    pei = spec_map.get("pei rating", "")
    floor_rating = spec_map.get("floor suitability rating", "")

    if pei:
        supporting["pei rating"] = pei
        pei_value = _extract_float(pei)
        if pei_value is not None:
            if pei_value >= 4:
                return _mk_response(
                    detail,
                    UseCase.commercial_heavy_floor,
                    ok=True,
                    confidence=0.9,
                    reason="PEI rating of 4 or 5 supports heavy commercial foot traffic.",
                    supporting_specs=supporting,
                )
            if pei_value <= 2:
                return _mk_response(
                    detail,
                    UseCase.commercial_heavy_floor,
                    ok=False,
                    confidence=0.95,
                    reason="PEI rating below 3 is intended for light traffic, not heavy commercial areas.",
                    supporting_specs=supporting,
                )

    if floor_rating:
        supporting["floor suitability rating"] = floor_rating
        if _contains_any(floor_rating, "heavy commercial", "commercial"):
            return _mk_response(
                detail,
                UseCase.commercial_heavy_floor,
                ok=True,
                confidence=0.85,
                reason="Floor suitability spec explicitly calls out commercial traffic.",
                supporting_specs=supporting,
            )
        if _contains_any(floor_rating, "residential only", "light", "wall only"):
            return _mk_response(
                detail,
                UseCase.commercial_heavy_floor,
                ok=False,
                confidence=0.9,
                reason="Floor suitability spec limits usage to residential/light areas.",
                supporting_specs=supporting,
            )

    return _mk_response(
        detail,
        UseCase.commercial_heavy_floor,
        ok=None,
        confidence=0.4,
        reason="No PEI or floor rating data found. Request traffic rating before commercial installation.",
        supporting_specs=supporting,
    )


def check_laundry_room_floor(detail: ProductDetail) -> UsageCheckResponse:
    spec_map = build_spec_map(detail)
    supporting: Dict[str, str] = {}

    water = spec_map.get("water resistance", "")
    bathroom = spec_map.get("bathroom floor use", "")
    placement = spec_map.get("placement location", "")

    if water:
        supporting["water resistance"] = water
        if _contains_any(water, "not water", "not resistant"):
            return _mk_response(
                detail,
                UseCase.laundry_room_floor,
                ok=False,
                confidence=0.9,
                reason="Spec says the product is not water resistant—laundry leaks would damage it.",
                supporting_specs=supporting,
            )

    if bathroom:
        supporting["bathroom floor use"] = bathroom
        if _contains_any(bathroom, "not suitable"):
            return _mk_response(
                detail,
                UseCase.laundry_room_floor,
                ok=False,
                confidence=0.9,
                reason="Bathroom floor spec is negative, so another wet room like a laundry is unsafe.",
                supporting_specs=supporting,
            )
        if _contains_any(bathroom, "suitable", "yes"):
            return _mk_response(
                detail,
                UseCase.laundry_room_floor,
                ok=True,
                confidence=0.85,
                reason="Bathroom floor suitability implies it can handle occasional laundry moisture.",
                supporting_specs=supporting,
            )

    if placement:
        supporting["placement location"] = placement
        if "indoor" in placement.lower():
            return _mk_response(
                detail,
                UseCase.laundry_room_floor,
                ok=True,
                confidence=0.6,
                reason="Indoor placement is allowed, but confirm water resistance for laundry spill tolerance.",
                supporting_specs=supporting,
            )

    return _mk_response(
        detail,
        UseCase.laundry_room_floor,
        ok=None,
        confidence=0.3,
        reason="Could not find wet-area data. Seal or choose a known water-resistant material for laundry rooms.",
        supporting_specs=supporting,
    )


def check_basement_floor(detail: ProductDetail) -> UsageCheckResponse:
    spec_map = build_spec_map(detail)
    supporting: Dict[str, str] = {}

    placement = spec_map.get("placement location", "")
    water = spec_map.get("water resistance", "")
    absorption = spec_map.get("water absorption", "")

    if placement:
        supporting["placement location"] = placement
        if "indoor" not in placement.lower():
            return _mk_response(
                detail,
                UseCase.basement_floor,
                ok=False,
                confidence=0.8,
                reason="Placement spec does not mention indoor/below-grade installs.",
                supporting_specs=supporting,
            )

    if water:
        supporting["water resistance"] = water
        if _contains_any(water, "not water", "not resistant"):
            return _mk_response(
                detail,
                UseCase.basement_floor,
                ok=False,
                confidence=0.9,
                reason="Spec says the material lacks water resistance, which is risky for basements.",
                supporting_specs=supporting,
            )
        if _contains_any(water, "waterproof", "water resistant", "water-resistent"):
            return _mk_response(
                detail,
                UseCase.basement_floor,
                ok=True,
                confidence=0.8,
                reason="Water-resistance spec supports below-grade moisture swings typical in basements.",
                supporting_specs=supporting,
            )

    if absorption:
        supporting["water absorption"] = absorption
        value = _extract_float(absorption)
        if value is not None and value <= 0.5:
            return _mk_response(
                detail,
                UseCase.basement_floor,
                ok=True,
                confidence=0.75,
                reason="Low water absorption (<0.5%) indicates the tile can handle basement humidity.",
                supporting_specs=supporting,
            )

    return _mk_response(
        detail,
        UseCase.basement_floor,
        ok=None,
        confidence=0.35,
        reason="Need water-resistance or absorption data to judge basement suitability.",
        supporting_specs=supporting,
    )
