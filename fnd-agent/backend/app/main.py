from fastapi import FastAPI, Depends, HTTPException
from . import product_loader, rules_engine, api_products
from .api_products import router as products_router
from .models import UsageCheckRequest, UsageCheckResponse

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


# mount product endpoints at /products
app.include_router(products_router, prefix="/products", tags=["products"])

def get_db():
    # however you're opening the SQLite connection now
    return product_loader.get_connection()


@app.post("/products/{sku}/usage", response_model=UsageCheckResponse)
def check_product_usage(
    sku: str,
    payload: UsageCheckRequest,
    conn=Depends(get_db),
):
    data = product_loader.load_product_with_details(conn, sku)
    if data is None:
        raise HTTPException(status_code=404, detail="Product not found")

    product, specs, docs, recs = data
    spec_map = rules_engine.build_spec_map(specs)

    if payload.use_case == "bathroom_floor":
        result = rules_engine.check_bathroom_floor(spec_map)
    else:
        raise HTTPException(status_code=400, detail="Unsupported use case")

    return UsageCheckResponse(
        sku=product.sku,
        use_case=payload.use_case,
        ok=result.ok,
        confidence=result.confidence,
        reason=result.reason,
        supporting_specs=result.supporting_specs,
    )
