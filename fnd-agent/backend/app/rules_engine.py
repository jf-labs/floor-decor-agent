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
    mixed = re.search(r"(-?\d+)\s+(\d+)\s*/\s*(\d+)", normalized)
    if mixed:
        try:
            whole = float(mixed.group(1))
            numerator = float(mixed.group(2))
            denominator = float(mixed.group(3))
            if denominator != 0:
                return whole + (numerator / denominator if whole >= 0 else -numerator / denominator)
        except ValueError:
            pass
    frac = re.search(r"(-?\d+)\s*/\s*(\d+)", normalized)
    if frac:
        try:
            numerator = float(frac.group(1))
            denominator = float(frac.group(2))
            if denominator != 0:
                return numerator / denominator
        except ValueError:
            pass
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


def check_steam_shower_enclosure(detail: ProductDetail) -> UsageCheckResponse:
    spec_map = build_spec_map(detail)
    supporting: Dict[str, str] = {}

    shower_surface = spec_map.get("shower surface", "")
    water_absorption = spec_map.get("water absorption", "")
    water_resistance = spec_map.get("water resistance", "")
    placement = spec_map.get("placement location", "")

    wall_ready = False
    if shower_surface:
        supporting["shower surface"] = shower_surface
        low = shower_surface.lower()
        if "not suitable for shower walls" in low:
            return _mk_response(
                detail,
                UseCase.steam_shower_enclosure,
                ok=False,
                confidence=0.95,
                reason="Spec explicitly says the product is not suitable for shower walls.",
                supporting_specs=supporting,
            )
        if "suitable for shower walls" in low or "wet walls" in low:
            wall_ready = True

    dense = False
    if water_absorption:
        supporting["water absorption"] = water_absorption
        abs_val = _extract_float(water_absorption)
        if abs_val is not None:
            if abs_val <= 0.5:
                dense = True
            elif abs_val > 3:
                return _mk_response(
                    detail,
                    UseCase.steam_shower_enclosure,
                    ok=False,
                    confidence=0.9,
                    reason="Water absorption is high, which risks steam-room saturation.",
                    supporting_specs=supporting,
                )

    if water_resistance:
        supporting["water resistance"] = water_resistance
        if _contains_any(water_resistance, "not water", "not resistant", "not recommended"):
            return _mk_response(
                detail,
                UseCase.steam_shower_enclosure,
                ok=False,
                confidence=0.9,
                reason="Spec indicates the material is not water resistant enough for a steam enclosure.",
                supporting_specs=supporting,
            )

    if placement:
        supporting["placement location"] = placement

    if wall_ready and dense and water_resistance:
        return _mk_response(
            detail,
            UseCase.steam_shower_enclosure,
            ok=True,
            confidence=0.85,
            reason="Low water absorption and shower-wall suitability indicate it can handle steam enclosures.",
            supporting_specs=supporting,
        )

    if wall_ready or dense:
        return _mk_response(
            detail,
            UseCase.steam_shower_enclosure,
            ok=None,
            confidence=0.5,
            reason="Missing either dense body or explicit shower-wall approval needed for a steam enclosure.",
            supporting_specs=supporting,
        )

    return _mk_response(
        detail,
        UseCase.steam_shower_enclosure,
        ok=None,
        confidence=0.2,
        reason="Could not confirm shower-wall suitability or water absorption for steam use.",
        supporting_specs=supporting,
    )


