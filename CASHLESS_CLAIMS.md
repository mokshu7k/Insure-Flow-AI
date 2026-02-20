# Cashless Claims — Feature Documentation

## Overview

Cashless claims allow a patient to receive hospital treatment **without paying out of pocket**. Instead, the hospital directly coordinates with the insurance company for payment authorization. This feature implements that entire flow end-to-end using QR-based authorization tokens.

---

## How It Works — Step by Step

```
CUSTOMER           HOSPITAL (PROVIDER)          INSURER ADMIN
   │                        │                         │
   │  1. Files CASHLESS      │                         │
   │     claim (picks        │                         │
   │     hospital from       │                         │
   │     network)            │                         │
   │──────────────────────►  │                         │
   │                         │                         │
   │                         │  2. Hospital sees claim │
   │                         │     in their dashboard, │
   │                         │     enters estimate     │
   │                         │     details & generates │
   │                         │     a QR code           │
   │                         │                         │
   │  3. QR is shown/given   │                         │
   │     to patient at       │                         │
   │◄────────────────────────│                         │
   │     hospital            │                         │
   │                         │                         │
   │  4. Patient scans QR,   │                         │
   │     reviews estimate    │                         │
   │     details & accepts   │                         │
   │                         │                         │
   │  5. Acceptance sent ────────────────────────────► │
   │     to insurer          │                         │
   │                         │                         │
   │                         │  6. Insurer reviews, ◄──│
   │                         │     adjusts amount if   │
   │                         │     needed, then        │
   │                         │     PRE-AUTHORIZES or   │
   │                         │     REJECTS             │
   │                         │                         │
   │  7. Claim moves to      │                         │
   │     PRE_AUTHORIZED or   │                         │
   │     REJECTED status     │                         │
```

---

## Role-by-Role Walkthrough

### Step 1 — Customer Files a Cashless Claim

Login as `customer1@test.ai` → go to **Claims** → **New Claim**.

- Select claim type **Cashless**
- Enter policy number (e.g. `POL-CASHLESS-TEST-001`)
- Upload required documents (discharge summary, policy doc, ID proof)
- The claim is created with `status = SUBMITTED` and `provider_id` pointing to the chosen hospital

> Three test cashless claims are pre-seeded for `customer1@test.ai`, already assigned to `hospital@provider.ai`:
> - `POL-CASHLESS-2026-001` — ₹1,50,000
> - `POL-CASHLESS-2026-002` — ₹95,000
> - `POL-CASHLESS-TEST-001` — ₹50,000

---

### Step 2 — Hospital Generates QR Code

Login as `hospital@provider.ai` (password: `Provider@123`) → go to **Cashless** in the sidebar.

The hospital sees a list of all CASHLESS claims assigned to them. For each claim:

1. Click the claim row to open the **Generate QR** form
2. Fill in:
   - **Patient Name** — full name of the patient
   - **Estimate Amount** — the hospital's cost estimate (₹)
   - **Procedure Name** — e.g. "Knee Replacement Surgery"
   - **Hospital Name** — e.g. "Apollo Hospital, Chennai"
   - **Diagnosis / Notes** — optional additional details
3. Click **Generate QR Code**

The system:
- Creates a `QRToken` record in the database with `status = PENDING_REVIEW`
- Generates a cryptographically signed HMAC-SHA256 token (single-use, 30-minute expiry)
- Renders it as a QR code image (PNG, base64-encoded)
- Displays the QR on screen — the hospital can show this to the patient physically on a screen or print it

---

### Step 3 — Patient Scans and Reviews

Login as any CUSTOMER → go to **Cashless** in the sidebar.

The patient sees a **Scan QR** view:

1. Enter or paste the QR token string (from scanning the QR or copying it)
2. Click **Scan**
3. The system fetches and displays:
   - Policy Number
   - Claim Type
   - Patient Name
   - Procedure Name
   - Hospital Name
   - **Estimated Amount** (highlighted)
   - Expiry time
   - Any additional estimate details

4. The patient clicks **Accept Estimate** (or **Decline** to reject)

> **Note:** Any logged-in customer with the token can accept — the QR token itself is the security mechanism (HMAC-signed, single-use, time-limited). No account ownership check is enforced, matching real-world cashless workflows where a family member may also accept on behalf of the patient.

---

