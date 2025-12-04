from typing import List
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from .db import get_db
from .models import Product, ProductDetail, UsageCheckRequest, UsageCheckResponse
from .product_loader import fetch_product_detail, search_products
from . import rules_engine

router = APIRouter()


@router.get("/{sku}", response_model=ProductDetail)
def get_product(
    sku: str,
    db: sqlite3.Connection = Depends(get_db),
) -> ProductDetail:
    try:
        return fetch_product_detail(db, sku)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"SKU {sku} not found")


@router.get("", response_model=List[Product])
def search(
    q: str,
    limit: int = 20,
    db: sqlite3.Connection = Depends(get_db),
) -> List[Product]:
    return search_products(db, q, limit)

@router.post("/{sku}/usage", response_model=UsageCheckResponse)
def check_usage(
    sku: str,
    payload: UsageCheckRequest,
    db: sqlite3.Connection = Depends(get_db),
) -> UsageCheckResponse:
    """
    Check a specific usage scenario for a SKU.
    First supported use_case: 'bathroom_floor'.
    """
    try:
        detail: ProductDetail = fetch_product_detail(db, sku)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"SKU {sku} not found")

    if payload.use_case == "bathroom_floor":
        return rules_engine.check_bathroom_floor(detail)

    raise HTTPException(status_code=400, detail="Unsupported use_case")