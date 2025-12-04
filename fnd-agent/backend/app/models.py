from typing import Dict, List, Optional, Literal
from pydantic import BaseModel


class Product(BaseModel):
    sku: str
    name: Optional[str] = None
    url: Optional[str] = None
    category_slug: Optional[str] = None
    price_per_sqft: Optional[str] = None
    price_per_box: Optional[str] = None
    size_primary: Optional[str] = None
    color: Optional[str] = None
    finish: Optional[str] = None
    store_id: Optional[int] = None
    last_scraped_at: Optional[str] = None


class ProductSpec(BaseModel):
    spec_key: str
    spec_value: str


class ProductDocument(BaseModel):
    doc_label: str
    doc_url: str


class ProductRecommendedItem(BaseModel):
    rec_name: str
    rec_url: str
    rec_sku: Optional[str] = None


class ProductDetail(BaseModel):
    """
    Full product payload used by /products/{sku}.
    """
    product: Product
    specs: List[ProductSpec]
    documents: List[ProductDocument]
    recommended_items: List[ProductRecommendedItem]


class UsageCheckRequest(BaseModel):
    # we’ll add more use_case options later
    use_case: Literal["bathroom_floor"]


class UsageCheckResponse(BaseModel):
    sku: str
    use_case: str
    ok: Optional[bool]
    confidence: float
    reason: str
    supporting_specs: Dict[str, str]