def check_outdoor_kitchen_counter(detail: ProductDetail) -> UsageCheckResponse:
    spec_map = build_spec_map(detail)
    supporting: Dict[str, str] = {}

    placement = spec_map.get("placement location", "")
    fireplace = spec_map.get("fireplace surround use", "")
    water_resistance = spec_map.get("water resistance", "")
    material = spec_map.get("material", "")

    outdoor_ready = False
    if placement:
        supporting["placement location"] = placement
        low = placement.lower()
        if "indoor only" in low:
            return _mk_response(
                detail,
                UseCase.outdoor_kitchen_counter,
                ok=False,
                confidence=0.9,
                reason="Placement spec restricts installation to indoor areas only.",
                supporting_specs=supporting,
            )
        if "outdoor" in low or "exterior" in low:
            outdoor_ready = True

    fire_safe = False
    if fireplace:
        supporting["fireplace surround use"] = fireplace
        low = fireplace.lower()
        if "no" in low or "not suitable" in low:
            return _mk_response(
                detail,
                UseCase.outdoor_kitchen_counter,
                ok=False,
                confidence=0.95,
                reason="Spec indicates it is not safe around fireplace heat, so grills/outdoor kitchens are risky.",
                supporting_specs=supporting,
            )
        if "yes" in low or "suitable" in low:
            fire_safe = True

    if water_resistance:
        supporting["water resistance"] = water_resistance
        if _contains_any(water_resistance, "not water", "not resistant", "not recommended"):
            return _mk_response(
                detail,
                UseCase.outdoor_kitchen_counter,
                ok=False,
                confidence=0.9,
                reason="Spec calls out poor water resistance, which is unsuitable for uncovered outdoor counters.",
                supporting_specs=supporting,
            )

    if material:
        supporting["material"] = material

    if outdoor_ready and fire_safe:
        return _mk_response(
            detail,
            UseCase.outdoor_kitchen_counter,
            ok=True,
            confidence=0.85,
            reason="Outdoor placement and fireplace/heat rating suggest it can handle an outdoor kitchen.",
            supporting_specs=supporting,
        )

    if outdoor_ready or fire_safe:
        return _mk_response(
            detail,
            UseCase.outdoor_kitchen_counter,
            ok=None,
            confidence=0.45,
            reason="Need both outdoor weathering and heat resistance confirmed for an outdoor counter.",
            supporting_specs=supporting,
        )

    return _mk_response(
        detail,
        UseCase.outdoor_kitchen_counter,
        ok=None,
        confidence=0.25,
        reason="Missing data about outdoor rating and high-heat tolerance for outdoor kitchens.",
        supporting_specs=supporting,
    )


def check_garage_workshop_floor(detail: ProductDetail) -> UsageCheckResponse:
    spec_map = build_spec_map(detail)
    supporting: Dict[str, str] = {}

    placement = spec_map.get("placement location", "")
    installation = spec_map.get("installation options", "")
    water_resistance = spec_map.get("water resistance", "")
    pei = spec_map.get("pei rating", "")
    floor_rating = spec_map.get("floor suitability rating", "")
    dcof = spec_map.get("dcof value", "") or spec_map.get("dcof", "")

    if placement:
        supporting["placement location"] = placement
        if "wall only" in placement.lower():
            return _mk_response(
                detail,
                UseCase.garage_workshop_floor,
                ok=False,
                confidence=0.95,
                reason="Placement spec limits this product to walls only, not floors.",
                supporting_specs=supporting,
            )

    if installation:
        supporting["installation options"] = installation
        if "wall only" in installation.lower():
            return _mk_response(
                detail,
                UseCase.garage_workshop_floor,
                ok=False,
                confidence=0.95,
                reason="Installation options do not include flooring applications.",
                supporting_specs=supporting,
            )

    if water_resistance:
        supporting["water resistance"] = water_resistance
        if _contains_any(water_resistance, "not water", "not resistant", "not recommended"):
            return _mk_response(
                detail,
                UseCase.garage_workshop_floor,
                ok=False,
                confidence=0.9,
                reason="Spec warns that liquids will damage the surface—garage spills are common.",
                supporting_specs=supporting,
            )

    if dcof:
        supporting["dcof"] = dcof
        value = _extract_float(dcof)
        if value is not None and value < 0.42:
            return _mk_response(
                detail,
                UseCase.garage_workshop_floor,
                ok=False,
                confidence=0.85,
                reason="DCOF is below wet-area guidance, making garage slip hazards likely.",
                supporting_specs=supporting,
            )

    heavy_rating = False
    if floor_rating:
        supporting["floor suitability rating"] = floor_rating
        if _contains_any(floor_rating, "heavy", "commercial", "garage"):
            heavy_rating = True

    pei_ready = False
    if pei:
        supporting["pei rating"] = pei
        pei_val = _extract_float(pei)
        if pei_val is not None and pei_val >= 4:
            pei_ready = True
        elif pei_val is not None and pei_val <= 2:
            return _mk_response(
                detail,
                UseCase.garage_workshop_floor,
                ok=False,
                confidence=0.9,
                reason="PEI rating is for light traffic, not the abrasion of a workshop.",
                supporting_specs=supporting,
            )

    if (pei_ready or heavy_rating) and water_resistance and (not dcof or _extract_float(dcof) is None or _extract_float(dcof) >= 0.42):
        return _mk_response(
            detail,
            UseCase.garage_workshop_floor,
            ok=True,
            confidence=0.8,
            reason="Traffic rating and water resistance indicate it can handle garage/workshop abuse.",
            supporting_specs=supporting,
        )

    return _mk_response(
        detail,
        UseCase.garage_workshop_floor,
        ok=None,
        confidence=0.35,
        reason="Need high traffic rating, slip data, and water resistance to recommend garages/workshops.",
        supporting_specs=supporting,
    )


