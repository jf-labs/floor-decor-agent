from enum import Enum
from typing import Dict, List, Optional

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
    product: Product
    specs: List[ProductSpec]
    documents: List[ProductDocument]
    recommended_items: List[ProductRecommendedItem]


class UseCase(str, Enum):
    bathroom_floor = "bathroom_floor"
    shower_floor = "shower_floor"
    shower_wall = "shower_wall"
    fireplace_surround = "fireplace_surround"
    radiant_heat = "radiant_heat"
    outdoor_patio = "outdoor_patio"
    pool_deck = "pool_deck"
    kitchen_backsplash = "kitchen_backsplash"
    commercial_heavy_floor = "commercial_heavy_floor"
    laundry_room_floor = "laundry_room_floor"
    basement_floor = "basement_floor"
    steam_shower_enclosure = "steam_shower_enclosure"
    outdoor_kitchen_counter = "outdoor_kitchen_counter"
    garage_workshop_floor = "garage_workshop_floor"
    driveway_paver = "driveway_paver"
    stair_tread = "stair_tread"
    commercial_kitchen_floor = "commercial_kitchen_floor"
    pool_interior = "pool_interior"
    exterior_wall_cladding = "exterior_wall_cladding"


class UsageCheckRequest(BaseModel):
    use_case: UseCase


class UsageCheckResponse(BaseModel):
    sku: str
    use_case: UseCase
    ok: Optional[bool]
    confidence: float
    reason: str
    supporting_specs: Dict[str, str]
