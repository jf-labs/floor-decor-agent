from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np
from sentence_transformers import SentenceTransformer

from . import db

BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "data"
EMBEDDING_FILE = DATA_DIR / "product_embeddings.npz"
EMBEDDING_META_FILE = DATA_DIR / "product_embeddings_meta.json"
DEFAULT_MODEL = os.getenv("FND_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

IMPORTANT_SPECS: Sequence[str] = (
    "Bathroom Floor Use",
    "Shower Surface",
    "Shower Wall Use",
    "Placement Location",
    "Water Resistance",
    "Frost Resistance",
    "Radiant Heat Compatible",
    "Installation Options",
    "Installation Type",
    "Material",
)


def _collect_products(conn) -> List[Dict]:
    cur = conn.execute(
        """
        SELECT
            sku,
            name,
            category_slug,
            price_per_sqft,
            price_per_box,
            size_primary,
            color,
            finish
        FROM products
        """
    )
    return [dict(row) for row in cur.fetchall()]


def _collect_spec_map(conn) -> Dict[str, Dict[str, str]]:
    spec_map: Dict[str, Dict[str, str]] = defaultdict(dict)
    placeholders = ",".join("?" for _ in IMPORTANT_SPECS)
    cur = conn.execute(
        f"""
        SELECT sku, spec_key, spec_value
        FROM product_specs
        WHERE spec_key IN ({placeholders})
        """,
        tuple(IMPORTANT_SPECS),
    )
    for row in cur.fetchall():
        spec_map[row["sku"]][row["spec_key"]] = row["spec_value"]
    return spec_map


def _compose_text(product: Dict, specs: Dict[str, str]) -> str:
    parts = [
        f"SKU: {product.get('sku', '').strip()}",
        f"Name: {product.get('name') or 'Unknown'}",
        f"Category: {product.get('category_slug') or 'Unknown'}",
    ]
    if product.get("price_per_sqft"):
        parts.append(f"Price per sqft: {product['price_per_sqft']}")
    if product.get("size_primary"):
        parts.append(f"Size: {product['size_primary']}")
    if product.get("color"):
        parts.append(f"Color: {product['color']}")
    if product.get("finish"):
        parts.append(f"Finish: {product['finish']}")

    for key in IMPORTANT_SPECS:
        value = specs.get(key)
        if value:
            parts.append(f"{key}: {value}")

    return "\n".join(parts)


def build_embedding_index(
    model_name: str = DEFAULT_MODEL,
    batch_size: int = 32,
) -> None:
    """
    Generate (or refresh) the product embedding index.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    conn = db.get_connection()
    try:
        products = _collect_products(conn)
        spec_map = _collect_spec_map(conn)
    finally:
        conn.close()

    if not products:
        raise RuntimeError("No products found in the database; cannot build embeddings.")

    texts: List[str] = []
    skus: List[str] = []
    for product in products:
        sku = product["sku"]
        text = _compose_text(product, spec_map.get(sku, {}))
        texts.append(text)
        skus.append(sku)

    model = SentenceTransformer(model_name)
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=True,
    ).astype(np.float32)

    np.savez_compressed(
        EMBEDDING_FILE,
        vectors=vectors,
        skus=np.array(skus),
    )

    meta = {
        "model_name": model_name,
        "count": len(skus),
        "spec_keys": list(IMPORTANT_SPECS),
        "texts": {sku: text for sku, text in zip(skus, texts)},
    }
    EMBEDDING_META_FILE.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(
        f"Wrote {len(skus)} embeddings to {EMBEDDING_FILE} using model {model_name}.",
        flush=True,
    )


@dataclass
class EmbeddingResult:
    sku: str
    score: float
    text: str


class ProductEmbeddingIndex:
    def __init__(self, model_name: str | None = None):
        if not EMBEDDING_FILE.exists() or not EMBEDDING_META_FILE.exists():
            raise FileNotFoundError(
                "Embedding files not found. Run `python -m app.build_embeddings` "
                "from the backend directory to generate them."
            )

        data = np.load(EMBEDDING_FILE)
        self.vectors = data["vectors"]
        skus = data["skus"]
        # np.load may return arrays of bytes; normalize to str
        self.skus = [sku.decode("utf-8") if isinstance(sku, bytes) else str(sku) for sku in skus]

        meta = json.loads(EMBEDDING_META_FILE.read_text(encoding="utf-8"))
        self.text_map = meta.get("texts", {})
        chosen_model = model_name or meta.get("model_name") or DEFAULT_MODEL
        self.model = SentenceTransformer(chosen_model)

    def search(self, query: str, top_k: int = 5) -> List[EmbeddingResult]:
        if not query.strip() or len(self.skus) == 0:
            return []
        query_vec = self.model.encode(
            [query],
            normalize_embeddings=True,
        )[0]
        scores = self.vectors @ query_vec
        top_indices = np.argsort(scores)[::-1][:top_k]
        results: List[EmbeddingResult] = []
        for idx in top_indices:
            sku = self.skus[idx]
            score = float(scores[idx])
            results.append(
                EmbeddingResult(
                    sku=sku,
                    score=score,
                    text=self.text_map.get(sku, ""),
                )
            )
        return results


_cached_index: ProductEmbeddingIndex | None = None


def get_embedding_index() -> ProductEmbeddingIndex:
    global _cached_index
    if _cached_index is None:
        _cached_index = ProductEmbeddingIndex()
    return _cached_index

