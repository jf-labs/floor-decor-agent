import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import product_loader
from .api_products import router as products_router
from .chat_service import ChatRequest, ChatResponse, ChatService
from .models import ProductDetail, UsageCheckRequest, UsageCheckResponse
from .use_case_checks import USE_CASE_CHECKERS

app = FastAPI(title="FND Agent API", version="0.1.0")


def _load_allowed_origins() -> list[str]:
    """
    Build the list of allowed CORS origins.

    Vite's dev server grabs the next free port (for example 5174) when
    5173 is busy, so we allow a few common ports by default and let
    deployments override the list with FND_ALLOWED_ORIGINS.
    """
    env_val = os.getenv("FND_ALLOWED_ORIGINS")
    if env_val:
        return [origin.strip() for origin in env_val.split(",") if origin.strip()]

    dev_hosts = ("127.0.0.1", "localhost")
    dev_ports = ("5173", "5174", "5175")
    return [f"http://{host}:{port}" for host in dev_hosts for port in dev_ports]


origins = _load_allowed_origins()

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
chat_service = ChatService()


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
    if not hasattr(detail, "specs"):
        detail = ProductDetail(**detail)

    checker = USE_CASE_CHECKERS.get(payload.use_case)
    if checker is None:
        raise HTTPException(status_code=400, detail="Unsupported use case")

    return checker(detail)


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest, conn=Depends(get_db)):
    return chat_service.handle_chat(payload, conn)
