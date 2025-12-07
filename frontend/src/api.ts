import type {
  Product,
  ProductDetail,
  UseCase,
  UsageCheckResponse,
} from "./types";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
  }
  return res.json();
}

export async function searchProducts(
  query: string,
  limit = 20
): Promise<Product[]> {
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
  });
  const res = await fetch(`${API_BASE}/products?${params.toString()}`);
  return handle<Product[]>(res);
}

export async function getProductDetail(
  sku: string
): Promise<ProductDetail> {
  const res = await fetch(`${API_BASE}/products/${sku}`);
  return handle<ProductDetail>(res);
}

export async function checkUsage(
  sku: string,
  useCase: UseCase
): Promise<UsageCheckResponse> {
  const res = await fetch(`${API_BASE}/products/${sku}/usage`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ use_case: useCase }),
  });
  return handle<UsageCheckResponse>(res);
}