### Step 4 — Insurer Reviews and Pre-Authorizes

Login as `admin@insureflow.ai` (password: `Admin@123`) → go to **Cashless** in the sidebar.

The insurer sees a table of all claims pending authorization (status `ACCEPTED_BY_PATIENT`). For each:

- View: patient name, procedure, hospital, estimate amount
- Optionally adjust the approved amount (e.g. cap it per policy terms)
- Optionally add notes (reason for adjustment or rejection)
- Click **Pre-Authorize** or **Reject**

Results:
- **Pre-Authorize** → QR token status becomes `PRE_AUTHORIZED`, Claim status becomes `PRE_AUTHORIZED`
- **Reject** → QR token consumed, Claim status becomes `REJECTED`

---

## Claim Status Flow for Cashless

```
SUBMITTED
    │
    ├──► UNDER_REVIEW  (standard path — insurer manually reviews)
    │
    └──► PRE_AUTHORIZED  (cashless path — insurer pre-authorizes via QR)
              │
              ├──► SETTLED   (payment disbursed to hospital)
              └──► REJECTED  (authorization withdrawn)
```

---

## QR Token Lifecycle

| Status | Meaning |
|---|---|
| `PENDING_REVIEW` | QR generated by hospital, awaiting patient scan |
| `ACCEPTED_BY_PATIENT` | Patient reviewed and accepted the estimate |
| `PRE_AUTHORIZED` | Insurer approved — hospital can proceed |
| `REJECTED` | Insurer rejected the claim |
| `EXPIRED` | Token expired before patient scanned it (30-min window) |

---

## Security Design

| Mechanism | Detail |
|---|---|
| **HMAC-SHA256 signing** | Token is signed with `QR_SECRET_KEY` from `.env` — cannot be forged |
| **Single-use** | `used = True` once consumed; re-use is rejected |
| **Time-limited** | 30-minute expiry (configurable via `QR_TOKEN_EXPIRE_MINUTES` in config) |
| **Duplicate prevention** | Cannot generate a second active QR if one is already `PENDING_REVIEW` or `ACCEPTED_BY_PATIENT` |
| **Audit trail** | Every action (QR generated, accepted, pre-authorized, rejected) is written to the immutable `audit_logs` table |

---

## API Endpoints

All endpoints require a valid JWT Bearer token.

| Method | Path | Role | Description |
|---|---|---|---|
| `GET` | `/api/cashless/network-claims` | `PROVIDER` | List cashless claims assigned to this hospital |
| `POST` | `/api/cashless/generate-qr` | `PROVIDER` | Generate QR code for a cashless claim |
| `GET` | `/api/cashless/scan/{token}` | `CUSTOMER` | Scan token, return estimate details for review |
| `POST` | `/api/cashless/accept` | `CUSTOMER` | Accept the cashless estimate |
| `GET` | `/api/cashless/pending-authorizations` | `INSURER_ADMIN` | List claims awaiting insurer decision |
| `POST` | `/api/cashless/pre-authorize` | `INSURER_ADMIN` | Pre-authorize or reject a cashless claim |

### Example: Generate QR
```http
POST /api/cashless/generate-qr
Authorization: Bearer <provider_token>

{
  "claim_id": "uuid-of-claim",
  "estimate_amount": 95000,
  "patient_name": "Rahul Sharma",
  "procedure_name": "Laparoscopic Cholecystectomy",
  "hospital_name": "Apollo Hospital, Chennai",
  "estimate_data": { "diagnosis": "Gallstones", "ward": "General" }
}
```

### Example: Accept Estimate
```http
POST /api/cashless/accept
Authorization: Bearer <customer_token>

{
  "token": "<plaintext_token_from_qr>"
}
```

### Example: Pre-Authorize
```http
POST /api/cashless/pre-authorize
Authorization: Bearer <insurer_token>

{
  "qr_token_id": "uuid-of-qr-token",
  "decision": "PRE_AUTHORIZED",
  "approved_amount": 90000,
  "notes": "Approved as per policy limit. ₹5000 deducted (consumables not covered)."
}
```

---

## Database Changes

### Modified: `qr_tokens` table

New columns added via Alembic migration `4c78f0ad6d36`:

