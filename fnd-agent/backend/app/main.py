from fastapi import FastAPI

from .api_products import router as products_router

app = FastAPI(title="FND Agent API", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


# mount product endpoints at /products
app.include_router(products_router, prefix="/products", tags=["products"])
