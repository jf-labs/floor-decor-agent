export type UseCase =
  | "bathroom_floor"
  | "shower_floor"
  | "shower_wall"
  | "fireplace_surround"
  | "radiant_heat";

export interface Product {
  sku: string;
  name?: string | null;
  url?: string | null;
  category_slug?: string | null;
  price_per_sqft?: string | null;
  price_per_box?: string | null;
  size_primary?: string | null;
  color?: string | null;
  finish?: string | null;
  store_id?: number | null;
  last_scraped_at?: string | null;
}

export interface ProductSpec {
  spec_key: string;
  spec_value: string;
}

export interface ProductDocument {
  doc_label: string;
  doc_url: string;
}

export interface ProductRecommendedItem {
  rec_name: string;
  rec_url: string;
  rec_sku?: string | null;
}

export interface ProductDetail {
  product: Product;
  specs: ProductSpec[];
  documents: ProductDocument[];
  recommended_items: ProductRecommendedItem[];
}

export interface UsageCheckResponse {
  sku: string;
  use_case: UseCase;
  ok: boolean | null;
  confidence: number;
  reason: string;
  supporting_specs: Record<string, string>;
}