| Column | Type | Description |
|---|---|---|
| `provider_id` | UUID (FK → users) | Hospital that generated the QR |
| `status` | VARCHAR(32) | Cashless lifecycle status |
| `estimate_data` | JSONB | Free-form estimate details (diagnosis, ward, etc.) |
| `patient_name` | VARCHAR(255) | Patient name as entered by hospital |
| `procedure_name` | VARCHAR(255) | Procedure/treatment name |
| `hospital_name` | VARCHAR(255) | Hospital name |
| `insurer_notes` | TEXT | Notes added by insurer during authorization |

### Modified: `claims` table

No new columns — the existing `provider_id` (added in a previous migration) links the claim to the hospital. The `claim_type = 'CASHLESS'` and `status = 'PRE_AUTHORIZED'` values are new.

### New Claim Status

`PRE_AUTHORIZED` — added to `ClaimStatus` constants and the state machine transitions:
```
SUBMITTED → PRE_AUTHORIZED → SETTLED
                           → REJECTED
```

---

## Frontend Pages

### `/cashless` — Role-switching page

| Role | View |
|---|---|
| `PROVIDER` | List of network cashless claims + QR generation form |
| `CUSTOMER` | Token input + QR scan result + accept/decline controls |
| `INSURER_ADMIN` | Pending authorization queue + approve/reject controls |

### Navigation

A **Cashless** item (QR code icon) is shown in the left sidebar for all roles. The page content auto-adapts based on the logged-in user's role.

---

## Files Added / Modified

### New Files
| File | Purpose |
|---|---|
| `app/schemas/cashless.py` | Pydantic request/response schemas |
| `app/services/cashless_service.py` | All business logic |
| `app/api/cashless.py` | FastAPI router with 6 endpoints |
| `migrations/versions/4c78f0ad6d36_cashless_qr_extensions.py` | DB migration |
| `frontend/src/services/cashlessService.ts` | Frontend API client |
| `frontend/src/app/cashless/page.tsx` | Role-switching UI page |
| `CASHLESS_CLAIMS.md` | This document |

### Modified Files
| File | Change |
|---|---|
| `app/core/constants.py` | Added `CashlessStatus` class, `PRE_AUTHORIZED` claim status, cashless audit action constants |
| `app/models/qr_token.py` | Added 7 new columns for cashless flow |
| `app/api/router.py` | Registered cashless router |
| `requirements.txt` | Added `qrcode[pil]` |
| `frontend/src/types/index.ts` | Added `CASHLESS` to `ClaimType`, `PRE_AUTHORIZED` to `ClaimStatus`, all cashless TypeScript interfaces |
| `frontend/src/components/layout/LeftRail.tsx` | Added Cashless nav item |
| `frontend/src/components/ui/index.tsx` | Added cashless statuses to `StatusPill` |
| `frontend/src/app/dashboard/page.tsx` | Added CASHLESS color to charts |
| `frontend/src/app/claims/page.tsx` | Added `PRE_AUTHORIZED` to status filter |
| `frontend/src/app/claims/new/page.tsx` | Added CASHLESS to claim type wizard |
| `scripts/seed_data.py` | Added 3 seeded cashless claims |

---

## Test Credentials

| Role | Email | Password |
|---|---|---|
| Customer | `customer1@test.ai` | `Test1234!` |
| Hospital | `hospital@provider.ai` | `Provider@123` |
| Insurer | `admin@insureflow.ai` | `Admin@123` |

## Seeded Cashless Claims

All assigned to `hospital@provider.ai`, filed by `customer1@test.ai`:

| Policy Number | Amount | Status |
|---|---|---|
| `POL-CASHLESS-2026-001` | ₹1,50,000 | SUBMITTED |
| `POL-CASHLESS-2026-002` | ₹95,000 | SUBMITTED |
| `POL-CASHLESS-TEST-001` | ₹50,000 | SUBMITTED |

---

## Quick Demo Flow

1. Login as `hospital@provider.ai` → **Cashless** → click `POL-CASHLESS-TEST-001` → fill estimate form → **Generate QR**
2. Copy the token displayed
3. Login as `customer1@test.ai` (or any customer) → **Cashless** → paste token → **Scan** → **Accept Estimate**
4. Login as `admin@insureflow.ai` → **Cashless** → find the pending item → **Pre-Authorize**
5. Check the claim in **Claims** — status is now `PRE_AUTHORIZED`
