from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import product_loader, rules_engine
from .api_products import router as products_router
from .models import UsageCheckRequest, UsageCheckResponse, UseCase


app = FastAPI(title="FND Agent API", version="0.1.0")

# CORS so the Vite frontend (localhost:5173) can call the API
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


# mount product endpoints at /products (search + detail)
app.include_router(products_router, prefix="/products", tags=["products"])


def get_db():
    """Yield a SQLite connection for each request."""
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
    Check whether a product (by SKU) is suitable for a given use case.

    Uses rules_engine.* functions and the scraped specs from SQLite.
    """
    detail = product_loader.load_product_with_details(conn, sku)
    if detail is None:
        raise HTTPException(status_code=404, detail="Product not found")

    uc = payload.use_case

    if uc == UseCase.bathroom_floor:
        result = rules_engine.check_bathroom_floor(detail)
    elif uc == UseCase.shower_floor:
        result = rules_engine.check_shower_floor(detail)
    elif uc == UseCase.shower_wall:
        result = rules_engine.check_shower_wall(detail)
    elif uc == UseCase.fireplace_surround:
        result = rules_engine.check_fireplace_surround(detail)
    elif uc == UseCase.radiant_heat:
        result = rules_engine.check_radiant_heat(detail)
    else:
        # In case you add new enum values but forget to wire them here
        raise HTTPException(status_code=400, detail="Unsupported use case")

    # rules_engine already returns a UsageCheckResponse, so just return it
    return result
