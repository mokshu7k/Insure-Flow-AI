# InsureFlow-AI — Complete System Flow

This document traces the entire journey of a claim through the system, from document upload to fraud assessment storage.

---

## High-Level Flow Overview

```
1. USER uploads document (invoice/prescription)
   ↓
2. OCR Pipeline extracts text and structured data
   ↓
3. Document saved (encrypted) + metadata stored in DB
   ↓
4. USER submits claim (references uploaded documents)
   ↓
5. Claim Service creates claim record
   ↓
6. Fraud Service triggers analysis
   ↓
7. Three-Layer Fraud Engine runs
   ↓
8. Fraud Assessment stored in DB
   ↓
9. Claim status updated based on fraud score
```

---

## Part 1: Document Upload and OCR Processing

### Entry Point: API Route

**File**: [app/api/v1/documents.py](file:///e:/Projects/Insure-Flow-AI/app/api/v1/documents.py)

**Endpoint**: `POST /api/v1/documents/`

**What it does**:
- Receives multipart file upload from user
- Validates file type (PDF, JPEG, PNG only)
- Validates file size (max 10MB from config)
- Calls `DocumentService.upload_document()`

**To modify**: Change allowed file types, add file size validation, add virus scanning

---

### Service Layer: Document Storage

**File**: [app/services/document_service.py](file:///e:/Projects/Insure-Flow-AI/app/services/document_service.py)

**Function**: `upload_document(file, claim_id, document_type, user_id, db)`

**What it does**:
1. Validates consent exists for the user
2. Calls OCR pipeline to extract text and structured data
3. Calls `FileStorage.save_file()` to encrypt and store the file
4. Creates [Document](file:///e:/Projects/Insure-Flow-AI/app/core/constants.py#25-35) DB record with:
   - Original filename
   - Encrypted file path
   - Document type (INVOICE, PRESCRIPTION, etc.)
   - OCR extracted text
   - Structured data JSON
5. Logs document upload to audit trail
6. Returns [Document](file:///e:/Projects/Insure-Flow-AI/app/core/constants.py#25-35) object

**To modify**: Add additional validation, change encryption settings, add document versioning

---

### OCR Pipeline: Text Extraction

**File**: [app/ocr/pipeline.py](file:///e:/Projects/Insure-Flow-AI/app/ocr/pipeline.py)

**Function**: `process_document(file_path, document_type)`

**What it does**:
1. Calls `preprocess.prepare_image()` — image enhancement
2. Calls `extractor.extract_text()` — Tesseract OCR
3. Calls `parser.parse_document()` — structured data extraction
4. Returns [(raw_text, structured_data_dict)](file:///e:/Projects/Insure-Flow-AI/app/config.py#60-63)

**Flow breakdown**:

#### Step 1: Preprocessing

**File**: [app/ocr/preprocess.py](file:///e:/Projects/Insure-Flow-AI/app/ocr/preprocess.py)

**Function**: `prepare_image(image_path)`

**What it does**:
- Loads image with OpenCV
- Converts to grayscale
- Applies denoising
- Applies adaptive thresholding
- Deskews if needed
- Returns preprocessed image array

**To modify**: Add rotation correction, add contrast enhancement, change threshold algorithm

---

#### Step 2: Text Extraction

**File**: [app/ocr/extractor.py](file:///e:/Projects/Insure-Flow-AI/app/ocr/extractor.py)

**Function**: `extract_text(image)`

**What it does**:
- Runs Tesseract OCR on preprocessed image
- Returns raw text string

**To modify**: Change Tesseract config (language, PSM mode), add confidence filtering

---

#### Step 3: Structured Parsing

**File**: [app/ocr/parser.py](file:///e:/Projects/Insure-Flow-AI/app/ocr/parser.py)

**Function**: `parse_document(text, document_type)`

**What it does**:
- Uses regex patterns to extract fields based on document type:
  - **INVOICE**: amount, date, provider name, invoice number
  - **PRESCRIPTION**: medication names, dosage, doctor name
  - **MEDICAL_REPORT**: diagnosis, treatment, dates
- Returns structured dict

**To modify**: Add new document types, improve regex patterns, add NLP-based extraction

---

### File Storage: Encryption

**File**: [app/utils/file_storage.py](file:///e:/Projects/Insure-Flow-AI/app/utils/file_storage.py)

**Function**: `save_file(file, user_id, claim_id)`

**What it does**:
1. Generates unique filename with UUID
2. Reads file bytes
3. Calls `encryption.encrypt_file()` to encrypt bytes
4. Saves encrypted bytes to disk at `ENCRYPTED_STORAGE_DIR/{user_id}/{claim_id}/{filename}.enc`
5. Returns encrypted file path

**To modify**: Change storage backend (S3, Azure Blob), add compression, change encryption algorithm

---

**File**: [app/utils/encryption.py](file:///e:/Projects/Insure-Flow-AI/app/utils/encryption.py)

**Function**: `encrypt_file(file_bytes)`

**What it does**:
- Uses Fernet (symmetric encryption) with `ENCRYPTION_KEY` from config
- Returns encrypted bytes

**To modify**: Switch to asymmetric encryption, add key rotation

---

## Part 2: Claim Submission

### Entry Point: API Route

**File**: [app/api/v1/claims.py](file:///e:/Projects/Insure-Flow-AI/app/api/v1/claims.py)

**Endpoint**: `POST /api/v1/claims/`

**What it does**:
- Receives claim submission request (policy number, claim type, amount, document IDs)
- Validates user has given consent
- Calls `ClaimService.create_claim()`

**To modify**: Add additional validation, add claim templates, add multi-step submission

---

### Service Layer: Claim Creation

**File**: [app/services/claim_service.py](file:///e:/Projects/Insure-Flow-AI/app/services/claim_service.py)

**Function**: `create_claim(claim_data, user_id, db)`

**What it does**:
1. Validates consent exists
2. Validates referenced documents belong to user
3. Creates [Claim](file:///e:/Projects/Insure-Flow-AI/app/core/constants.py#7-12) DB record with status `SUBMITTED`
4. Links documents to claim
5. Logs claim creation to audit trail
6. **Automatically triggers fraud analysis** by calling `FraudService.analyze_claim()`
7. Updates claim status based on fraud score:
   - Score >= 0.7 → `MANUAL_REVIEW_REQUIRED`
   - Score < 0.7 → `FRAUD_ANALYZED`
8. Returns [Claim](file:///e:/Projects/Insure-Flow-AI/app/core/constants.py#7-12) object

**To modify**: Add claim validation rules, change auto-analysis trigger, add notification system

---

## Part 3: Fraud Detection (The Core Engine)

### Entry Point: Fraud Service

**File**: [app/services/fraud_service.py](file:///e:/Projects/Insure-Flow-AI/app/services/fraud_service.py)

**Class**: [FraudService](file:///e:/Projects/Insure-Flow-AI/app/services/fraud_service.py#16-101)

**Function**: [analyze_claim(claim: Claim) → FraudAnalysisResult](file:///e:/Projects/Insure-Flow-AI/app/services/fraud_service.py#31-87)

**What it does**:
1. Builds `claim_context` dict from claim data:
   ```python
   {
       "claim_id": str(claim.id),
       "policy_number": claim.policy_number,
       "claim_type": claim.claim_type,
       "claim_amount": claim.claim_amount,
       "user_id": str(claim.user_id),
       # Pre-fetch historical data for Layer 2:
       "recent_claim_count": <query DB for user's recent claims>,
       "prior_fraud_flags": <query DB for user's past fraud flags>,
       "days_to_policy_expiry": <calculate from policy data>
   }
   ```
2. Calls `FraudOrchestrator.analyze(claim_context)`
3. Stores [FraudAssessment](file:///e:/Projects/Insure-Flow-AI/app/models/fraud.py#11-35) record in DB with:
   - `fraud_score`
   - `deterministic_signals_json` (list of flags)
   - `statistical_signals_json` (list of anomalies)
   - `explanation_text` (human-readable)
4. Logs to audit trail
5. Returns [FraudAnalysisResult](file:///e:/Projects/Insure-Flow-AI/app/schemas/fraud.py#36-44)

**To modify**: Add more historical data fields, change DB query logic, add caching

---

### Orchestrator: Legacy Wrapper

**File**: [app/ai_agents/orchestrator.py](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/orchestrator.py)

**Class**: [FraudOrchestrator](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/orchestrator.py#16-44)

**Function**: [analyze(claim_context) → FraudAnalysisResult](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/orchestrator.py#32-44)

**What it does**:
- Thin wrapper that delegates to the new engine
- Calls `FraudEngineOrchestrator.analyze(claim_context)`
- Converts frozen engine response back to legacy [FraudAnalysisResult](file:///e:/Projects/Insure-Flow-AI/app/schemas/fraud.py#36-44) via `adapter.to_legacy()`
- Returns mutable [FraudAnalysisResult](file:///e:/Projects/Insure-Flow-AI/app/schemas/fraud.py#36-44) (for backward compatibility)

**To modify**: This is just a wrapper — all logic is in the engine below

---

### Fraud Engine: Main Orchestrator

**File**: [app/ai_agents/fraud/orchestrator.py](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/fraud/orchestrator.py)

**Class**: [FraudEngineOrchestrator](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/fraud/orchestrator.py#24-157)

**Function**: [analyze(claim_context, privacy_mode=None) → FraudAssessmentResponse](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/orchestrator.py#32-44)

**What it does** (step-by-step):

#### Step 1: Run Layer 1 (Deterministic Rules)

Calls `layer1_deterministic.evaluate(claim_context)`

**File**: [app/ai_agents/fraud/layer1_deterministic.py](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/fraud/layer1_deterministic.py)

**What it does**:
- Checks claim amount against thresholds from `config.CLAIM_AMOUNT_THRESHOLDS`
- Checks if amount is suspiciously round (divisible by 10,000)
- Checks policy number length
- Returns [DeterministicResult(score, signals)](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/fraud/schemas.py#16-27)
  - Example signals: `["AMOUNT_EXCEEDS_THRESHOLD", "SUSPICIOUSLY_ROUND_AMOUNT"]`

**To modify**: Add new rules (e.g., duplicate invoice check, time-of-day patterns), change thresholds in [config.py](file:///e:/Projects/Insure-Flow-AI/app/config.py)

---

#### Step 2: Run Layer 2 (Statistical Analysis)

Calls `layer2_statistical.evaluate(claim_context)`

**File**: [app/ai_agents/fraud/layer2_statistical.py](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/fraud/layer2_statistical.py)

**What it does**:
- **Amount z-score**: Compares claim amount to mean/std from `config.STATISTICAL_BASELINES`
  - If z-score > 2.5 → adds `"AMOUNT_STATISTICAL_OUTLIER"`
- **Claim frequency**: Checks `recent_claim_count` from context
  - If >= 3 → adds `"UNUSUALLY_HIGH_CLAIM_FREQUENCY"`
- **Prior fraud**: Checks `prior_fraud_flags` from context
  - If >= 1 → adds `"PREVIOUS_FRAUD_FLAGS_ON_RECORD"`
- **Near expiry**: Checks `days_to_policy_expiry` from context
  - If <= 30 → adds `"CLAIM_NEAR_POLICY_EXPIRY"`
- Returns [StatisticalResult(score, anomalies)](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/fraud/schemas.py#29-40)

**To modify**: Add provider risk scoring, add temporal clustering detection, update baselines in [config.py](file:///e:/Projects/Insure-Flow-AI/app/config.py), add ML model predictions

---

#### Step 3: Run Layer 3 (Narrative / AI)

Calls `layer3_narrative.evaluate(claim_context, signals, anomalies, behavioral_flags, preliminary_score, privacy_mode)`

**File**: [app/ai_agents/fraud/layer3_narrative.py](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/fraud/layer3_narrative.py)

**What it does**:
1. **Privacy gate**: Calls `privacy.sanitize(claim_context, mode)`
   - **File**: [app/ai_agents/fraud/privacy.py](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/fraud/privacy.py)
   - Removes/masks PII based on mode (strict/balanced/raw)
   - Returns sanitized dict
2. **Check if external AI enabled**: Reads `config.ENABLE_EXTERNAL_AI`
   - If `False` (default) → skip to local narrative
   - If `True` → attempt external AI call with timeout
3. **External AI call** (if enabled):
   - Calls [_call_external_ai()](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/fraud/layer3_narrative.py#181-201) with sanitized data
   - If timeout/error → sets `ai_degraded_mode = True`, falls back to local
4. **Local narrative** (default path):
   - Classifies risk level from score using `config.RISK_LEVEL_BOUNDARIES`
   - Humanizes all flags using `_FLAG_DESCRIPTIONS` dict
   - Builds `structured_reasoning` dict:
     ```python
     {
         "risk_level": "HIGH",
         "summary": "Fraud risk assessment: HIGH (score: 0.75). 3 signal(s) identified.",
         "signals_explained": {
             "AMOUNT_EXCEEDS_THRESHOLD": "Claim amount exceeds typical threshold...",
             ...
         },
         "recommendation": "This claim requires MANUAL REVIEW..."
     }
     ```
   - Computes local narrative score (signal density × 0.10)
   - Returns [NarrativeResult(score, structured_reasoning, ai_degraded_mode)](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/fraud/schemas.py#42-54)

**To modify**: Add external AI integration (OpenAI, Anthropic), change risk boundaries in [config.py](file:///e:/Projects/Insure-Flow-AI/app/config.py), improve local narrative templates

---

#### Step 4: Aggregate Scores

Calls `aggregator.aggregate(deterministic, statistical, narrative)`

**File**: [app/ai_agents/fraud/aggregator.py](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/fraud/aggregator.py)

**What it does**:
1. Checks `narrative.ai_degraded_mode`
   - If `True` → uses degraded weights (0.55 / 0.45 / 0.0)
   - If `False` → uses normal weights (0.40 / 0.35 / 0.25)
2. Computes weighted average:
   ```
   final_score = (det_score × w_det + stat_score × w_stat + narr_score × w_narr) / total_weight
   ```
3. Clamps to [0.0, 1.0]
4. Returns [AggregatedScore(final_score, layer_scores, config_version, baseline_version, ai_degraded_mode)](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/fraud/schemas.py#59-73)

**To modify**: Change weights in [config.py](file:///e:/Projects/Insure-Flow-AI/app/config.py), add non-linear scoring, add score calibration

---

#### Step 5: Audit Logging

Calls `audit_logger.log_assessment()`

**File**: [app/ai_agents/fraud/audit_logger.py](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/fraud/audit_logger.py)

**What it does**:
- Writes to dedicated audit log via `app.core.logging.get_audit_logger()`
- Logs: claim_id, final_score, privacy_mode, external_ai_used, ai_degraded_mode, config_version, timestamp
- **Never logs raw claim data or PII**

**To modify**: Add additional metadata, change log format, add external log shipping

---

#### Step 6: Build Final Response

Orchestrator builds frozen [FraudAssessmentResponse](file:///e:/Projects/Insure-Flow-AI/app/schemas/fraud.py#9-34):
- Converts `structured_reasoning` to explanation text
- Embeds `config_version` and `baseline_version`
- Includes all signals, anomalies, behavioral flags
- Includes metadata with `agent_scores` breakdown

Returns frozen [FraudAssessmentResponse](file:///e:/Projects/Insure-Flow-AI/app/schemas/fraud.py#9-34)

---

### Adapter: Legacy Conversion

**File**: [app/ai_agents/fraud/adapter.py](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/fraud/adapter.py)

**Function**: [to_legacy(response) → FraudAnalysisResult](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/fraud/adapter.py#15-55)

**What it does**:
- Converts frozen [FraudAssessmentResponse](file:///e:/Projects/Insure-Flow-AI/app/schemas/fraud.py#9-34) to mutable [FraudAnalysisResult](file:///e:/Projects/Insure-Flow-AI/app/schemas/fraud.py#36-44)
- Maps field names (e.g., `deterministic_signals` → `deterministic_flags`)
- Preserves `metadata.agent_scores` for test compatibility
- Returns [FraudAnalysisResult](file:///e:/Projects/Insure-Flow-AI/app/schemas/fraud.py#36-44) (the schema [fraud_service.py](file:///e:/Projects/Insure-Flow-AI/app/services/fraud_service.py) expects)

**To modify**: This is just a mapping layer — only change if you modify schemas

---

## Part 4: Storage and Response

### Database Storage

**File**: [app/services/fraud_service.py](file:///e:/Projects/Insure-Flow-AI/app/services/fraud_service.py) (continued)

After getting [FraudAnalysisResult](file:///e:/Projects/Insure-Flow-AI/app/schemas/fraud.py#36-44) from orchestrator:

1. Creates [FraudAssessment](file:///e:/Projects/Insure-Flow-AI/app/models/fraud.py#11-35) DB record:
   ```python
   FraudAssessment(
       id=uuid.uuid4(),
       claim_id=claim.id,
       fraud_score=result.fraud_score,
       deterministic_signals_json=result.deterministic_flags,
       statistical_signals_json=result.statistical_flags,
       explanation_text=result.explanation
   )
   ```
2. Commits to database
3. Logs to audit trail via `AuditService.log_action()`

**Model**: [app/models/fraud.py](file:///e:/Projects/Insure-Flow-AI/app/models/fraud.py) — [FraudAssessment](file:///e:/Projects/Insure-Flow-AI/app/models/fraud.py#11-35) table

**To modify**: Add additional fields to model, add fraud assessment versioning

---

### Claim Status Update

**File**: [app/services/claim_service.py](file:///e:/Projects/Insure-Flow-AI/app/services/claim_service.py) (continued)

After fraud analysis completes:

```python
if fraud_score >= config.FRAUD_THRESHOLD:  # 0.7
    claim.status = ClaimStatus.MANUAL_REVIEW_REQUIRED
else:
    claim.status = ClaimStatus.FRAUD_ANALYZED
```

**To modify**: Add additional status transitions, add notification triggers, add escalation rules

---

## Configuration: The Control Panel

**File**: [app/ai_agents/fraud/config.py](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/fraud/config.py)

**This is where you change fraud engine behavior without touching code**:

| What to change | Variable | Example |
|----------------|----------|---------|
| Layer weights | `WEIGHT_DETERMINISTIC`, `WEIGHT_STATISTICAL`, `WEIGHT_NARRATIVE` | Change to 0.50 / 0.30 / 0.20 |
| Amount thresholds | `CLAIM_AMOUNT_THRESHOLDS["HEALTH"]` | Change from 500,000 to 600,000 |
| Statistical baselines | `STATISTICAL_BASELINES["HEALTH"]["mean"]` | Update from historical data |
| Z-score sensitivity | `Z_SCORE_THRESHOLD` | Change from 2.5 to 3.0 (less sensitive) |
| Behavioral thresholds | `HIGH_CLAIM_FREQUENCY_THRESHOLD` | Change from 3 to 5 claims |
| AI timeout | `AI_TIMEOUT_SECONDS` | Change from 5 to 10 seconds |
| Privacy mode | `DEFAULT_PRIVACY_MODE` | Change from "balanced" to "strict" |
| Risk boundaries | `RISK_LEVEL_BOUNDARIES["HIGH"]` | Change from 0.70 to 0.75 |

**Critical**: After changing any threshold or weight, **bump `CONFIG_VERSION`** so you can trace which config produced which scores.

---

## Summary: Where to Make Common Changes

| I want to... | File(s) to modify |
|--------------|-------------------|
| Add a new fraud rule | [layer1_deterministic.py](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/fraud/layer1_deterministic.py) + [config.py](file:///e:/Projects/Insure-Flow-AI/app/config.py) (add threshold) |
| Add a new anomaly check | [layer2_statistical.py](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/fraud/layer2_statistical.py) + [config.py](file:///e:/Projects/Insure-Flow-AI/app/config.py) (add baseline/threshold) |
| Change fraud score weights | [config.py](file:///e:/Projects/Insure-Flow-AI/app/config.py) (`WEIGHT_*` variables) |
| Add external AI integration | [layer3_narrative.py](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/fraud/layer3_narrative.py) ([_call_external_ai()](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/fraud/layer3_narrative.py#181-201)) + [config.py](file:///e:/Projects/Insure-Flow-AI/app/config.py) (`ENABLE_EXTERNAL_AI`) |
| Change PII sanitization | [privacy.py](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/fraud/privacy.py) ([_apply_strict()](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/fraud/privacy.py#74-85), [_apply_balanced()](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/fraud/privacy.py#87-101)) |
| Add new document type for OCR | [ocr/parser.py](file:///e:/Projects/Insure-Flow-AI/app/ocr/parser.py) (add regex patterns) + [core/constants.py](file:///e:/Projects/Insure-Flow-AI/app/core/constants.py) (add enum) |
| Change file encryption | [utils/encryption.py](file:///e:/Projects/Insure-Flow-AI/app/utils/encryption.py) |
| Add new API endpoint | `api/v1/<module>.py` + [api/router.py](file:///e:/Projects/Insure-Flow-AI/app/api/router.py) |
| Add new claim validation | [services/claim_service.py](file:///e:/Projects/Insure-Flow-AI/app/services/claim_service.py) |
| Change fraud threshold | [config.py](file:///e:/Projects/Insure-Flow-AI/app/config.py) (`FRAUD_THRESHOLD`) |
| Add historical data for Layer 2 | [services/fraud_service.py](file:///e:/Projects/Insure-Flow-AI/app/services/fraud_service.py) (add to `claim_context` dict) |
| Add audit logging fields | [ai_agents/fraud/audit_logger.py](file:///e:/Projects/Insure-Flow-AI/app/ai_agents/fraud/audit_logger.py) |

---

## Testing Your Changes

After modifying any component:

```bash
# Test fraud engine in isolation
pytest tests/unit/test_fraud_agents.py -v

# Test full claim flow (requires DB)
pytest tests/integration/test_claim_service.py -v

# Test API endpoints (requires DB + running app)
pytest tests/e2e/test_api_flow.py -v
```
