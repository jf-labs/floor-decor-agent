from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from . import product_loader
from .models import Product, ProductDetail

router = APIRouter()


def get_db():
    conn = product_loader.get_connection()
    try:
        yield conn
    finally:
        conn.close()


@router.get("", response_model=List[Product])
def search_products(
    q: Optional[str] = Query(
        None, description="Search by SKU, name, or category"
    ),
    limit: int = 25,
    conn=Depends(get_db),
):
    """
    Search products by SKU, name, or category_slug.
    Returns a plain list[Product] (no wrapper object).
    """
    sql = """
        SELECT
            sku,
            name,
            url,
            category_slug,
            price_per_sqft,
            price_per_box,
            size_primary,
            color,
            finish,
            store_id,
            last_scraped_at
        FROM products
    """
    params: list = []

    if q:
        q_like = f"%{q}%"
        sql += """
            WHERE
                sku LIKE ?
                OR (name IS NOT NULL AND name LIKE ?)
                OR (category_slug IS NOT NULL AND category_slug LIKE ?)
        """
        params.extend([q_like, q_like, q_like])

    sql += " ORDER BY name LIMIT ?"
    params.append(limit)

    cur = conn.execute(sql, params)
    rows = cur.fetchall()

    return [Product(**dict(row)) for row in rows]


@router.get("/{sku}", response_model=ProductDetail)
def get_product(
    sku: str,
    conn=Depends(get_db),
):
    """
    Get full product details (product + specs + docs + recommended_items).
    """
    detail = product_loader.load_product_with_details(conn, sku)
    if detail is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return detail