def check_driveway_paver(detail: ProductDetail) -> UsageCheckResponse:
    spec_map = build_spec_map(detail)
    supporting: Dict[str, str] = {}

    placement = spec_map.get("placement location", "")
    thickness = spec_map.get("product thickness", "")
    frost = spec_map.get("frost resistance", "")
    water_absorption = spec_map.get("water absorption", "")

    outdoor_ready = False
    if placement:
        supporting["placement location"] = placement
        low = placement.lower()
        if "indoor only" in low:
            return _mk_response(
                detail,
                UseCase.driveway_paver,
                ok=False,
                confidence=0.9,
                reason="Placement spec restricts use to indoor areas.",
                supporting_specs=supporting,
            )
        if "outdoor" in low or "exterior" in low:
            outdoor_ready = True

    thickness_val = None
    if thickness:
        supporting["product thickness"] = thickness
        thickness_val = _extract_float(thickness)
        if thickness_val is not None and thickness_val < 1:
            return _mk_response(
                detail,
                UseCase.driveway_paver,
                ok=False,
                confidence=0.9,
                reason="Product thickness is under 1\", which is too thin for vehicle loads.",
                supporting_specs=supporting,
            )

    frost_ok = False
    if frost:
        supporting["frost resistance"] = frost
        if _contains_any(frost, "no", "not resistant"):
            return _mk_response(
                detail,
                UseCase.driveway_paver,
                ok=False,
                confidence=0.9,
                reason="Spec indicates the paver is not frost resistant, which a driveway requires.",
                supporting_specs=supporting,
            )
        if _contains_any(frost, "yes", "resistant", "rated"):
            frost_ok = True

    dense = False
    if water_absorption:
        supporting["water absorption"] = water_absorption
        abs_val = _extract_float(water_absorption)
        if abs_val is not None and abs_val <= 0.5:
            dense = True

    if outdoor_ready and thickness_val is not None and thickness_val >= 1.25 and (frost_ok or dense):
        return _mk_response(
            detail,
            UseCase.driveway_paver,
            ok=True,
            confidence=0.85,
            reason="Thickness and freeze-thaw data indicate it can support vehicle traffic.",
            supporting_specs=supporting,
        )

    return _mk_response(
        detail,
        UseCase.driveway_paver,
        ok=None,
        confidence=0.35,
        reason="Need outdoor rating plus thick, frost-resistant specs to approve driveway installs.",
        supporting_specs=supporting,
    )


def check_stair_tread(detail: ProductDetail) -> UsageCheckResponse:
    spec_map = build_spec_map(detail)
    supporting: Dict[str, str] = {}

    installation = spec_map.get("installation options", "")
    placement = spec_map.get("placement location", "")
    thickness = spec_map.get("product thickness", "")
    floor_rating = spec_map.get("floor suitability rating", "")

    floor_allowed = False
    if installation:
        supporting["installation options"] = installation
        low = installation.lower()
        if "wall only" in low:
            return _mk_response(
                detail,
                UseCase.stair_tread,
                ok=False,
                confidence=0.9,
                reason="Installation options call out wall-only applications, not stairs.",
                supporting_specs=supporting,
            )
        if "floor" in low:
            floor_allowed = True

    if placement:
        supporting["placement location"] = placement

    thickness_val = None
    if thickness:
        supporting["product thickness"] = thickness
        thickness_val = _extract_float(thickness)
        if thickness_val is not None and thickness_val < 0.3:
            return _mk_response(
                detail,
                UseCase.stair_tread,
                ok=False,
                confidence=0.85,
                reason="Material thinner than 0.3\" is prone to breaking on stair nosings.",
                supporting_specs=supporting,
            )

    if floor_rating:
        supporting["floor suitability rating"] = floor_rating
        if _contains_any(floor_rating, "wall only", "light wall"):
            return _mk_response(
                detail,
                UseCase.stair_tread,
                ok=False,
                confidence=0.9,
                reason="Floor suitability rating does not allow foot traffic needed for stairs.",
                supporting_specs=supporting,
            )

    if floor_allowed and (thickness_val is None or thickness_val >= 0.375):
        return _mk_response(
            detail,
            UseCase.stair_tread,
            ok=True,
            confidence=0.7,
            reason="Installation options include floors and thickness appears adequate for stair nosings.",
            supporting_specs=supporting,
        )

    return _mk_response(
        detail,
        UseCase.stair_tread,
        ok=None,
        confidence=0.3,
        reason="Need explicit stair trim or structural thickness to confirm suitability.",
        supporting_specs=supporting,
    )


