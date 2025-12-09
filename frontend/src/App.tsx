import { useEffect, useRef, useState } from "react";
import type {
  Product,
  ProductDetail,
  ChatMessage,
} from "./types";
import { searchProducts, getProductDetail, sendChat } from "./api";
import "./App.css";

const IMPORTANT_SPEC_KEYS = [
  "Bathroom Floor Use",
  "Shower Surface",
  "Placement Location",
  "Water Resistance",
  "Frost Resistance",
  "Radiant Heat Compatible",
  "Installation Options",
  "Installation Type",
  "Material",
];

type ChatMessageWithMeta = ChatMessage & {
  id: string;
  referencedProducts?: ProductDetail[];
};

const createMessageId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;

function toSpecMap(detail: ProductDetail | null) {
  const map: Record<string, string> = {};
  detail?.specs.forEach((spec) => {
    map[spec.spec_key] = spec.spec_value;
  });
  return map;
}

function ProductContextCard({ detail }: { detail: ProductDetail }) {
  const { product } = detail;
  const specMap = toSpecMap(detail);

  return (
    <div className="product-card">
      <div className="product-card-header">
        <div>
          <p className="product-card-name">{product.name ?? "(No name)"}</p>
          <p className="product-card-sku">SKU {product.sku}</p>
        </div>
        {product.category_slug && (
          <span className="product-card-pill">{product.category_slug}</span>
        )}
      </div>
      <ul className="product-card-specs">
        {IMPORTANT_SPEC_KEYS.filter((key) => specMap[key])
          .slice(0, 4)
          .map((key) => (
            <li key={key}>
              <strong>{key}:</strong> {specMap[key]}
            </li>
          ))}
      </ul>
      {product.url && (
        <a className="product-card-link" href={product.url} target="_blank" rel="noreferrer">
          View on Floor &amp; Decor ↗
        </a>
      )}
    </div>
  );
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

  const [messages, setMessages] = useState<ChatMessageWithMeta[]>([
    {
      id: createMessageId(),
      role: "assistant",
      content:
        "Hi! I’m the FND Agent. Ask me about Floor & Decor products, specs, or whether a SKU is safe for a specific use. I can search SKUs, pull details, and run the rules engine for you.",
    },
  ]);
  const [chatInput, setChatInput] = useState("");
  const [chatError, setChatError] = useState<string | null>(null);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const chatContainerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!selectedSku) {
      setDetail(null);
      setDetailError(null);
      return;
    }

    let cancelled = false;
    (async () => {
      setIsLoadingDetail(true);
      setDetailError(null);
      try {
        const nextDetail = await getProductDetail(selectedSku);
        if (!cancelled) {
          setDetail(nextDetail);
        }
      } catch (err) {
        if (!cancelled) {
          setDetailError(err instanceof Error ? err.message : "Failed to load product");
        }
      } finally {
        if (!cancelled) {
          setIsLoadingDetail(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [selectedSku]);

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [messages, isChatLoading]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsSearching(true);
    setSearchError(null);
    setResults([]);

    try {
      const items = await searchProducts(query.trim(), 25);
      setResults(items);
      if (items.length > 0) {
        setSelectedSku(items[0].sku);
      }
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setIsSearching(false);
    }
  };

  const handleSelectProduct = (product: Product) => {
    setSelectedSku(product.sku);
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim()) return;

    const userMessage: ChatMessageWithMeta = {
      id: createMessageId(),
      role: "user",
      content: chatInput.trim(),
    };
    const nextMessages = [...messages, userMessage];
    setMessages(nextMessages);
    setChatInput("");
    setChatError(null);
    setIsChatLoading(true);

    try {
      const payload = {
        messages: nextMessages.map(({ role, content }) => ({ role, content })),
        active_sku: selectedSku,
      };
      const response = await sendChat(payload);
      const assistantMessage: ChatMessageWithMeta = {
        id: createMessageId(),
        role: "assistant",
        content: response.message.content,
        referencedProducts: response.referenced_products,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setChatError(err instanceof Error ? err.message : "Chat request failed");
    } finally {
      setIsChatLoading(false);
    }
  };

  return (
    <div className="app-root">
      <header className="app-header">
        <div className="app-header-inner">
          <div>
            <h1 className="app-title">FND Agent</h1>
            <p className="app-subtitle">
              Hybrid product search + chat assistant powered by Floor &amp; Decor specs.
            </p>
          </div>
          <div className="app-status-dot" title="Backend assumed at :8000">
            ●
          </div>
        </div>
      </header>

      <main className="app-main">
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
            {results.map((product) => (
              <button
                key={product.sku}
                className={
                  "result-item" +
                  (product.sku === selectedSku ? " result-item-selected" : "")
                }
                type="button"
                onClick={() => handleSelectProduct(product)}
              >
                <div className="result-title">
                  {product.name ?? "(No name)"}{" "}
                  <span className="result-sku">· {product.sku}</span>
                </div>
                <div className="result-meta">
                  <span>{product.category_slug ?? "Unknown category"}</span>
                  {product.price_per_sqft && (
                    <span className="result-price">{product.price_per_sqft.trim()}</span>
                  )}
                </div>
              </button>
            ))}
          </div>

          {selectedSku && (
            <div className="active-sku-chip">
              Active SKU: <strong>{selectedSku}</strong>
            </div>
          )}

          {isLoadingDetail && (
            <div className="loading-box">Fetching active product…</div>
          )}

          {detailError && (
            <div className="error-box">
              <span>{detailError}</span>
            </div>
          )}

          {detail && (
            <div className="active-product-card">
              <p className="section-label">Active product</p>
              <ProductContextCard detail={detail} />
            </div>
          )}
        </section>

        <section className="panel panel-right chat-panel">
          <h2 className="panel-title">Chat with FND Agent</h2>
          <div className="chat-history" ref={chatContainerRef}>
            {messages.map((msg) => (
              <div key={msg.id} className={`chat-message chat-${msg.role}`}>
                <div className="chat-bubble">
                  <p>{msg.content}</p>
                </div>
                {msg.referencedProducts && msg.referencedProducts.length > 0 && (
                  <div className="chat-product-stack">
                    {msg.referencedProducts.map((product) => (
                      <ProductContextCard
                        key={`${msg.id}-${product.product.sku}`}
                        detail={product}
                      />
                    ))}
                  </div>
                )}
              </div>
            ))}
            {isChatLoading && (
              <div className="chat-message chat-assistant">
                <div className="chat-bubble chat-bubble-loading">Thinking…</div>
              </div>
            )}
          </div>

          {chatError && (
            <div className="error-box">
              <span>{chatError}</span>
            </div>
          )}

          <form className="chat-input" onSubmit={handleSendMessage}>
            <textarea
              placeholder="Ask a question about specs, usage, or installation…"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              disabled={isChatLoading}
            />
            <button
              className="btn btn-primary"
              type="submit"
              disabled={isChatLoading || !chatInput.trim()}
            >
              {isChatLoading ? "Sending…" : "Send"}
            </button>
          </form>
        </section>
      </main>
    </div>
  );
}

export default App;
