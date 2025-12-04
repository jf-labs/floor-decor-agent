from typing import List
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from .db import get_db
from .models import (
    Product,
    ProductDetail,
    UsageCheckRequest,
    UsageCheckResponse,
    UseCase,
)
from .product_loader import fetch_product_detail, search_products
from . import rules_engine

router = APIRouter()


@router.get("/{sku}", response_model=ProductDetail)
def get_product(
    sku: str,
    db: sqlite3.Connection = Depends(get_db),
) -> ProductDetail:
    """
    Return full product details for a given SKU:
    - core product info
    - specs
    - documents
    - recommended items
    """
    try:
        return fetch_product_detail(db, sku)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"SKU {sku} not found")


@router.get("", response_model=List[Product])
def search_products_endpoint(
    q: str,
    limit: int = 20,
    db: sqlite3.Connection = Depends(get_db),
) -> List[Product]:
    """
    Basic search endpoint:
    /products?q=hickory&limit=20
    """
    return search_products(db, q, limit)


@router.post("/{sku}/usage", response_model=UsageCheckResponse)
def check_usage(
    sku: str,
    payload: UsageCheckRequest,
    db: sqlite3.Connection = Depends(get_db),
) -> UsageCheckResponse:
    """
    Check a specific usage scenario for a SKU.
    use_case is an Enum (UseCase) with values like:
      - bathroom_floor
      - shower_floor
      - shower_wall
      - fireplace_surround
      - radiant_heat
    """
    try:
        detail: ProductDetail = fetch_product_detail(db, sku)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"SKU {sku} not found")

    uc = payload.use_case

    if uc == UseCase.bathroom_floor:
        return rules_engine.check_bathroom_floor(detail)
    if uc == UseCase.shower_floor:
        return rules_engine.check_shower_floor(detail)
    if uc == UseCase.shower_wall:
        return rules_engine.check_shower_wall(detail)
    if uc == UseCase.fireplace_surround:
        return rules_engine.check_fireplace_surround(detail)
    if uc == UseCase.radiant_heat:
        return rules_engine.check_radiant_heat(detail)

    # if we get here, something slipped past validation
    raise HTTPException(status_code=400, detail="Unsupported use_case")
