import os
from typing import Callable

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import product_loader, rules_engine
from .api_products import router as products_router
from .models import ProductDetail, UsageCheckRequest, UsageCheckResponse, UseCase

app = FastAPI(title="FND Agent API", version="0.1.0")


def _load_allowed_origins() -> list[str]:
    """
    Build the list of allowed CORS origins.

    Vite's dev server grabs the next free port (for example 5174) when
    5173 is busy, so we allow a few common ports by default and let
    deployments override the list with FND_ALLOWED_ORIGINS.
    """
    env_val = os.getenv("FND_ALLOWED_ORIGINS")
    if env_val:
        return [origin.strip() for origin in env_val.split(",") if origin.strip()]

    dev_hosts = ("127.0.0.1", "localhost")
    dev_ports = ("5173", "5174", "5175")
    return [f"http://{host}:{port}" for host in dev_hosts for port in dev_ports]


origins = _load_allowed_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


# /products: search + detail
app.include_router(products_router, prefix="/products", tags=["products"])

USE_CASE_CHECKERS: dict[UseCase, Callable[[ProductDetail], UsageCheckResponse]] = {
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


def get_db():
    conn = product_loader.get_connection()
    try:
        yield conn
    finally:
        conn.close()


@app.post("/products/{sku}/usage", response_model=UsageCheckResponse)
def check_product_usage(
    sku: str,
    payload: UsageCheckRequest,
    conn=Depends(get_db),
):
    """
    Check whether a product is suitable for a given use case,
    using the scraped specs and rules_engine.
    """
    detail = product_loader.load_product_with_details(conn, sku)
    if detail is None:
        raise HTTPException(status_code=404, detail="Product not found")

    # detail can be a Pydantic ProductDetail or a dict
    if not hasattr(detail, "specs"):
        detail = ProductDetail(**detail)

    checker = USE_CASE_CHECKERS.get(payload.use_case)
    if checker is None:
        raise HTTPException(status_code=400, detail="Unsupported use case")

    return checker(detail)
