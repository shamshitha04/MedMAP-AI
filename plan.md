# MedMap AI: Master Execution & TDD Plan

## Architectural Overview
- **Backend:** FastAPI (Async) + Uvicorn
- **Ground Truth Database:** SQLite via SQLAlchemy 2.0 (`aiosqlite`)
- **Cloud Vector Engine:** Pinecone Serverless Async SDK (`dotproduct` metric)
- **Frontend:** Next.js + Tailwind + Shadcn UI
- **Testing Engine:** `pytest` + `httpx` (AsyncClient)

---

## Phase 1: Core Infrastructure & Ground Truth (SQLite)
**Objective:** Establish the deterministic local knowledge graph and the API contract.

- [ ] **1.1 Database Setup (`backend/app/models/sql_models.py` & `core/db_setup.py`)**
  - **Action:** Configure `aiosqlite` async engine. Define the `MedicineRecord` SQLAlchemy model with fields: `id`, `brand_name`, `generic_name`, `official_strength`, `form`, and `combination_flag`.
  - **TDD:** Write `tests/test_db.py`. Assert that inserting and retrieving a mock medicine with `combination_flag=True` executes asynchronously without blocking the event loop.
- [ ] **1.2 Pydantic Schemas (`backend/app/models/schemas.py`)**
  - **Action:** Define strict input (`ExtractionRequest`) and output (`ExtractionResponse`, `MatchedMedicine`) models. The response MUST include the `guardrail_logs: List[str]` array.
- [ ] **1.3 API Router (`backend/app/api/routes.py`)**
  - **Action:** Create `POST /extract`. Accept `image_base64` or `raw_text`.
  - **TDD:** Write `tests/test_api.py` using `httpx.AsyncClient`. Send a dummy request and assert a `200 OK` status code.

---

## Phase 2: Ingestion & The "Illusion of Edge"
**Objective:** Handle multi-modal input and build the fail-proof edge cache.

- [ ] **2.1 Hash Cache Intercept (`backend/app/services/extraction_service.py`)**
  - **Action:** Implement a SHA-256 hash check on `image_base64`. If it matches a demo hash, bypass all ML logic and return `backend/app/cache/golden_responses.json`.
  - **TDD:** Fire a known demo image via `httpx`. Assert response time is `< 50ms` and the returned payload matches the golden cache.
- [ ] **2.2 VLM/NLP Extraction (`backend/app/services/extraction_service.py`)**
  - **Action:** Integrate OpenAI `gpt-4o-mini` using `client.beta.chat.completions.parse()` to enforce the Pydantic JSON structure for images. Use local DeBERTa for raw text.



---

## Phase 3: 🟢 Phase 1 XAI Guardrails (Pre-Match)
**Objective:** Protect the system from input ambiguity before generating vector embeddings.

- [ ] **3.1 Variant Separation & Normalization (`backend/app/services/guardrail_service.py`)**
  - **Action:** Write `apply_pre_match_guardrails()`. Inspect the extracted brand name for numeric tokens. If found (e.g., "625"), move it to `brand_variant` and set `strength=None`. Normalize all text (e.g., lowercase, "Tab" -> "Tablet").
  - **TDD:** Pass `"Augmentin 625 Tab"` to the function. Assert the output is `{brand: "augmentin", variant: "625", form: "tablet"}` and that `"Variant token stripped"` is appended to `guardrail_logs`.

---

## Phase 4: Pinecone Async Hybrid Retrieval
**Objective:** Perform the semantic/lexical similarity search via the cloud vector index.

- [ ] **4.1 Vector Generation (`backend/app/services/search_service.py`)**
  - **Action:** Generate dense vectors using `all-MiniLM-L6-v2`. Generate sparse vectors using `pinecone_text.sparse.BM25Encoder` to capture exact lexical tokens.
- [ ] **4.2 Async Pinecone Query (`backend/app/services/search_service.py`)**
  - **Action:** Pass both sparse and dense vectors to the Pinecone `query` method. Pinecone natively handles the `alpha` weighting to enforce the **Sparse Penalty Rule** (down-ranking mismatched variants).
- [ ] **4.3 Bayesian Prescriber Priors**
  - **Action:** If `prescriber_id` exists, query SQLite for historical ID mappings and artificially boost that candidate's similarity score.

---

## Phase 5: 🟡 Phase 2 XAI Guardrails (Post-Match)
**Objective:** Enforce the final deterministic lock and compile the audit trail.



- [ ] **5.1 Deterministic Locking (`backend/app/services/guardrail_service.py`)**
  - **Action:** Write `apply_post_match_guardrails()`. Compare the Top-1 Pinecone result against the local SQLite ground truth.
  - **Rules to Enforce:**
    - **Combination Lock:** If SQLite `combination_flag == True`, prevent component splitting.
    - **Form Penalty:** Penalize score heavily if physical forms mismatch.
    - **Strength Injection:** Overwrite any extracted strength with the SQLite `official_strength`.
- [ ] **5.2 Confidence & Output Delivery**
  - **Action:** Convert the final score to a risk tier ("High", "Medium", "Low"). Compile all Phase 1 and Phase 2 actions into the `guardrail_logs` array.
  - **TDD (End-to-End Integration):** Feed `"Amoxiclav 625"` through the full pipeline. Assert the final JSON exactly matches the Grounded Output Spec, confirming `official_strength` was injected and the logs are populated.

---

## Phase 6: Frontend Simulation UI
**Objective:** Build the Next.js "Show, Don't Tell" visual interface.

- [ ] **6.1 Next.js & Shadcn Components (`frontend/src/components/custom/SplitScreenUI.tsx`)**
  - **Action:** Build the dual-pane UI using Shadcn Cards and Tabs. Ensure the API URL points to `NEXT_PUBLIC_API_URL` (`http://127.0.0.1:8000/extract`).
- [ ] **6.2 The Confusion Simulation Render**
  - **Action:** - **Left Pane (Flow A):** Render the raw extracted JSON, highlighting dangerous AI assumptions in red.
    - **Right Pane (Flow B):** Render the grounded SQLite payload. Use green UI badges to highlight the injected strength and display the `guardrail_logs` array as a transparent audit trail.
## 7. System Guarantees (The Medical Safety SLA)
To ensure enterprise-grade clinical safety and prove production readiness, this architecture enforces the following non-negotiable guarantees:
- **Immutable Ground Truth:** The AI will *never* override the `official_strength` defined in the local SQLite database. The deterministic database is always the final authority.
- **100% Auditability:** Every single deterministic correction, penalty, or lock applied by the system is explicitly logged in the `guardrail_logs` array for complete explainability.
- **Risk-Based Routing:** Any matching result that remains ambiguous or falls below the confidence threshold after Phase 2 penalties is automatically flagged for "Manual Review Required."
- **Deterministic Fallback:** If the Pinecone cloud connection fails or times out, the system gracefully falls back to the pre-computed edge cache (or a baseline local SQLite query) to guarantee zero downtime during live clinical use.    