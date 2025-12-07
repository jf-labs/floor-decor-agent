from typing import List
import sqlite3
from pathlib import Path

from .models import (
    Product,
    ProductSpec,
    ProductDocument,
    ProductRecommendedItem,
    ProductDetail,
)

# Path to: C:\Users\j0sep\fnd-agent-1\data\fnd_products.db
DB_PATH = Path(__file__).resolve().parents[3] / "data" / "fnd_products.db"


def get_connection() -> sqlite3.Connection:
    """
    Open a SQLite connection to the fnd_products.db with row_factory set,
    so dict(row) works everywhere.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def fetch_product_detail(db: sqlite3.Connection, sku: str) -> ProductDetail:
    cur = db.cursor()

    # 1) core product
    cur.execute(
        """
        SELECT sku, name, url, category_slug,
               price_per_sqft, price_per_box,
               size_primary, color, finish,
               store_id, last_scraped_at
        FROM products
        WHERE sku = ?
        """,
        (sku,),
    )
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"SKU {sku} not found")

    product = Product(
        sku=row["sku"],
        name=row["name"],
        url=row["url"],
        category_slug=row["category_slug"],
        price_per_sqft=row["price_per_sqft"],
        price_per_box=row["price_per_box"],
        size_primary=row["size_primary"],
        color=row["color"],
        finish=row["finish"],
        store_id=row["store_id"],
        last_scraped_at=row["last_scraped_at"],
    )

    # 2) specs
    cur.execute(
        """
        SELECT spec_key, spec_value
        FROM product_specs
        WHERE sku = ?
        ORDER BY spec_key
        """,
        (sku,),
    )
    specs = [
        ProductSpec(spec_key=r["spec_key"], spec_value=r["spec_value"])
        for r in cur.fetchall()
    ]

    # 3) documents
    cur.execute(
        """
        SELECT doc_label, doc_url
        FROM product_documents
        WHERE sku = ?
        ORDER BY id
        """,
        (sku,),
    )
    docs = [
        ProductDocument(doc_label=r["doc_label"], doc_url=r["doc_url"])
        for r in cur.fetchall()
    ]

    # 4) recommended items (currently empty table, but wired)
    cur.execute(
        """
        SELECT rec_name, rec_url, rec_sku
        FROM product_recommended_items
        WHERE sku = ?
        ORDER BY id
        """,
        (sku,),
    )
    recs = [
        ProductRecommendedItem(
            rec_name=r["rec_name"],
            rec_url=r["rec_url"],
            rec_sku=r["rec_sku"],
        )
        for r in cur.fetchall()
    ]

    return ProductDetail(
        product=product,
        specs=specs,
        documents=docs,
        recommended_items=recs,
    )


def search_products(
    db: sqlite3.Connection,
    q: str,
    limit: int = 20,
) -> List[Product]:
    cur = db.cursor()
    cur.execute(
        """
        SELECT sku, name, url, category_slug,
               price_per_sqft, price_per_box,
               size_primary, color, finish,
               store_id, last_scraped_at
        FROM products
        WHERE LOWER(name) LIKE '%' || LOWER(?) || '%'
        LIMIT ?
        """,
        (q, limit),
    )
    rows = cur.fetchall()
    return [
        Product(
            sku=r["sku"],
            name=r["name"],
            url=r["url"],
            category_slug=r["category_slug"],
            price_per_sqft=r["price_per_sqft"],
            price_per_box=r["price_per_box"],
            size_primary=r["size_primary"],
            color=r["color"],
            finish=r["finish"],
            store_id=r["store_id"],
            last_scraped_at=r["last_scraped_at"],
        )
        for r in rows
    ]
