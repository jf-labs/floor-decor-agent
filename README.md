# Purpose

This project serves as a hands-on exercise to learn and apply system design principles in a practical setting. The goal is to simulate how scalable systems are structured in real-world environments by incorporating concepts such as modular architecture, API orchestration, caching, monitoring, and fault tolerance.

Rather than focusing solely on implementation, this repository emphasizes the translation of high-level design (HLD) diagrams into working modules, documenting architectural decisions, and iteratively refining components based on design patterns used in production systems.

# Problem Statement & Motivation

Retail associates and customers often struggle to find in-stock product alternatives quickly when a desired SKU is unavailable at their local store. This project tackles that problem by designing a system that can retrieve, filter, and recommend substitute products based on inventory, proximity, and relevance — similar to how large retailers optimize their backend systems. By approaching this through a system design lens, the project focuses on how scalable architectures handle real-time data retrieval, caching, and ranking logic to deliver fast, reliable recommendations.

---

## Current Feature Set

- **Product search + detail**: FastAPI endpoints backed by SQLite and the scraped product/spec tables.
- **Rules engine**: Deterministic usage checks for 11+ scenarios (bathroom floor, pool deck, outdoor patio, commercial kitchen, etc.).
- **Hybrid chat assistant**:
  - Left column: legacy search results + “active product” card.
  - Right column: ChatGPT-style interface.
  - Backend orchestrator prompts a local Llama 3 8B (via Ollama), performs retrieval over product embeddings, and can call three tools: `search_products`, `get_product_detail`, `check_usage`.
  - The assistant cites referenced products and runs the rule engine when needed.

---

## Prerequisites

- Python 3.12 + `pip`
- Node 18+ (for the Vite frontend)
- [Ollama](https://ollama.com/) running locally (default host `http://127.0.0.1:11434`)
- A model pulled into Ollama; recommended command:

  ```bash
  ollama pull llama3:8b
  ```

---

## Backend Setup

```bash
cd fnd-agent/backend
python -m venv .venv
. .venv/bin/activate # or .venv\Scripts\Activate.ps1 on Windows
pip install -r ../../requirements.txt
```

### Build the embedding index

The chat assistant performs retrieval over product/spec text. Generate the embeddings after any database refresh:

```bash
cd fnd-agent/backend
python -m app.build_embeddings
```

This writes `data/product_embeddings.npz` and metadata next to the SQLite DB.

### Environment variables

Optional tweaks (can be exported before launching Uvicorn):

- `FND_OLLAMA_MODEL` – defaults to `llama3`.
- `OLLAMA_BASE_URL` – defaults to `http://127.0.0.1:11434`.
- `FND_OLLAMA_TEMPERATURE` – defaults to `0.2`.
- `FND_EMBEDDING_MODEL` – defaults to `sentence-transformers/all-MiniLM-L6-v2`.

### Run the API

```bash
cd fnd-agent/backend
uvicorn app.main:app --reload
```

---

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Vite will start on `http://localhost:5173` (or the next free port). The left column handles SKU search; the right column is the chat interface.

---

## Chat Workflow

1. The user asks a free-form question (e.g., “Can SKU 100787878 go on a pool deck?”).
2. Backend builds retrieval context from the embedding index and the active SKU (if any).
3. Ollama responds with a JSON directive. The orchestrator either:
   - Calls a tool (search/details/usage) and feeds the result back to the model, or
   - Returns a final response grounded in specs.
4. The frontend displays the answer, along with product cards for any referenced SKUs.

If the chat endpoint responds with `400` complaining about missing embeddings, rerun `python -m app.build_embeddings`.

---

## Development Notes

- `tf-keras` is installed as a compatibility shim for `sentence-transformers`. If TensorFlow tries to load and complains, ensure `pip install tf-keras` has been run in the active virtual environment.
- To update embeddings after new data, simply rerun the build script; the backend hot-reloads the cached index on restart.
- The orchestrator intentionally avoids LangChain/LlamaIndex for clarity—logic lives in `app/chat_service.py`.

---

## Next Steps (ideas)

- Add streaming responses from Ollama for more interactive chat.
- Persist chat history per session and allow exporting transcripts.
- Expose additional tools (pricing, inventory, spec comparisons) once the data is available.