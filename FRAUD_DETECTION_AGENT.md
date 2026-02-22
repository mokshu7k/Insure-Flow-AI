# Fraud Detection Agent — System Documentation

> **Engine:** `agent-v1` · **Framework:** LangGraph StateGraph · **LLM:** Gemini 2.5 Flash · **Scoring:** AI-driven (Gemini aggregator)

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Graph Topology](#graph-topology)
3. [Node Reference](#node-reference)
   - [Node 1: Extraction Integrity](#node-1-extraction-integrity)
   - [Node 2: Cross-Document Consistency](#node-2-cross-document-consistency)
   - [Node 3: Document Intelligence](#node-3-document-intelligence)
   - [Node 4: Image Forensics](#node-4-image-forensics)
   - [Node 5: Document Content Fraud](#node-5-document-content-fraud)
   - [Node 6: Behavioral Risk](#node-6-behavioral-risk)
4. [Aggregator (Gemini Risk Synthesis)](#aggregator)
5. [State Definition](#state-definition)
6. [Tool Inventory](#tool-inventory)
7. [Bridge Layer (Service → Agent)](#bridge-layer)
8. [API Endpoints](#api-endpoints)
9. [Frontend Integration](#frontend-integration)
10. [Scoring & Weights](#scoring--weights)
11. [Manual Review Triggers](#manual-review-triggers)
12. [File Structure](#file-structure)
13. [Testing](#testing)

---

## Architecture Overview

The fraud detection system is a **6-node LangGraph agent** that analyses insurance claim documents for fraud signals. It combines deterministic analysis (pattern matching, math validation, pixel forensics) with Gemini-powered intelligence (content plausibility, risk synthesis) to produce an explainable fraud assessment.

**Key design principles:**
- **AI-driven final scoring** — Gemini evaluates all node findings holistically instead of a static weighted formula; falls back to a deterministic heuristic if unavailable
- **Three-way reconciliation** — every extracted value is verified against raw text AND an independent Gemini shadow call
- **Max-dominant scoring** — the highest-severity signal dominates each node's score, preventing dilution by clean checks
- **Graceful degradation** — every Gemini call has a deterministic fallback; the agent works fully offline (reduced accuracy); every node is wrapped in try/except to prevent single-node failures from crashing the pipeline
- **Explainability first** — every flag is human-readable; the aggregator produces a natural-language risk explanation

---

## Graph Topology

```
       ┌─→ Node 1 (Extraction) → Node 2 (Cross-Doc) → Node 3 (DocIntel) → Node 5 (ContentFraud/Gemini) ──┐
START ─┼─→ Node 4 (Image Forensics — parallel, pixel-level) ──────────────────────────────────────────────┼─→ Aggregator(Gemini) → END
       └─→ Node 6 (Behavioral & Statistical Risk — parallel) ─────────────────────────────────────────────┘
```

| Branch | Nodes | Execution | LLM Calls |
|--------|-------|-----------|-----------|
| **A** (sequential) | 1 → 2 → 3 → 5 | Sequential chain — each node enriches state | Gemini ×3 (Node 1: ×2, Node 5: ×1) |
| **B** (parallel) | 4 | Runs concurrently with Branch A | None (OpenCV only) |
| **C** (parallel) | 6 | Runs concurrently with Branch A | None (metadata only) |
| **Aggregator** | — | Waits for all 3 branches | Gemini ×1 (scoring + synthesis) |

Parallel writes to `node_results` are merged via a custom `_merge_node_results` reducer (dict merge) to avoid LangGraph's `InvalidUpdateError`.

---

## Node Reference

### Node 1: Extraction Integrity

> **File:** `app/ai_agents/fraud/nodes/extraction_integrity.py`
> **LLM:** Gemini ×2 (primary JSON extraction + shadow total)
> **Weight:** 0.20

Performs three-way reconciliation between PyMuPDF raw text, Gemini's full JSON extraction, and an independent Gemini shadow call that only extracts the total amount.

**Tools used:**
| Tool | Module | Purpose |
|------|--------|---------|
| `get_raw_text()` | `tools/pdf_extractor` | PyMuPDF raw text stream |
| `get_page_images()` | `tools/pdf_extractor` | Page-to-image rendering |
| `primary_extraction()` | `tools/gemini_extractor` | Full structured JSON extraction |
| `shadow_total_extraction()` | `tools/gemini_extractor` | Blind total-only shadow call |
| `coordinate_extraction()` | `tools/gemini_extractor` | Optional positional verification |
| `literal_anchor_check()` | `tools/reconciliation` | String match Gemini fields vs raw text |
| `arithmetic_recalculation()` | `tools/reconciliation` | Python-sum of line items vs total |
| `shadow_comparison()` | `tools/reconciliation` | Primary total vs shadow total |
| `calculate_integrity_score()` | `tools/reconciliation` | Weighted score aggregation |

**Checks:**
1. **Literal Anchor** — every Gemini field is searched in raw text; missing = hallucination
2. **Arithmetic Recalculation** — Python sums line items; delta > threshold = manipulation
3. **Shadow Comparison** — independent Gemini total vs primary total; mismatch = inconsistency
4. **Coordinate Verification** — optional Tesseract-based positional cross-check

**Score:** 0–100 · **Flags:** `PRIMARY_EXTRACTION_FAILED`, `LITERAL_FAIL`, `ARITHMETIC_FAIL`, `SHADOW_FAIL`

---

### Node 2: Cross-Document Consistency

> **File:** `app/ai_agents/fraud/nodes/cross_document_consistency.py`
> **LLM:** None (fully deterministic)
> **Weight:** 0.15

Validates the "story of the claim" across all uploaded documents — do dates align, do names match, do amounts add up?

**Tools used:**
| Tool | Module | Purpose |
|------|--------|---------|
| `promote_fields()` | `services/extraction_service` | Canonical field normalization |
| `compare_names()` | `tools/name_matcher` | Fuzzy name matching (thefuzz) |

**Checks:**
1. **Date Overlap & Timeline** — admission ≤ doc_date ≤ discharge; flags gaps >1 day
2. **Entity Name Equality** — patient/hospital/doctor names cross-checked across all document pairs (strict + fuzzy match)
3. **Policy Window Alignment** — all dates must fall within policy start/end dates
4. **Financial Sum-of-Parts** — Σ(sub-receipts) vs hospital bill total; flags >5% inflation

**Risk Weights:** `timeline_violation=90`, `policy_window_breach=85`, `name_mismatch=80`, `financial_mismatch=75`, `date_mismatch=70`

**Score:** 0–100, formula: `max_penalty + min(20, sum(others) × 0.3)` · **Flags:** `TIMELINE`, `TIMELINE_GAP`, `NAME_MISMATCH`, `NAME_VARIANT`, `POLICY_BREACH`, `FINANCIAL_INFLATION`

---

### Node 3: Document Intelligence

> **File:** `app/ai_agents/fraud/nodes/document_intelligence.py`
> **LLM:** None (fully deterministic)
> **Weight:** 0.10

Detects redaction bypass, data hallucination, and validates PAN/Aadhaar IDs.

**Tools used:**
| Tool | Module | Purpose |
|------|--------|---------|
| `check_redaction_integrity()` | `tools/redaction_checker` | Mask-bypass detection |
| `greedy_string_matcher()` | `tools/redaction_checker` | Field-to-raw-text matching |
| `validate_pan()` | `tools/id_validator` | PAN structural rules |
| `validate_aadhaar()` | `tools/id_validator` | Verhoeff checksum algorithm |

**Checks:**
1. **Redaction Bypass** — detects Gemini "seeing through" masked IDs (privacy violation)
2. **Hallucinated Digits** — detects Gemini inventing digits not in raw source
3. **Greedy String Matcher** — every extracted field must exist verbatim in raw PDF text
4. **PAN Validation** — position-based format rules + holder-type check
5. **Aadhaar Validation** — Verhoeff checksum; flags unmasked 12-digit numbers

**Risk Weights:** `redaction_privacy=90`, `aadhaar_checksum=80`, `redaction_hallucination=70`, `raw_mismatch=60`, `aadhaar_unmasked=60`, `pan_invalid=50`

**Score:** 0–100, formula: `max_penalty + min(25, sum(others) × 0.2)` · **Flags:** `REDACTION_PRIVACY`, `REDACTION_HALLUCINATION`, `RAW_MISMATCH`, `PAN_INVALID`, `AADHAAR_FULL_EXTRACTED`

---

### Node 4: Image Forensics

> **File:** `app/ai_agents/fraud/nodes/image_forensics.py`
> **LLM:** None (OpenCV / Pillow only)
> **Weight:** 0.15
> **Execution:** Parallel from START (only needs `document_bytes`)

Zero-trust pixel-level analysis — treats every document as potentially forged.

**Tools used:**
| Tool | Module | Purpose |
|------|--------|---------|
| `analyze_metadata()` | `tools/metadata_analyzer` | EXIF/software tag analysis |
| `analyze_pdf_metadata()` | `tools/metadata_analyzer` | PDF-specific metadata extraction |
| `compute_ela()` | `tools/ela_analyzer` | Error Level Analysis (JPEG recomp) |
| `compute_hashes()` | `tools/perceptual_hasher` | pHash/aHash/dHash fingerprinting |
| `detect_duplicates_in_set()` | `tools/perceptual_hasher` | Cross-page duplicate detection |
| `detect_copy_move()` | `tools/copy_move_detector` | DCT block matching for cloned regions |

**Checks:**
1. **Metadata/EXIF** — flags Photoshop/Canva/Illustrator, date anomalies, missing camera data, low DPI
2. **Error Level Analysis** — JPEG recompression detects localised edits; flags hotspots, hot areas, low SSIM
3. **Perceptual Hashing** — pHash duplicate/near-duplicate detection (template-farm detection)
4. **Copy-Move Detection** — DCT block-matching for cloned/spliced regions + noise inconsistency

**Risk Weights:** `phash_duplicate=95`, `copy_move=90`, `ela_hotspot=85`, `phash_near_duplicate=80`, `suspicious_software=75`, `noise_inconsistency=70`, `ela_hot_area=65`, `date_anomaly=60`

**Score:** 0–100, formula: `max_penalty + min(25, sum(others) × 0.2)` · **Flags:** `SUSPICIOUS_SOFTWARE`, `DATE_ANOMALY`, `ELA_HOTSPOT`, `COPY_MOVE_DETECTED`, `NOISE_INCONSISTENCY`, `DUPLICATE`, `NEAR_DUPLICATE`

**Notable:** Stores `document_hashes` in state for external cross-claim comparison. Converts PDFs to JPEG at 2× zoom before pixel analysis.

---

### Node 5: Document Content Fraud

> **File:** `app/ai_agents/fraud/nodes/document_content_fraud.py`
> **LLM:** Gemini ×1 (content analysis with document-type-specific checklists)
> **Weight:** 0.25 (highest weight — most impactful node)

Gemini-powered deep content analysis — arithmetic/GST validation + medical plausibility checks.

**Tools used:**
| Tool | Module | Purpose |
|------|--------|---------|
| `validate_arithmetic()` | `tools/arithmetic_gst_validator` | Line-item sums, qty×rate |
| `validate_gst()` | `tools/arithmetic_gst_validator` | Tax-slab + GSTIN format |
| `analyze_document_content()` | `tools/gemini_content_analyzer` | AI medical/financial plausibility |

**Checks:**
1. **Arithmetic Validator** — line-item math, total decomposition
2. **GST Validator** — tax slab rates, CGST/SGST matching, GSTIN format
3. **Gemini Content Analyser** — document-type-specific checklists:
   - **Hospital Bills** (8 items): phantom charges, duplicate items, pricing, date consistency
   - **Discharge Summaries** (6 items): procedure-diagnosis alignment, timeline
   - **Prescriptions** (5 items): drug-diagnosis interaction, dosage plausibility
   - **Lab Reports** (4 items): result-range consistency
4. **Diagnosis Consistency** — flags variation in diagnosis text across documents

**Score:** 0–100, formula: `0.6 × deterministic_score + 0.4 × gemini_risk_score` · **Flags:** `ARITHMETIC_MISMATCH`, `LINE_ITEM_MATH_ERROR`, `GST_RATE_ANOMALY`, `CGST_SGST_MISMATCH`, `GSTIN_FORMAT_INVALID`, `CONTENT_{severity}: [{category}] ...`, `DIAGNOSIS_VARIATION`

---

### Node 6: Behavioral Risk

> **File:** `app/ai_agents/fraud/nodes/behavioral_risk.py`
> **LLM:** None (purely deterministic metadata analysis)
> **Weight:** 0.15
> **Execution:** Parallel from START (only needs `claim_metadata`)

Analyses claim timing, frequency patterns, and policyholder history for behavioral red flags.

**Tools used:**
| Tool | Module | Purpose |
|------|--------|---------|
| `analyze_behavioral_risk()` | `tools/behavioral_analyzer` | Full behavioral scoring |

**Checks:**
1. **Claim Timing** — days since policy activation (early claims are riskier)
2. **Claim Frequency** — number of claims in 30-day window
3. **Claim-to-Sum-Insured Ratio** — proportion of sum insured being claimed
4. **90-Day Aggregate** — total claim amount in rolling 90-day window
5. **Prior Fraud History** — historical fraud flag count on the claimant

**Input:** `claim_metadata` containing: `claim_amount`, `claim_type`, `sum_insured`, `policy_start_date`, `claim_created_at`, `recent_claims_30d`, `total_claim_amount_90d`, `fraud_flag_count`

**Score:** 0–100 · **Flags:** `VERY_EARLY_CLAIM`, `EARLY_CLAIM`, `HIGH_FREQUENCY`, `MODERATE_FREQUENCY`, `VERY_HIGH_RATIO`, `HIGH_RATIO`, `EXCESSIVE_90D`, `HIGH_90D`, `PRIOR_FRAUD_HISTORY`

---

## Aggregator

> **File:** `app/ai_agents/fraud/graph.py` → `aggregator_node()`
> **LLM:** Gemini ×1 (AI-powered scoring + risk synthesis)

The aggregator is the final node that receives all 6 nodes' outputs and makes a **single Gemini LLM call** (`generate_fraud_score_and_synthesis`) to determine the final fraud score. This replaces the previous static weighted-average formula — Gemini now evaluates all findings holistically.

### How it works

1. **Collects all node flags** — gathers every flag string from all 6 nodes
2. **Builds a compact digest** — for each node: score (0–100), flag count, top 8 flags, key check results (pass/fail/values)
3. **Sends to Gemini** — a structured prompt instructs the LLM to:
   - Evaluate findings across all nodes holistically
   - Assign a final fraud score (0–1) — a single critical finding (e.g. copy-move, duplicate hash) can push the score above 0.8 even if other nodes are clean
   - Multiple low-severity flags should compound but not reach HIGH without cross-node corroboration
   - Skipped or errored nodes should neither help nor hurt the score
   - Return risk level, explanation, critical signals, and manual-review recommendation
4. **Applies deterministic triggers** — 7 instant-trigger patterns (see [Manual Review Triggers](#manual-review-triggers)) are checked on top of the AI decision
5. **Graceful fallback** — if Gemini is unavailable, falls back to a deterministic heuristic: `score = 0.6 × max(node_scores) + 0.4 × avg(node_scores)`

### Gemini response schema

```json
{
  "final_score": 0.45,
  "risk_level": "MEDIUM",
  "risk_explanation": "2-4 sentence explanation referencing key findings",
  "critical_signals": ["signal1", "signal2"],
  "manual_review_recommended": true,
  "confidence": "HIGH"
}
```

### Risk level boundaries

| Score Range | Level |
|-------------|-------|
| ≥ 0.85 | `VERY_HIGH` |
| ≥ 0.70 | `HIGH` |
| ≥ 0.50 | `MEDIUM` |
| ≥ 0.30 | `LOW` |
| < 0.30 | `MINIMAL` |

> **Note:** These boundaries are enforced as a safety net. If Gemini returns a score and risk level that don't match, the boundaries override the LLM's label.

---

## State Definition

> **File:** `app/ai_agents/fraud/state.py`

`FraudAgentState` is a `TypedDict` that flows through every node. The `node_results` field uses a custom `_merge_node_results` reducer to safely merge parallel writes from Branches B and C.

**Key state groups:**

| Group | Fields |
|-------|--------|
| Identity | `claim_id`, `document_id` |
| Inputs | `document_bytes`, `document_type_code`, `existing_extracted_data` |
| Context | `all_documents_data`, `policy_data`, `claim_metadata` |
| Per-node outputs | `*_checks`, `*_risk_score`, `*_flags` (6 groups) |
| Aggregate | `node_results`, `final_fraud_score`, `final_risk_level` |
| Enhanced | `manual_review_required`, `manual_review_triggers`, `risk_explanation`, `critical_signals` |

---

## Tool Inventory

14 tools across `app/ai_agents/fraud/tools/`:

| Tool Module | Type | Used By | Key Capability |
|-------------|------|---------|----------------|
| `pdf_extractor` | Deterministic | Node 1 | PyMuPDF raw text + page images |
| `gemini_extractor` | LLM | Node 1 | Gemini full JSON + shadow total extraction |
| `reconciliation` | Deterministic | Node 1 | Three-way reconciliation scoring |
| `name_matcher` | Deterministic | Node 2 | Fuzzy name comparison (thefuzz) |
| `redaction_checker` | Deterministic | Node 3 | Redaction bypass + string matching |
| `id_validator` | Deterministic | Node 3 | PAN structural + Aadhaar Verhoeff |
| `metadata_analyzer` | Deterministic | Node 4 | EXIF / PDF metadata extraction |
| `ela_analyzer` | Deterministic | Node 4 | JPEG Error Level Analysis |
| `perceptual_hasher` | Deterministic | Node 4 | pHash / aHash / dHash fingerprinting |
| `copy_move_detector` | Deterministic | Node 4 | DCT block clone detection |
| `arithmetic_gst_validator` | Deterministic | Node 5 | Line-item math + GST validation |
| `gemini_content_analyzer` | LLM | Node 5, Agg | Content plausibility + AI scoring + risk synthesis |
| `behavioral_analyzer` | Deterministic | Node 6 | Claim timing / frequency analysis |

---

## Bridge Layer

> **File:** `app/services/fraud_service.py` → `run_fraud_agent_analysis()`

The bridge function connects the encrypted document storage and database models to the LangGraph agent:

```
API Request
    ↓
Permission check (INSURER_ADMIN / CLAIM_ADJUSTER)
    ↓
Load target ClaimDocument from DB
    ↓
Decrypt PDF bytes: ./storage/encrypted/<claim_id>/<uuid>.enc → Fernet.decrypt()
    ↓
Load ALL documents on claim (for Node 2 cross-doc checks)
    ↓
Build policy_data from Claim.verified_data["policy_snapshot"]
    ↓
Build claim_metadata from UserFraudProfile (recent_claims_30d, fraud_flag_count, etc.)
    ↓
run_fraud_agent() → 6-node LangGraph pipeline
    ↓
Persist results to FraudAssessment table (upsert)
    ↓
Update denormalized fraud_score on Claim
    ↓
Update UserFraudProfile (increment fraud_flag_count if HIGH/VERY_HIGH)
    ↓
Log audit action
```

The `run_fraud_analysis()` endpoint (legacy) now also routes through the agent — it auto-picks the first completed document.

---

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/fraud/analyze/{claim_id}` | Run agent on auto-selected document (first completed) |
| `POST` | `/fraud/agent-analyze/{claim_id}/{document_id}` | Run agent on a specific document |
| `GET` | `/fraud/{claim_id}` | Fetch latest fraud assessment |

**Response shape** (`FraudAssessmentResponse`):
```json
{
  "id": "uuid",
  "claim_id": "uuid",
  "fraud_score": 0.3456,
  "risk_level": "MEDIUM",
  "explanation_text": "Gemini-generated risk narrative...",
  "layer_scores": {
    "extraction_integrity": { "score": 45, "weight": 0.20, "flags": ["..."], "layer": "extraction_integrity" },
    "cross_document_consistency": { "score": 20, "weight": 0.15, "flags": [], "layer": "cross_document_consistency" }
  },
  "layer_details": {
    "extraction_integrity": { "score": 45, "flags": ["..."], "details": { "...": "..." } }
  },
  "feature_snapshot": {
    "manual_review_required": true,
    "manual_review_triggers": ["Aggregate risk score: 0.35 (MEDIUM)"],
    "critical_signals": ["ARITHMETIC_MISMATCH"],
    "analyzed_document_id": "uuid"
  },
  "deterministic_signals": ["..."],
  "statistical_signals": ["..."],
  "behavioral_flags": ["..."],
  "document_flags": ["..."],
  "network_flags": [],
  "config_version": "agent-v1",
  "ai_degraded_mode": false,
  "ml_model_used": false,
  "created_at": "2025-01-01T00:00:00Z"
}
```

---

## Frontend Integration

The fraud agent is integrated into the **Claim Detail Page** (`frontend/src/app/claims/[id]/page.tsx`) via the `FraudAgentPanel` component.

### FraudAgentPanel (`frontend/src/components/ui/FraudAgentPanel.tsx`)

**Features:**
- **Document selector** — dropdown to choose which document to analyse (or auto-select first completed)
- **Per-node breakdown** — expandable rows for all 6 nodes showing:
  - Score bar (0–100) with color coding (green / amber / red)
  - Weight multiplier badge
  - Flag count
  - Expanded: node description, individual signal tags, detailed check results
- **Manual review banner** — amber alert when `manual_review_required` is true, with trigger list
- **Critical signals** — red alert showing high-severity signals from Gemini synthesis
- **AI risk explanation** — full Gemini-generated narrative
- **Analysed document indicator** — shows which document was used
- **Engine metadata** — config version, assessment timestamp

### Data Flow

```
User clicks "Analyze" → FraudAgentPanel
    ↓
fraudService.analyze(claimId) or fraudService.agentAnalyze(claimId, docId)
    ↓
POST /fraud/analyze/{claimId} or /fraud/agent-analyze/{claimId}/{docId}
    ↓
Backend: decrypt → 6-node agent → persist → return FraudAssessmentResponse
    ↓
Frontend: render per-node scores, flags, explanation, triggers
```

### Types (`frontend/src/types/index.ts`)

Key interfaces:
- `FraudAssessment` — full assessment with `layer_scores`, `layer_details`, `feature_snapshot`
- `LayerScore` — `{ score, flags, layer, weight?, method?, ai_degraded? }`

---

## Scoring & Weights

### Final Score — AI-Driven

The final fraud score is **determined by Gemini**, not a static formula. The aggregator sends each node's score, flags, and key check results to Gemini, which evaluates the findings holistically and returns a score between 0 and 1.

**Why AI scoring?**
- A static weighted average dilutes critical signals — e.g. a copy-move detection (Node 4 score=90) with clean Nodes 1–3 would produce a low average
- Gemini can reason about **cross-node corroboration** — e.g. an arithmetic mismatch (Node 5) combined with image tampering (Node 4) is far more suspicious than either alone
- The LLM can distinguish between benign flags (missing optional fields) and genuinely alarming signals

**Deterministic fallback** (when Gemini is unavailable):
```
score = 0.6 × max(node_scores / 100) + 0.4 × avg(node_scores / 100)
```

### Node Weights (Informational)

These weights are no longer used for scoring — they are sent to the frontend for display purposes and hint at relative importance:

| Node | Weight | Rationale |
|------|--------|-----------|
| Extraction Integrity | 0.20 | Foundation — data quality gate |
| Cross-Document Consistency | 0.15 | Story coherence across documents |
| Document Intelligence | 0.10 | Privacy checks (lower fraud impact) |
| Image Forensics | 0.15 | Pixel-level forgery detection |
| **Document Content Fraud** | **0.25** | **Highest** — AI-powered deep analysis |
| Behavioral Risk | 0.15 | Metadata-based pattern detection |

### Per-Node Scoring Formula

Each node (except 1 and 6) uses the **max-dominant with diminishing additions** pattern:

```
score = max_penalty + min(CAP, sum(other_penalties) × FACTOR)
```

This ensures:
- A single critical signal dominates (no dilution)
- Multiple minor signals still compound
- Score is bounded and predictable

These per-node scores (0–100) are then passed to Gemini for the final holistic evaluation.

### Risk Thresholds

Across all nodes: **<20 CLEAN**, **<60 SUSPICIOUS**, **≥60 HIGH_RISK**

---

## Manual Review Triggers

The aggregator checks for 7 instant-trigger patterns plus a score threshold:

| Pattern | Reason |
|---------|--------|
| `COPY_MOVE_DETECTED` | Document tampering — copy-move regions detected |
| `PHASH_DUPLICATE` | Document reuse — perceptual-hash duplicate |
| `CLAIM_BEFORE_POLICY` | Temporal fraud — claim filed before policy start |
| `VERY_EARLY_CLAIM` | Suspicious timing — very early claim after policy activation |
| `PRIOR_FRAUD_HISTORY` | History — prior fraud flags on policyholder |
| `ARITHMETIC_MISMATCH` | Financial — bill arithmetic inconsistency |
| `CONTENT_CRITICAL` | AI analysis — critical content-fraud signal |
| Score ≥ 0.50 | Aggregate risk threshold |

Additionally, the Gemini risk synthesis can recommend manual review independently.

---

## File Structure

```
app/ai_agents/fraud/
├── __init__.py
├── graph.py                    # StateGraph definition, aggregator, run_fraud_agent()
├── state.py                    # FraudAgentState TypedDict with merge reducer
├── nodes/
│   ├── extraction_integrity.py     # Node 1: PyMuPDF + Gemini reconciliation
│   ├── cross_document_consistency.py # Node 2: timeline, names, finances
│   ├── document_intelligence.py    # Node 3: redaction, IDs, hallucination
│   ├── image_forensics.py          # Node 4: EXIF, ELA, pHash, copy-move
│   ├── document_content_fraud.py   # Node 5: arithmetic, GST, Gemini analysis
│   └── behavioral_risk.py          # Node 6: timing, frequency, history
└── tools/
    ├── pdf_extractor.py            # PyMuPDF raw text + page images
    ├── gemini_extractor.py         # Gemini structured extraction
    ├── reconciliation.py           # Three-way reconciliation checks
    ├── name_matcher.py             # Fuzzy name comparison
    ├── redaction_checker.py        # Redaction bypass detection
    ├── id_validator.py             # PAN + Aadhaar validation
    ├── metadata_analyzer.py        # EXIF / PDF metadata
    ├── ela_analyzer.py             # Error Level Analysis
    ├── perceptual_hasher.py        # pHash / aHash / dHash
    ├── copy_move_detector.py       # DCT block clone detection
    ├── arithmetic_gst_validator.py # Line-item math + GST
    ├── gemini_content_analyzer.py  # Gemini content + risk synthesis
    └── behavioral_analyzer.py      # Claim timing / frequency
```

**Backend integration:**
- `app/api/fraud.py` — FastAPI router (3 endpoints)
- `app/services/fraud_service.py` — Bridge: decrypt → agent → persist
- `app/models/fraud.py` — FraudAssessment ORM model
- `app/schemas/fraud.py` — Pydantic response schema

**Frontend:**
- `frontend/src/components/ui/FraudAgentPanel.tsx` — Per-node visualization
- `frontend/src/services/fraudService.ts` — API client (analyze, agentAnalyze, getAssessment)
- `frontend/src/types/index.ts` — TypeScript interfaces

---

## Testing

| Test Suite | Tests | File |
|------------|-------|------|
| Node 2: Cross-Document Consistency | 19 | `scripts/test_node2_consistency.py` |
| Node 3: Document Intelligence | 25 | `scripts/test_node3_intelligence.py` |
| Node 4: Image Forensics + Integration | 37 | `scripts/test_node4_forensics.py` |
| Node 5: Document Content Fraud | 30 | `scripts/test_node5_content_fraud.py` |
| Node 6: Behavioral Risk | 41 | `scripts/test_node6_behavioral.py` |
| Bridge: Service → Agent | 15 | `scripts/test_bridge.py` |
| **Total** | **167** | — |

All tests validate:
- Node scoring logic with controlled inputs
- Flag generation for each check type
- Edge cases (empty data, missing fields, graceful degradation)
- Graph topology (config version = `agent-v1`, 6-node pipeline)
- Bridge data assembly (decrypt → agent → persist)
- Aggregator AI scoring with deterministic fallback