def check_commercial_kitchen_floor(detail: ProductDetail) -> UsageCheckResponse:
    spec_map = build_spec_map(detail)
    supporting: Dict[str, str] = {}

    water_resistance = spec_map.get("water resistance", "")
    pei = spec_map.get("pei rating", "")
    floor_rating = spec_map.get("floor suitability rating", "")
    dcof = spec_map.get("dcof value", "") or spec_map.get("dcof", "")
    material = spec_map.get("material", "")

    if material:
        supporting["material"] = material
        if _contains_any(material, "wood", "bamboo", "cork"):
            return _mk_response(
                detail,
                UseCase.commercial_kitchen_floor,
                ok=False,
                confidence=0.95,
                reason="Wood/bio-based materials are not recommended for wet, greasy commercial kitchens.",
                supporting_specs=supporting,
            )

    if water_resistance:
        supporting["water resistance"] = water_resistance
        if _contains_any(water_resistance, "not water", "not resistant", "not recommended"):
            return _mk_response(
                detail,
                UseCase.commercial_kitchen_floor,
                ok=False,
                confidence=0.9,
                reason="Spec says the surface does not tolerate water/chemicals—bad fit for commercial kitchens.",
                supporting_specs=supporting,
            )

    if dcof:
        supporting["dcof"] = dcof
        value = _extract_float(dcof)
        if value is not None and value < 0.5:
            return _mk_response(
                detail,
                UseCase.commercial_kitchen_floor,
                ok=False,
                confidence=0.9,
                reason="DCOF is below the 0.50 wet-slip guideline for commercial kitchens.",
                supporting_specs=supporting,
            )

    pei_ready = False
    if pei:
        supporting["pei rating"] = pei
        pei_val = _extract_float(pei)
        if pei_val is not None and pei_val >= 4:
            pei_ready = True
        elif pei_val is not None and pei_val <= 2:
            return _mk_response(
                detail,
                UseCase.commercial_kitchen_floor,
                ok=False,
                confidence=0.9,
                reason="PEI rating is too light for high-traffic commercial kitchens.",
                supporting_specs=supporting,
            )

    commercial_flag = False
    if floor_rating:
        supporting["floor suitability rating"] = floor_rating
        if _contains_any(floor_rating, "commercial", "heavy", "restaurant"):
            commercial_flag = True
        if _contains_any(floor_rating, "residential only", "wall"):
            return _mk_response(
                detail,
                UseCase.commercial_kitchen_floor,
                ok=False,
                confidence=0.9,
                reason="Floor suitability rating limits the product to residential/light use.",
                supporting_specs=supporting,
            )

    if pei_ready and commercial_flag and (not dcof or _extract_float(dcof) is None or _extract_float(dcof) >= 0.5):
        return _mk_response(
            detail,
            UseCase.commercial_kitchen_floor,
            ok=True,
            confidence=0.85,
            reason="Traffic, slip, and water-resistance specs align with commercial kitchen demands.",
            supporting_specs=supporting,
        )

    return _mk_response(
        detail,
        UseCase.commercial_kitchen_floor,
        ok=None,
        confidence=0.35,
        reason="Need explicit commercial traffic, slip, and water-proof specs for kitchen approval.",
        supporting_specs=supporting,
    )


