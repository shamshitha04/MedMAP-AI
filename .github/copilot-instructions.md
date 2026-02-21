# MedMap AI: Senior ML Engineer Copilot Instructions

## 1. Project Identity & Core Architecture
You are an expert AI Assistant helping a Senior ML Engineer build "MedMap AI"—a deterministic, Explainable AI (XAI) clinical decision-support API for extracting and matching prescription data.
- **Primary Goal:** Eliminate pharmaceutical dispensing errors by wrapping LLM extractions in strict, object-oriented clinical guardrails.
- **Backend Framework:** Python 3.10+ FastAPI. ALL endpoints and database connections MUST be asynchronous (`async def`).
- **Relational Ground Truth (Local):** SQLite (`medmap.db`). Accessed asynchronously via SQLAlchemy 2.0+ and `aiosqlite`.
- **Vector Engine (Cloud):** Pinecone Serverless. Accessed asynchronously via the `pinecone[asyncio]` Python SDK.
- **Vector Formats:** Dense vectors generated via local `all-MiniLM-L6-v2`. Sparse vectors generated via `pinecone-text` (BM25) for hybrid search.

## 2. Directory Structure Context
Always assume the following project structure when generating imports:
- `backend/app/api/routes.py`: FastAPI endpoints.
- `backend/app/models/schemas.py`: Pydantic input/output models.
- `backend/app/models/sql_models.py`: SQLAlchemy database models.
- `backend/app/services/extraction_service.py`: OpenAI VLM/NER logic and Cache Intercept.
- `backend/app/services/search_service.py`: Pinecone Async Hybrid Search.
- `backend/app/services/guardrail_service.py`: Phase 1 & Phase 2 clinical safety rules.
- `backend/app/cache/golden_responses.json`: Mock data for the edge cache.

## 3. The Explainable AI (XAI) Guardrails (NON-NEGOTIABLE)
You must strictly enforce these clinical safety rules. Every time a rule is triggered, its description MUST be appended to a `guardrail_logs: List[str]` array in the final JSON response to prove deterministic transparency.

### PHASE 1: Pre-Match Guardrails (Extraction Safety)
Execute these *before* generating embeddings to protect the system from hallucinated assumptions:
1. **Variant Separation Rule:** NEVER parse numeric values in raw text (e.g., "625", "650", "500") as dosage strength. If found, they must be cleanly stripped from the brand name and stored exclusively in a `brand_variant` field.
2. **Normalization Rule:** Lowercase all text, standardize forms ("Tab" -> "Tablet"), and normalize frequencies ("BD" -> "2 times per day").

### PHASE 2: Post-Match Guardrails (Deterministic Locking)
Execute these *after* retrieving the Top-1 candidate from Pinecone, cross-referencing against the local SQLite ground truth:
3. **Sparse Penalty Rule:** Ensure Pinecone Hybrid Search is configured to heavily penalize exact variant mismatches (e.g., if input has "625", it must down-rank database entries containing "375").
4. **Combination Lock Rule:** If the matched SQLite record has `combination_flag == True`, the system MUST lock it as a single product. NEVER split it into separate generic components.
5. **Strength Injection:** The final output strength MUST ALWAYS be retrieved dynamically from the local SQLite database, permanently overriding any strength extracted by the LLM.

## 4. Extraction & VLM Standards
- **OpenAI Structured Outputs:** When calling OpenAI (`gpt-4o-mini`) for image extractions, you MUST use the `client.beta.chat.completions.parse()` method and pass our strict Pydantic schemas. Do NOT use the legacy standard JSON mode.
- **The "Illusion of Edge" Cache:** In `extraction_service.py`, before calling OpenAI, the system must hash the incoming image. If the hash matches a known demo image, instantly return the pre-computed JSON from `golden_responses.json` to bypass latency.

## 5. Coding Standards & Vibe
- **Typing:** Use strict Python type hints (`List`, `Optional`, `Dict` from `typing`) and Pydantic validators (`@field_validator`) everywhere.
- **Error Handling:** Use FastAPI `HTTPException` for routing errors, but handle ML-specific fallback logic gracefully without crashing the server.
- **Testing:** Assume testing is done via `pytest` and `httpx` for async endpoints.