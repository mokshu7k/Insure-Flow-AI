# InsureFlow — Target Workflow Description

## Vision

Transform InsureFlow into a **plugin tool** that integrates easily with the current ecosystem of insurance companies. Insurance companies already have patient/customer details as per their policies — InsureFlow plugs into that existing data and provides an intelligent claims processing pipeline.

---

## Data That Comes From the Insurer (Policy Purchase Time)

### Common to All Policy Types
- Policy schedule
- Policy number
- Coverage details
- Nominees
- Premium amount
- First premium receipt
- Terms & Conditions

### Vehicle Insurance Specific
- RC (Registration Certificate)
- Driving License
- Aadhaar
- PAN
- Income proof
- Address proof
- PUC (Pollution Under Control) Certificate

### Health Insurance Specific
- Aadhaar
- PAN
- Income proof
- Medical reports
- Medical history
- Prescriptions
- Policyholder's photo
- Address proof

### Extensibility
The schema is designed so that **more policy types** (Life, Travel, Property, etc.) can be easily added without schema changes — just by adding new `policy_type` + `document_requirement` configurations.

---

## Claims Workflow

### Step 1: User Sign-In
- User signs in with a **unique ID** provided by their insurer (`insurer_customer_id`).
- Upon sign-in, all policies linked to that ID are displayed with their current state (active, expired, lapsed, etc.).

### Step 2: Initiate Claim
- User selects a policy and initiates a claim.
- The system determines what documents are needed based on policy type + claim type.
- Documents are categorized as **compulsory** or **optional**.
- User provides their situation description and any additional context.

### Step 3: Document Upload & OCR
- User uploads required documents.
- Each document type has an **extraction template** — a structured definition of what fields the OCR/LLM should extract from that document.
- The extraction template is passed to the Gemini LLM along with the document so it can:
  - Extract fields correctly and completely.
  - Identify what's **missing** from the document.
  - Decide whether the document is acceptable or needs resubmission.
- This ensures **trash data is not ingested** — we catch problems at ingestion itself.

### Step 4: KYC Verification
- For identity documents (Aadhaar, PAN), the OCR'd data is **cross-checked against what's already stored in the DB** from when the user originally purchased the policy (insurer-side data).
- Mismatches are flagged immediately.

### Step 5: Document Validation Pipeline
1. **Structural validation** — MIME type, file size, corruption, blank page detection.
2. **OCR quality check** — Extraction confidence thresholds.
3. **Field completeness** — All required fields present per extraction template.
4. **KYC match** — Identity doc data matches stored KYC data.
5. **Rule-based checks** — Business rules (date logic, amount ranges, etc.).
6. **Authenticity checks** — QR code verification (Aadhaar), format validation (PAN), etc.

### Step 6: Fraud Detection
- Existing 6-layer fraud detection engine runs on the claim.
- Document-level fraud signals feed into Layer 4.
- Results determine risk level and whether manual review is needed.

### Step 7: Accept / Reject / Manual Review
- Based on fraud score + validation results, claims are:
  - Auto-approved (low risk, all docs valid)
  - Sent for manual review (medium risk or flagged docs)
  - Auto-rejected (high risk, critical failures)

### Step 8: Settlement
- Approved claims proceed to settlement (existing flow).
- QR tokens for cashless claims (existing flow).

---

## Key Design Principles

1. **Multi-tenant**: Multiple insurers can use the platform. Each insurer has their own policy types, document requirements, and configurations.
2. **Flexible policy types**: New insurance verticals (life, travel, property, marine, etc.) can be added through configuration — no code changes needed.
3. **Template-driven OCR**: What to extract from each document is defined in templates, not hardcoded. The LLM uses these templates for accurate extraction.
4. **KYC-first verification**: Identity verification happens against trusted insurer-provided data, not just self-reported information.
5. **Quality at ingestion**: Bad documents are caught immediately, not discovered downstream. Missing fields are reported back to the user with clear instructions.
6. **Full audit trail**: Every status change, document validation, and decision is tracked.