def check_pool_interior(detail: ProductDetail) -> UsageCheckResponse:
    spec_map = build_spec_map(detail)
    supporting: Dict[str, str] = {}

    water_absorption = spec_map.get("water absorption", "")
    water_resistance = spec_map.get("water resistance", "")
    placement = spec_map.get("placement location", "")
    frost = spec_map.get("frost resistance", "")

    if water_absorption:
        supporting["water absorption"] = water_absorption
        abs_val = _extract_float(water_absorption)
        if abs_val is not None and abs_val > 3:
            return _mk_response(
                detail,
                UseCase.pool_interior,
                ok=False,
                confidence=0.95,
                reason="Water absorption is too high for constant submersion.",
                supporting_specs=supporting,
            )
        if abs_val is not None and abs_val <= 0.5:
            dense = True
        else:
            dense = False
    else:
        dense = False

    if water_resistance:
        supporting["water resistance"] = water_resistance
        if _contains_any(water_resistance, "not water", "not resistant", "not recommended"):
            return _mk_response(
                detail,
                UseCase.pool_interior,
                ok=False,
                confidence=0.9,
                reason="Spec explicitly says it is not water resistant—cannot be submerged.",
                supporting_specs=supporting,
            )
    water_positive = water_resistance != "" and not _contains_any(
        water_resistance, "not water", "not resistant", "not recommended"
    )

    exterior_flag = False
    if placement:
        supporting["placement location"] = placement
        if "outdoor" in placement.lower() or "exterior" in placement.lower():
            exterior_flag = True

    frost_ok = False
    if frost:
        supporting["frost resistance"] = frost
        if _contains_any(frost, "no", "not resistant"):
            return _mk_response(
                detail,
                UseCase.pool_interior,
                ok=False,
                confidence=0.9,
                reason="Lack of frost resistance risks cracking in freeze/thaw pool environments.",
                supporting_specs=supporting,
            )
        if _contains_any(frost, "yes", "resistant", "rated"):
            frost_ok = True

    if dense and water_positive and (frost_ok or exterior_flag):
        return _mk_response(
            detail,
            UseCase.pool_interior,
            ok=True,
            confidence=0.8,
            reason="Low absorption and water/frost resistance indicate it can stay submerged.",
            supporting_specs=supporting,
        )

    return _mk_response(
        detail,
        UseCase.pool_interior,
        ok=None,
        confidence=0.3,
        reason="Need dense body and submersion-rated specs to approve pool interiors.",
        supporting_specs=supporting,
    )


def check_exterior_wall_cladding(detail: ProductDetail) -> UsageCheckResponse:
    spec_map = build_spec_map(detail)
    supporting: Dict[str, str] = {}

    placement = spec_map.get("placement location", "")
    installation = spec_map.get("installation options", "")
    frost = spec_map.get("frost resistance", "")
    water_resistance = spec_map.get("water resistance", "")

    outdoor_flag = False
    if placement:
        supporting["placement location"] = placement
        low = placement.lower()
        if "indoor only" in low:
            return _mk_response(
                detail,
                UseCase.exterior_wall_cladding,
                ok=False,
                confidence=0.9,
                reason="Placement spec restricts the product to interior installs.",
                supporting_specs=supporting,
            )
        if "outdoor" in low or "exterior" in low:
            outdoor_flag = True

    wall_flag = False
    if installation:
        supporting["installation options"] = installation
        low = installation.lower()
        if "wall" in low:
            wall_flag = True
        if "floor only" in low:
            return _mk_response(
                detail,
                UseCase.exterior_wall_cladding,
                ok=False,
                confidence=0.9,
                reason="Installation options limit to floors, not wall cladding.",
                supporting_specs=supporting,
            )

    frost_ok = False
    if frost:
        supporting["frost resistance"] = frost
        if _contains_any(frost, "no", "not resistant"):
            return _mk_response(
                detail,
                UseCase.exterior_wall_cladding,
                ok=False,
                confidence=0.9,
                reason="Spec indicates it cannot handle freeze/thaw on exterior walls.",
                supporting_specs=supporting,
            )
        if _contains_any(frost, "yes", "resistant", "rated"):
            frost_ok = True

    if water_resistance:
        supporting["water resistance"] = water_resistance
        if _contains_any(water_resistance, "not water", "not resistant", "not recommended"):
            return _mk_response(
                detail,
                UseCase.exterior_wall_cladding,
                ok=False,
                confidence=0.9,
                reason="Spec indicates poor water resistance—exterior exposure would cause failure.",
                supporting_specs=supporting,
            )

    if outdoor_flag and wall_flag and (frost_ok or not frost):
        return _mk_response(
            detail,
            UseCase.exterior_wall_cladding,
            ok=True,
            confidence=0.8,
            reason="Outdoor placement plus wall installation instructions indicate façade suitability.",
            supporting_specs=supporting,
        )

    return _mk_response(
        detail,
        UseCase.exterior_wall_cladding,
        ok=None,
        confidence=0.35,
        reason="Need explicit wall install + exterior/frost-resistant specs to approve façade use.",
        supporting_specs=supporting,
    )
