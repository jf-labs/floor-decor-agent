from __future__ import annotations

from typing import Callable, Dict

from . import rules_engine
from .models import ProductDetail, UsageCheckResponse, UseCase

USE_CASE_CHECKERS: Dict[UseCase, Callable[[ProductDetail], UsageCheckResponse]] = {
    UseCase.bathroom_floor: rules_engine.check_bathroom_floor,
    UseCase.shower_floor: rules_engine.check_shower_floor,
    UseCase.shower_wall: rules_engine.check_shower_wall,
    UseCase.fireplace_surround: rules_engine.check_fireplace_surround,
    UseCase.radiant_heat: rules_engine.check_radiant_heat,
    UseCase.outdoor_patio: rules_engine.check_outdoor_patio,
    UseCase.pool_deck: rules_engine.check_pool_deck,
    UseCase.kitchen_backsplash: rules_engine.check_kitchen_backsplash,
    UseCase.commercial_heavy_floor: rules_engine.check_commercial_heavy_floor,
    UseCase.laundry_room_floor: rules_engine.check_laundry_room_floor,
    UseCase.basement_floor: rules_engine.check_basement_floor,
    UseCase.steam_shower_enclosure: rules_engine.check_steam_shower_enclosure,
    UseCase.outdoor_kitchen_counter: rules_engine.check_outdoor_kitchen_counter,
    UseCase.garage_workshop_floor: rules_engine.check_garage_workshop_floor,
    UseCase.driveway_paver: rules_engine.check_driveway_paver,
    UseCase.stair_tread: rules_engine.check_stair_tread,
    UseCase.commercial_kitchen_floor: rules_engine.check_commercial_kitchen_floor,
    UseCase.pool_interior: rules_engine.check_pool_interior,
    UseCase.exterior_wall_cladding: rules_engine.check_exterior_wall_cladding,
}

