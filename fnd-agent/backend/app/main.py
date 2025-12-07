from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import product_loader, rules_engine
from .api_products import router as products_router
from .models import UsageCheckRequest, UsageCheckResponse, UseCase

app = FastAPI(title="FND Agent API", version="0.1.0")

origins = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]

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
    if hasattr(detail, "specs"):
        specs = detail.specs
    else:
        specs = detail["specs"]

    spec_map = rules_engine.build_spec_map(specs)
    uc = payload.use_case

    if uc == UseCase.bathroom_floor:
        result = rules_engine.check_bathroom_floor(spec_map)
    elif uc == UseCase.shower_floor:
        result = rules_engine.check_shower_floor(spec_map)
    elif uc == UseCase.shower_wall:
        result = rules_engine.check_shower_wall(spec_map)
    elif uc == UseCase.fireplace_surround:
        result = rules_engine.check_fireplace_surround(spec_map)
    elif uc == UseCase.radiant_heat:
        result = rules_engine.check_radiant_heat(spec_map)
    else:
        raise HTTPException(status_code=400, detail="Unsupported use case")

    return UsageCheckResponse(
        sku=sku,
        use_case=uc,
        ok=result.ok,
        confidence=result.confidence,
        reason=result.reason,
        supporting_specs=result.supporting_specs,
    )
