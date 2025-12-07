import { useEffect, useMemo, useState } from "react";
import type {
  Product,
  ProductDetail,
  UseCase,
  UsageCheckResponse,
} from "./types";

import { searchProducts, getProductDetail, checkUsage } from "./api";
import "./App.css";

const USE_CASE_LABELS: Record<UseCase, string> = {
  bathroom_floor: "Bathroom floor",
  shower_floor: "Shower floor",
  shower_wall: "Shower wall",
  fireplace_surround: "Fireplace surround",
  radiant_heat: "Radiant heat",
};

function confidenceToPercent(c: number): string {
  return `${Math.round(c * 100)}%`;
}

function badgeClass(ok: boolean | null): string {
  if (ok === true) return "badge badge-ok";
  if (ok === false) return "badge badge-bad";
  return "badge badge-unknown";
}

function badgeText(ok: boolean | null): string {
  if (ok === true) return "OK";
  if (ok === false) return "Not recommended";
  return "Unknown / depends";
}

function App() {
  const [query, setQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [results, setResults] = useState<Product[]>([]);
  const [selectedSku, setSelectedSku] = useState<string | null>(null);

  const [detail, setDetail] = useState<ProductDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);

  const [selectedUseCase, setSelectedUseCase] =
    useState<UseCase>("bathroom_floor");
  const [usageResult, setUsageResult] =
    useState<UsageCheckResponse | null>(null);
  const [usageError, setUsageError] = useState<string | null>(null);
  const [isCheckingUsage, setIsCheckingUsage] = useState(false);

  const canCheckUsage = useMemo(
    () => !!selectedSku && !!detail,
    [selectedSku, detail]
  );

  // Automatically load detail when selectedSku changes
  useEffect(() => {
    if (!selectedSku) {
      setDetail(null);
      setUsageResult(null);
      setDetailError(null);
      return;
    }

    (async () => {
      setIsLoadingDetail(true);
      setDetailError(null);
      setUsageResult(null);
      try {
        const d = await getProductDetail(selectedSku);
        setDetail(d);
      } catch (err) {
        setDetailError(
          err instanceof Error ? err.message : "Failed to load product"
        );
      } finally {
        setIsLoadingDetail(false);
      }
    })();
  }, [selectedSku]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsSearching(true);
    setSearchError(null);
    setResults([]);
    setSelectedSku(null);
    setDetail(null);
    setUsageResult(null);

    try {
      const items = await searchProducts(query.trim(), 25);
      setResults(items);
      if (items.length > 0) {
        setSelectedSku(items[0].sku);
      }
    } catch (err) {
      setSearchError(
        err instanceof Error ? err.message : "Search failed"
      );
    } finally {
      setIsSearching(false);
    }
  };

  const handleSelectProduct = (p: Product) => {
    setSelectedSku(p.sku);
  };

  const handleCheckUsage = async () => {
    if (!selectedSku || !detail) return;

    setIsCheckingUsage(true);
    setUsageError(null);
    setUsageResult(null);

    try {
      const res = await checkUsage(selectedSku, selectedUseCase);
      setUsageResult(res);
    } catch (err) {
      setUsageError(
        err instanceof Error ? err.message : "Usage check failed"
      );
    } finally {
      setIsCheckingUsage(false);
    }
  };

  const selectedProduct = useMemo(
    () => results.find((r) => r.sku === selectedSku) ?? detail?.product ?? null,
    [results, selectedSku, detail]
  );

  return (
    <div className="app-root">
      <header className="app-header">
        <div className="app-header-inner">
          <div>
            <h1 className="app-title">FND Agent</h1>
            <p className="app-subtitle">
              San Leandro product usage checker · simple, spec-driven answers.
            </p>
          </div>
          <div className="app-status-dot" title="Backend assumed at :8000">
            ●
          </div>
        </div>
      </header>

      <main className="app-main">
        {/* Left column: search + results */}
        <section className="panel panel-left">
          <h2 className="panel-title">Search products</h2>
          <form className="search-form" onSubmit={handleSearch}>
            <input
              className="input"
              type="text"
              placeholder="Search by name, color, style, SKU..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <button
              className="btn btn-primary"
              type="submit"
              disabled={isSearching || !query.trim()}
            >
              {isSearching ? "Searching..." : "Search"}
            </button>
          </form>
          {searchError && (
            <div className="error-box">
              <span>{searchError}</span>
            </div>
          )}

          <div className="results-list">
            {results.length === 0 && !isSearching && (
              <p className="hint">Start by searching for a product.</p>
            )}
            {results.map((p) => (
              <button
                key={p.sku}
                className={
                  "result-item" +
                  (p.sku === selectedSku ? " result-item-selected" : "")
                }
                type="button"
                onClick={() => handleSelectProduct(p)}
              >
                <div className="result-title">
                  {p.name ?? "(No name)"}{" "}
                  <span className="result-sku">· {p.sku}</span>
                </div>
                <div className="result-meta">
                  <span>{p.category_slug ?? "Unknown category"}</span>
                  {p.price_per_sqft && (
                    <span className="result-price">
                      {p.price_per_sqft.trim()}
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>
        </section>

        {/* Right column: details + usage */}
        <section className="panel panel-right">
          <h2 className="panel-title">Product details & usage</h2>

          {isLoadingDetail && (
            <div className="loading-box">Loading product details…</div>
          )}

          {detailError && (
            <div className="error-box">
              <span>{detailError}</span>
            </div>
          )}

          {!selectedProduct && !isLoadingDetail && (
            <p className="hint">
              Select a product from the left to see its details and usage
              rules.
            </p>
          )}

          {selectedProduct && (
            <div className="detail-card">
              <div className="detail-header">
                <h3 className="detail-name">
                  {selectedProduct.name ?? "(No name)"}
                </h3>
                <span className="detail-sku">SKU {selectedProduct.sku}</span>
              </div>
              <div className="detail-meta-row">
                <span>
                  Category:{" "}
                  <strong>
                    {selectedProduct.category_slug ?? "Unknown"}
                  </strong>
                </span>
                {selectedProduct.size_primary && (
                  <span>
                    Size:{" "}
                    <strong>{selectedProduct.size_primary}</strong>
                  </span>
                )}
              </div>
              <div className="detail-meta-row">
                {selectedProduct.price_per_sqft && (
                  <span>
                    {selectedProduct.price_per_sqft}
                    {selectedProduct.price_per_box && " · "}
                  </span>
                )}
                {selectedProduct.price_per_box && (
                  <span>{selectedProduct.price_per_box}</span>
                )}
              </div>
              {selectedProduct.url && (
                <div className="detail-link-row">
                  <a
                    href={selectedProduct.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    View on Floor &amp; Decor ↗
                  </a>
                </div>
              )}
            </div>
          )}

          {/* Usage checker */}
          {selectedProduct && (
            <div className="usage-card">
              <div className="usage-header">
                <h3>Usage checker</h3>
                <p className="usage-subtitle">
                  Choose a scenario and check if this SKU is suitable, based on
                  scraped specs.
                </p>
              </div>

              <div className="usecase-row">
                <span className="usecase-label">Use case:</span>
                <div className="usecase-buttons">
                  {(Object.keys(USE_CASE_LABELS) as UseCase[]).map((uc) => (
                    <button
                      key={uc}
                      type="button"
                      className={
                        "pill" +
                        (uc === selectedUseCase ? " pill-active" : "")
                      }
                      onClick={() => setSelectedUseCase(uc)}
                    >
                      {USE_CASE_LABELS[uc]}
                    </button>
                  ))}
                </div>
              </div>

              <div className="usage-actions">
                <button
                  className="btn btn-primary"
                  type="button"
                  disabled={!canCheckUsage || isCheckingUsage}
                  onClick={handleCheckUsage}
                >
                  {isCheckingUsage
                    ? "Checking..."
                    : "Check this product for this use"}
                </button>
              </div>

              {usageError && (
                <div className="error-box">
                  <span>{usageError}</span>
                </div>
              )}

              {usageResult && (
                <div className="usage-result">
                  <div className="usage-summary-row">
                    <span className={badgeClass(usageResult.ok)}>
                      {badgeText(usageResult.ok)}
                    </span>
                    <span className="usage-meta">
                      Confidence:{" "}
                      {confidenceToPercent(usageResult.confidence)}
                    </span>
                  </div>
                  <p className="usage-reason">{usageResult.reason}</p>

                  {Object.keys(usageResult.supporting_specs).length > 0 && (
                    <div className="usage-specs">
                      <h4>Supporting specs</h4>
                      <ul>
                        {Object.entries(
                          usageResult.supporting_specs
                        ).map(([key, value]) => (
                          <li key={key}>
                            <span className="spec-key">{key}</span>
                            <span className="spec-value">{value}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
