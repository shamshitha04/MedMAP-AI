# MedMap AI
### Deterministic, Explainable Clinical Decision Support for Prescription Safety

[cite_start]**MedMap AI** is a deterministic clinical decision-support system designed to prevent pharmaceutical dispensing errors caused by AI misinterpretation of prescription data[cite: 3, 4]. 

[cite_start]Large language models often confidently misread numeric brand variants (e.g., “625”) as dosage strengths[cite: 5]. In healthcare workflows, such ambiguity is unacceptable. [cite_start]MedMap AI wraps AI extraction inside strict, object-oriented clinical guardrails and validates all results against a verified local knowledge graph before producing output[cite: 3, 5].

---

## 🏥 Core Problem
Prescription text frequently contains numeric brand variants such as:
* **Augmentin 625**
* **Amoxiclav 375**
* **Crocin 650**

[cite_start]Traditional AI systems may interpret these numbers as dosage strengths rather than brand variants, leading to dangerous dispensing decisions[cite: 5]. 
* [cite_start]**Confidence is not correctness.** [cite: 5]
* [cite_start]**Healthcare systems require deterministic validation.** [cite: 4, 5]

---

## ⚙️ System Architecture
[cite_start]MedMap AI separates local orchestration from cloud-native vector search to maximize speed and reliability[cite: 7].



* [cite_start]**Frontend:** React / Next.js with TypeScript and Shadcn UI (Port 3000)[cite: 9].
* [cite_start]**Backend:** Python 3.10+ FastAPI (asyncio) via Uvicorn[cite: 10].
* [cite_start]**Ground Truth (Local):** SQLite + SQLAlchemy 2.0 (`aiosqlite`) for deterministic verification[cite: 11, 12].
* [cite_start]**Vector Engine (Cloud):** Pinecone Serverless for hybrid semantic + lexical retrieval[cite: 13, 14].
* [cite_start]**ML Pipeline:** GPT-4o-mini (Structured Outputs) + `all-MiniLM-L6-v2` embeddings[cite: 15, 16, 18].

---

## 🛡️ Explainable AI (XAI) Guardrail System
[cite_start]The system enforces a two-phase safety pipeline to eliminate hallucinated risks[cite: 5, 24, 36].

### Phase 1: Pre-Match Guardrails (The Safety Net)
* [cite_start]**Variant Separation Rule:** Numeric tokens inside brand names are treated strictly as brand variants and blocked from being interpreted as dosage strength[cite: 26, 27].
* [cite_start]**Normalization Rule:** Standardizes drug forms (e.g., "Tab" -> "Tablet") and frequency tokens before retrieval[cite: 29].

### Phase 2: Post-Match Deterministic Lock (The Final Lock)
* [cite_start]**Sparse Penalty Rule:** Hybrid search mathematically penalizes mismatched variants (e.g., penalizing "375" if input is "625")[cite: 33].
* [cite_start]**Combination Lock Rule:** If a medication is marked as a combination drug in SQLite, it cannot be split into separate components[cite: 40].
* [cite_start]**Strength Injection:** Official dosage strength is retrieved from the verified SQLite database and overrides any AI-extracted value[cite: 43].
* [cite_start]**Risk Classification:** Results are categorized as High, Medium, or Low confidence based on penalized similarity scores[cite: 45].

---

## 🚀 System Guarantees
To ensure production readiness, this architecture enforces the following:
* **Immutable Ground Truth:** AI never overrides the `official_strength` defined in SQLite.
* [cite_start]**100% Auditability:** Every correction is appended to a `guardrail_logs` array for transparent traceability[cite: 46, 55].
* **Manual Review Required:** Ambiguous results below confidence thresholds are flagged for human intervention.
* [cite_start]**Deterministic Fallback:** If cloud connections fail, the system utilizes a local edge cache ("Illusion of Edge") to maintain functionality[cite: 21, 22].

---

## 🖥️ Demonstration Mode: "Show, Don't Tell"
[cite_start]The UI visualizes the necessity of the architecture via parallel flows[cite: 56, 57]:
1.  [cite_start]**Flow A (No Guardrails):** Displays raw AI matching, demonstrating dangerous assumptions (e.g., assuming "625" is strength)[cite: 58].
2.  [cite_start]**Flow B (With Guardrails):** Displays grounded safety pipeline results with green UI badges highlighting auto-corrections and an audit trail panel[cite: 59, 60].



---

## 🛠️ Installation & Setup
1. [cite_start]**Environment:** `python -m venv MedMap`[cite: 8].
2. **Backend:** ```bash
   pip install -r backend/requirements.txt
   uvicorn app.main:app --reload
3. **Frontend:** ```bash
npm install
npm run dev