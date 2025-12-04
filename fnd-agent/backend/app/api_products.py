from typing import List
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from .db import get_db
from .models import Product, ProductDetail
from .product_loader import fetch_product_detail, search_products

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
