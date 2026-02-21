"""
Seed script — populates test users, policies, claims, and a settlement so dashboards have real data.

Run from project root:
    venv/Scripts/python scripts/seed_data.py

Idempotent: skips rows that already exist (matched by email / policy_number).
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Make sure imports resolve from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.claim import Claim
from app.models.insurer import Insurer
from app.models.policy import Policy
from app.models.policy_type import PolicyType
from app.models.document_requirement import DocumentRequirement
from app.models.settlement import Settlement
from app.models.user import User


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HEALTH DOCUMENT EXTRACTION TEMPLATES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AADHAAR_TEMPLATE = {
    "fields": [
        {"key": "aadhaar_number", "type": "string", "required": True, "label": "12-digit Aadhaar Number"},
        {"key": "full_name", "type": "string", "required": True, "label": "Full Name as printed"},
        {"key": "date_of_birth", "type": "date", "required": True, "label": "Date of Birth (DD/MM/YYYY)"},
        {"key": "gender", "type": "string", "required": True, "label": "Gender (M/F/O)"},
        {"key": "address", "type": "string", "required": False, "label": "Address"},
        {"key": "photo_present", "type": "boolean", "required": True, "label": "Is photo visible and clear?"},
        {"key": "qr_code_present", "type": "boolean", "required": False, "label": "Is QR code visible?"},
    ],
    "instructions": (
        "Extract the 12-digit Aadhaar number (may have spaces — store without spaces). "
        "Extract full name exactly as printed. Extract DOB in DD/MM/YYYY format. "
        "Note if the photo is clearly visible. Check if QR code is present. "
        "If masked Aadhaar (only last 4 digits visible), set aadhaar_number to 'XXXX-XXXX-{last4}'."
    ),
}
AADHAAR_RULES = {"rules": [
    {"field": "aadhaar_number", "check": "regex", "pattern": r"^\d{12}$", "message": "Aadhaar must be exactly 12 digits"},
    {"field": "date_of_birth", "check": "date_not_future", "message": "DOB cannot be a future date"},
    {"field": "gender", "check": "in_set", "values": ["M", "F", "O"], "message": "Gender must be M, F, or O"},
    {"field": "photo_present", "check": "equals", "value": True, "message": "Photo must be clearly visible"},
]}

PAN_TEMPLATE = {
    "fields": [
        {"key": "pan_number", "type": "string", "required": True, "label": "PAN Number (10 chars)"},
        {"key": "full_name", "type": "string", "required": True, "label": "Full Name"},
        {"key": "father_name", "type": "string", "required": False, "label": "Father's Name"},
        {"key": "date_of_birth", "type": "date", "required": True, "label": "Date of Birth"},
        {"key": "photo_present", "type": "boolean", "required": True, "label": "Is photo visible?"},
    ],
    "instructions": (
        "Extract the 10-character PAN (format: ABCDE1234F). "
        "Extract full name, father's name, and DOB in DD/MM/YYYY."
    ),
}
PAN_RULES = {"rules": [
    {"field": "pan_number", "check": "regex", "pattern": r"^[A-Z]{5}[0-9]{4}[A-Z]$", "message": "Invalid PAN format"},
    {"field": "date_of_birth", "check": "date_not_future", "message": "DOB cannot be future"},
    {"field": "photo_present", "check": "equals", "value": True, "message": "Photo must be visible"},
]}

HOSPITAL_BILL_TEMPLATE = {
    "fields": [
        {"key": "hospital_name", "type": "string", "required": True, "label": "Hospital Name"},
        {"key": "hospital_address", "type": "string", "required": True, "label": "Hospital Address"},
        {"key": "hospital_registration_no", "type": "string", "required": True, "label": "Hospital Registration / ROHINI ID"},
        {"key": "hospital_gstin", "type": "string", "required": True, "label": "Hospital GSTIN (15-char)"},
        {"key": "patient_name", "type": "string", "required": True, "label": "Patient Name"},
        {"key": "admission_date", "type": "date", "required": True, "label": "Date of Admission"},
        {"key": "discharge_date", "type": "date", "required": True, "label": "Date of Discharge"},
        {"key": "bill_number", "type": "string", "required": True, "label": "Bill / Invoice Number"},
        {"key": "bill_date", "type": "date", "required": True, "label": "Bill Date"},
        {"key": "total_amount", "type": "number", "required": True, "label": "Total Bill Amount (₹)"},
        {"key": "net_payable", "type": "number", "required": True, "label": "Net Amount Payable (₹)"},
        {"key": "room_charges", "type": "number", "required": False, "label": "Room Charges"},
        {"key": "doctor_fees", "type": "number", "required": False, "label": "Doctor Fees"},
        {"key": "medicine_charges", "type": "number", "required": False, "label": "Medicine Charges"},
        {"key": "surgery_charges", "type": "number", "required": False, "label": "Surgery Charges"},
        {"key": "line_items", "type": "array", "required": False, "label": "Itemized line items",
         "item_fields": [{"key": "description", "type": "string"}, {"key": "quantity", "type": "number"}, {"key": "rate", "type": "number"}, {"key": "amount", "type": "number"}]},
    ],
    "instructions": (
        "Extract ALL charges broken down by category. CRITICAL: Extract hospital GSTIN (15-char) "
        "and registration/ROHINI ID. total_amount is gross; net_payable is what patient owes. "
        "Dates in DD/MM/YYYY. Amounts in INR as numbers without commas."
    ),
}
HOSPITAL_BILL_RULES = {"rules": [
    {"field": "hospital_gstin", "check": "regex", "pattern": "^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z][Z][0-9A-Z]$", "message": "Invalid GSTIN format"},
    {"field": "hospital_registration_no", "check": "not_empty", "message": "Hospital registration/ROHINI ID is required"},
    {"field": "total_amount", "check": "range", "min": 1, "max": 50000000, "message": "Amount out of range"},
    {"field": "admission_date", "check": "date_not_future", "message": "Admission date cannot be future"},
    {"field": "discharge_date", "check": "date_not_future", "message": "Discharge date cannot be future"},
    {"field": "admission_date", "check": "date_before", "other_field": "discharge_date", "message": "Admission must be before discharge"},
]}

DISCHARGE_SUMMARY_TEMPLATE = {
    "fields": [
        {"key": "hospital_name", "type": "string", "required": True, "label": "Hospital Name"},
        {"key": "patient_name", "type": "string", "required": True, "label": "Patient Name"},
        {"key": "admission_date", "type": "date", "required": True, "label": "Date of Admission"},
        {"key": "discharge_date", "type": "date", "required": True, "label": "Date of Discharge"},
        {"key": "primary_diagnosis", "type": "string", "required": True, "label": "Primary Diagnosis"},
        {"key": "procedures_performed", "type": "array_of_strings", "required": False, "label": "Procedures / Surgeries"},
        {"key": "treating_doctor_name", "type": "string", "required": True, "label": "Treating Doctor Name"},
        {"key": "condition_at_discharge", "type": "string", "required": True, "label": "Condition at Discharge"},
        {"key": "medications_at_discharge", "type": "array", "required": False, "label": "Discharge Medications",
         "item_fields": [{"key": "name", "type": "string"}, {"key": "dosage", "type": "string"}, {"key": "frequency", "type": "string"}, {"key": "duration", "type": "string"}]},
    ],
    "instructions": (
        "Extract full clinical picture: diagnosis (primary + secondary), procedures, treating doctor, "
        "and discharge condition. Dates in DD/MM/YYYY."
    ),
}
DISCHARGE_SUMMARY_RULES = {"rules": [
    {"field": "admission_date", "check": "date_not_future", "message": "Admission date cannot be future"},
    {"field": "discharge_date", "check": "date_not_future", "message": "Discharge date cannot be future"},
    {"field": "admission_date", "check": "date_before", "other_field": "discharge_date", "message": "Admission must be before discharge"},
]}

PRESCRIPTION_TEMPLATE = {
    "fields": [
        {"key": "doctor_name", "type": "string", "required": True, "label": "Doctor Name"},
        {"key": "doctor_registration_no", "type": "string", "required": False, "label": "Doctor Registration No."},
        {"key": "patient_name", "type": "string", "required": True, "label": "Patient Name"},
        {"key": "prescription_date", "type": "date", "required": True, "label": "Prescription Date"},
        {"key": "diagnosis", "type": "string", "required": True, "label": "Diagnosis"},
        {"key": "medications", "type": "array", "required": True, "label": "Medications",
         "item_fields": [{"key": "name", "type": "string"}, {"key": "dosage", "type": "string"}, {"key": "frequency", "type": "string"}, {"key": "duration", "type": "string"}]},
        {"key": "doctor_signature_present", "type": "boolean", "required": True, "label": "Doctor Signature/Stamp Present?"},
    ],
    "instructions": "Extract ALL medications with dosage, frequency, duration. Doctor signature/stamp is mandatory.",
}
PRESCRIPTION_RULES = {"rules": [
    {"field": "prescription_date", "check": "date_not_future", "message": "Prescription date cannot be future"},
    {"field": "doctor_signature_present", "check": "equals", "value": True, "message": "Doctor signature/stamp required"},
    {"field": "medications", "check": "min_length", "min": 1, "message": "At least one medication must be listed"},
]}

CLAIM_FORM_TEMPLATE = {
    "fields": [
        {"key": "patient_name", "type": "string", "required": True, "label": "Patient Name"},
        {"key": "policy_number", "type": "string", "required": True, "label": "Policy Number"},
        {"key": "hospital_name", "type": "string", "required": True, "label": "Hospital Name"},
        {"key": "admission_date", "type": "date", "required": True, "label": "Date of Admission"},
        {"key": "diagnosis", "type": "string", "required": True, "label": "Diagnosis"},
        {"key": "estimated_cost", "type": "number", "required": False, "label": "Total Cost (₹)"},
        {"key": "patient_signature_present", "type": "boolean", "required": True, "label": "Patient Signature Present?"},
        {"key": "hospital_stamp_present", "type": "boolean", "required": True, "label": "Hospital Stamp Present?"},
    ],
    "instructions": "Extract policy number (critical), patient/hospital details, diagnosis. Both patient signature and hospital stamp must be present.",
}
CLAIM_FORM_RULES = {"rules": [
    {"field": "patient_signature_present", "check": "equals", "value": True, "message": "Patient signature required"},
    {"field": "hospital_stamp_present", "check": "equals", "value": True, "message": "Hospital stamp required"},
]}

LAB_REPORT_TEMPLATE = {
    "fields": [
        {"key": "lab_name", "type": "string", "required": True, "label": "Lab / Diagnostic Center"},
        {"key": "patient_name", "type": "string", "required": True, "label": "Patient Name"},
        {"key": "sample_date", "type": "date", "required": True, "label": "Sample Date"},
        {"key": "report_date", "type": "date", "required": True, "label": "Report Date"},
        {"key": "test_results", "type": "array", "required": True, "label": "Test Results",
         "item_fields": [{"key": "test_name", "type": "string"}, {"key": "result_value", "type": "string"}, {"key": "unit", "type": "string"}, {"key": "reference_range", "type": "string"}, {"key": "is_abnormal", "type": "boolean"}]},
    ],
    "instructions": "Extract ALL test results with values, units, reference ranges. Flag abnormal values.",
}
LAB_REPORT_RULES = {"rules": [
    {"field": "sample_date", "check": "date_not_future", "message": "Sample date cannot be future"},
    {"field": "test_results", "check": "min_length", "min": 1, "message": "At least one test result required"},
]}

PHARMACY_BILL_TEMPLATE = {
    "fields": [
        {"key": "pharmacy_name", "type": "string", "required": True, "label": "Pharmacy Name"},
        {"key": "pharmacy_license", "type": "string", "required": True, "label": "Drug License Number"},
        {"key": "bill_number", "type": "string", "required": True, "label": "Bill Number"},
        {"key": "bill_date", "type": "date", "required": True, "label": "Bill Date"},
        {"key": "items", "type": "array", "required": True, "label": "Medicine Items",
         "item_fields": [{"key": "medicine_name", "type": "string"}, {"key": "quantity", "type": "number"}, {"key": "amount", "type": "number"}]},
        {"key": "total_amount", "type": "number", "required": True, "label": "Total Amount (₹)"},
    ],
    "instructions": "Extract each medicine with batch/expiry/quantity/amount. Drug license (DL-) is critical for verification.",
}
PHARMACY_BILL_RULES = {"rules": [
    {"field": "pharmacy_license", "check": "not_empty", "message": "Drug license number is required"},
    {"field": "bill_date", "check": "date_not_future", "message": "Bill date cannot be future"},
    {"field": "total_amount", "check": "range", "min": 1, "max": 5000000, "message": "Amount out of range"},
]}

PREAUTH_LETTER_TEMPLATE = {
    "fields": [
        {"key": "insurer_name", "type": "string", "required": True, "label": "Insurance Company"},
        {"key": "preauth_number", "type": "string", "required": True, "label": "Pre-authorization Number"},
        {"key": "policy_number", "type": "string", "required": True, "label": "Policy Number"},
        {"key": "patient_name", "type": "string", "required": True, "label": "Patient Name"},
        {"key": "hospital_name", "type": "string", "required": True, "label": "Hospital Name"},
        {"key": "approved_amount", "type": "number", "required": True, "label": "Approved Amount (₹)"},
        {"key": "diagnosis", "type": "string", "required": True, "label": "Diagnosis"},
        {"key": "approval_date", "type": "date", "required": True, "label": "Approval Date"},
    ],
    "instructions": "Extract approved amount, policy number, and approval date. Note any conditions or exclusions.",
}
PREAUTH_RULES = {"rules": [
    {"field": "approved_amount", "check": "range", "min": 1, "max": 50000000, "message": "Amount out of range"},
    {"field": "approval_date", "check": "date_not_future", "message": "Approval date cannot be future"},
]}

FIR_MLC_TEMPLATE = {
    "fields": [
        {"key": "fir_number", "type": "string", "required": False, "label": "FIR Number"},
        {"key": "incident_date", "type": "date", "required": True, "label": "Date of Incident"},
        {"key": "incident_description", "type": "string", "required": True, "label": "Incident Description"},
        {"key": "patient_name", "type": "string", "required": True, "label": "Patient/Victim Name"},
        {"key": "injuries_described", "type": "string", "required": False, "label": "Injuries Described"},
        {"key": "mlc_number", "type": "string", "required": False, "label": "MLC Number"},
    ],
    "instructions": "Required for accident/injury claims. Extract FIR number, incident details, and injury description.",
}
FIR_MLC_RULES = {"rules": [
    {"field": "incident_date", "check": "date_not_future", "message": "Incident date cannot be future"},
]}

DEATH_CERTIFICATE_TEMPLATE = {
    "fields": [
        {"key": "deceased_name", "type": "string", "required": True, "label": "Name of Deceased"},
        {"key": "date_of_death", "type": "date", "required": True, "label": "Date of Death"},
        {"key": "cause_of_death", "type": "string", "required": True, "label": "Cause of Death"},
        {"key": "registration_number", "type": "string", "required": True, "label": "Death Registration Number"},
        {"key": "issuing_authority", "type": "string", "required": True, "label": "Issuing Authority"},
    ],
    "instructions": "Extract cause of death carefully — must be consistent with claim diagnosis. Registration number required.",
}
DEATH_CERTIFICATE_RULES = {"rules": [
    {"field": "date_of_death", "check": "date_not_future", "message": "Date of death cannot be future"},
]}

AMBULANCE_RECEIPT_TEMPLATE = {
    "fields": [
        {"key": "ambulance_provider", "type": "string", "required": True, "label": "Ambulance Provider"},
        {"key": "date", "type": "date", "required": True, "label": "Date of Service"},
        {"key": "drop_location", "type": "string", "required": True, "label": "Drop Location (Hospital)"},
        {"key": "patient_name", "type": "string", "required": False, "label": "Patient Name"},
        {"key": "amount", "type": "number", "required": True, "label": "Amount Charged (₹)"},
    ],
    "instructions": "Extract service details. Drop location should match hospital on other documents.",
}
AMBULANCE_RECEIPT_RULES = {"rules": [
    {"field": "date", "check": "date_not_future", "message": "Date cannot be future"},
    {"field": "amount", "check": "range", "min": 100, "max": 100000, "message": "Amount seems unusual for ambulance"},
]}

HEALTH_DOCUMENT_REQUIREMENTS = [
    # ── COMPULSORY ──
    {"document_type_code": "AADHAAR", "display_name": "Aadhaar Card", "is_compulsory": True,
     "extraction_template": AADHAAR_TEMPLATE, "validation_rules": AADHAAR_RULES,
     "description": "Government-issued Aadhaar for identity verification",
     "instructions": "Upload front side with photo. Masked Aadhaar accepted.",
     "allowed_mime_types": ["image/jpeg", "image/png", "image/webp", "application/pdf"], "max_file_size_mb": 10, "sort_order": 1},
    {"document_type_code": "PAN", "display_name": "PAN Card", "is_compulsory": True,
     "extraction_template": PAN_TEMPLATE, "validation_rules": PAN_RULES,
     "description": "PAN card for identity and tax verification",
     "instructions": "Upload front side with photo visible.",
     "allowed_mime_types": ["image/jpeg", "image/png", "image/webp", "application/pdf"], "max_file_size_mb": 10, "sort_order": 2},
    {"document_type_code": "HOSPITAL_BILL", "display_name": "Hospital Bill / Invoice", "is_compulsory": True,
     "extraction_template": HOSPITAL_BILL_TEMPLATE, "validation_rules": HOSPITAL_BILL_RULES,
     "description": "Itemized hospital bill with all charges",
     "instructions": "Upload final hospital bill. If multi-page, use a single PDF.",
     "allowed_mime_types": ["image/jpeg", "image/png", "application/pdf"], "max_file_size_mb": 20, "sort_order": 3},
    {"document_type_code": "DISCHARGE_SUMMARY", "display_name": "Discharge Summary", "is_compulsory": True,
     "extraction_template": DISCHARGE_SUMMARY_TEMPLATE, "validation_rules": DISCHARGE_SUMMARY_RULES,
     "description": "Hospital discharge summary with diagnosis and doctor details",
     "instructions": "Must include diagnosis and treating doctor details.",
     "allowed_mime_types": ["image/jpeg", "image/png", "application/pdf"], "max_file_size_mb": 20, "sort_order": 4},
    {"document_type_code": "PRESCRIPTION", "display_name": "Doctor's Prescription", "is_compulsory": True,
     "extraction_template": PRESCRIPTION_TEMPLATE, "validation_rules": PRESCRIPTION_RULES,
     "description": "Doctor's prescription with diagnosis and medications",
     "instructions": "Must have doctor signature/stamp.",
     "allowed_mime_types": ["image/jpeg", "image/png", "application/pdf"], "max_file_size_mb": 15, "sort_order": 5},
    {"document_type_code": "CLAIM_FORM", "display_name": "Signed Claim Form", "is_compulsory": True,
     "extraction_template": CLAIM_FORM_TEMPLATE, "validation_rules": CLAIM_FORM_RULES,
     "description": "Insurance claim form signed by patient and stamped by hospital",
     "instructions": "Must be signed by you and stamped by the hospital.",
     "allowed_mime_types": ["image/jpeg", "image/png", "application/pdf"], "max_file_size_mb": 15, "sort_order": 6},
    # ── OPTIONAL ──
    {"document_type_code": "LAB_REPORT", "display_name": "Lab / Diagnostic Reports", "is_compulsory": False,
     "extraction_template": LAB_REPORT_TEMPLATE, "validation_rules": LAB_REPORT_RULES,
     "description": "Blood tests, imaging, or diagnostic results",
     "instructions": "Upload if tests were conducted. Include all pages.",
     "allowed_mime_types": ["image/jpeg", "image/png", "application/pdf"], "max_file_size_mb": 25, "sort_order": 7},
    {"document_type_code": "PHARMACY_BILL", "display_name": "Pharmacy Bills", "is_compulsory": False,
     "extraction_template": PHARMACY_BILL_TEMPLATE, "validation_rules": PHARMACY_BILL_RULES,
     "description": "Receipts for medicines bought outside the hospital",
     "instructions": "Upload pharmacy bills. Must show medicine names and amounts.",
     "allowed_mime_types": ["image/jpeg", "image/png", "application/pdf"], "max_file_size_mb": 10, "sort_order": 8},
    {"document_type_code": "PREAUTH_LETTER", "display_name": "Pre-authorization Letter", "is_compulsory": False,
     "extraction_template": PREAUTH_LETTER_TEMPLATE, "validation_rules": PREAUTH_RULES,
     "description": "Pre-auth / cashless approval letter from insurer",
     "instructions": "Upload if this is a cashless claim.",
     "allowed_mime_types": ["image/jpeg", "image/png", "application/pdf"], "max_file_size_mb": 10, "sort_order": 9},
    {"document_type_code": "FIR_REPORT", "display_name": "FIR / Medico-Legal Certificate", "is_compulsory": False,
     "extraction_template": FIR_MLC_TEMPLATE, "validation_rules": FIR_MLC_RULES,
     "description": "Police FIR or MLC — required for accident/injury claims",
     "instructions": "Upload FIR or MLC if claim is related to accident/injury.",
     "allowed_mime_types": ["image/jpeg", "image/png", "application/pdf"], "max_file_size_mb": 15, "sort_order": 10},
    {"document_type_code": "DEATH_CERTIFICATE", "display_name": "Death Certificate", "is_compulsory": False,
     "extraction_template": DEATH_CERTIFICATE_TEMPLATE, "validation_rules": DEATH_CERTIFICATE_RULES,
     "description": "Death certificate — required for death-related claims",
     "instructions": "Upload registered death certificate from municipal authority.",
     "allowed_mime_types": ["image/jpeg", "image/png", "application/pdf"], "max_file_size_mb": 10, "sort_order": 11},
    {"document_type_code": "AMBULANCE_RECEIPT", "display_name": "Ambulance Receipt", "is_compulsory": False,
     "extraction_template": AMBULANCE_RECEIPT_TEMPLATE, "validation_rules": AMBULANCE_RECEIPT_RULES,
     "description": "Receipt for ambulance services",
     "instructions": "Upload ambulance receipt if charges are part of your claim.",
     "allowed_mime_types": ["image/jpeg", "image/png", "application/pdf"], "max_file_size_mb": 10, "sort_order": 12},
]


# ────────────────────────────────────────────────────────────────────────────
#  DATA DEFINITIONS
# ────────────────────────────────────────────────────────────────────────────

USERS = [
    {
        "email": "admin@insureflow.ai",
        "password": "Admin@123",
        "role": "INSURER_ADMIN",
        "full_name": "InsureFlow Admin",
    },
    {
        "email": "customer1@test.ai",
        "password": "Test1234!",
        "role": "CUSTOMER",
        "full_name": "Rajesh Kumar",
        "phone": "9876543210",
    },
    {
        "email": "customer2@test.ai",
        "password": "Test1234!",
        "role": "CUSTOMER",
        "full_name": "Priya Sharma",
        "phone": "9876543211",
    },
    {
        "email": "adjuster@insureflow.ai",
        "password": "Admin@123",
        "role": "CLAIM_ADJUSTER",
        "full_name": "Claim Adjuster",
    },
    {
        "email": "hospital@provider.ai",
        "password": "Provider@123",
        "role": "PROVIDER",
        "full_name": "City Hospital",
    },
]

# Policies for customer1 — one active policy per claim type.
# (policy_number, policy_type, sum_insured, premium, start_date, end_date, meta_data)
_today = date.today()
POLICIES_TEMPLATE = [
    (
        "POL-HEALTH-2026-001",
        "HEALTH",
        500_000.0,
        12_000.0,
        date(2025, 1, 1),
        date(2026, 12, 31),
        {"network_hospitals": ["City Hospital", "Metro General"], "room_rent_limit": 5000},
    ),
    (
        "POL-MOTOR-2026-001",
        "MOTOR",
        300_000.0,
        8_500.0,
        date(2025, 6, 1),
        date(2026, 5, 31),
        {"vehicle_reg": "MH12AB1234", "make": "Maruti", "model": "Swift", "year": 2022},
    ),
    (
        "POL-REIMB-2026-001",
        "REIMBURSEMENT",
        200_000.0,
        5_000.0,
        date(2025, 3, 1),
        date(2026, 2, 28),
        {"plan": "Super Top-Up"},
    ),
    (
        "POL-CASHLESS-2026-001",
        "CASHLESS",
        400_000.0,
        15_000.0,
        date(2025, 1, 1),
        date(2026, 12, 31),
        {"network_hospitals": ["City Hospital", "Apollo", "Fortis"]},
    ),
]

# Claims for customer1 — covers all statuses & claim types.
# (policy_number, claim_type, claim_amount, status, fraud_score, daysAgo)
CLAIMS_TEMPLATE = [
    ("POL-HEALTH-2026-001", "HEALTH",         125_000.0,  "APPROVED",                 0.12,  25),
    ("POL-MOTOR-2026-001",  "MOTOR",            85_000.0,  "SETTLED",                  0.05,  40),
    ("POL-HEALTH-2026-001", "HEALTH",         250_000.0,  "MANUAL_REVIEW_REQUIRED",   0.78,  10),
    ("POL-REIMB-2026-001",  "REIMBURSEMENT",   32_000.0,  "SUBMITTED",              None,    2),
    ("POL-HEALTH-2026-001", "HEALTH",         175_000.0,  "REJECTED",                 0.92,  50),
    ("POL-MOTOR-2026-001",  "MOTOR",            45_000.0,  "UNDER_REVIEW",             0.33,   7),
    ("POL-HEALTH-2026-001", "HEALTH",         310_000.0,  "FRAUD_ANALYZED",           0.68,  14),
    ("POL-REIMB-2026-001",  "REIMBURSEMENT",   18_500.0,  "APPROVED",                 0.08,  30),
    # Handy test policies (low amounts so you can see them clearly)
    ("POL-HEALTH-2026-001", "HEALTH",           1.0,       "SUBMITTED",              None,    0),
    ("POL-MOTOR-2026-001",  "MOTOR",             1.0,       "SUBMITTED",              None,    0),
    ("POL-REIMB-2026-001",  "REIMBURSEMENT",    1.0,       "SUBMITTED",              None,    0),
]

# Cashless claims for customer1 assigned to hospital@provider.ai
CASHLESS_CLAIMS_TEMPLATE = [
    # (claim_amount, status, daysAgo)
    (75_000.0,  "SUBMITTED", 2),
    (120_000.0, "SUBMITTED", 1),
    (180_000.0, "SUBMITTED", 0),
]


# ────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ────────────────────────────────────────────────────────────────────────────

async def _seed_or_get_templates(db: AsyncSession) -> tuple[object, object]:
    """Idempotently seed insurer, policy type, and document requirements."""
    # Get or create DEMO_HEALTH insurer
    result = await db.execute(select(Insurer).where(Insurer.code == "DEMO_HEALTH"))
    insurer = result.scalar_one_or_none()
    if not insurer:
        insurer = Insurer(
            id=uuid.uuid4(),
            name="Demo Health Insurance Co.",
            code="DEMO_HEALTH",
            registration_number="IRDAI-DEMO-001",
            contact_email="admin@demo-health.com",
            is_active=True,
        )
        db.add(insurer)
        await db.flush()
        print("  + insurer  DEMO_HEALTH")
    else:
        print(f"  ~ skip insurer DEMO_HEALTH (exists)")

    # Get or create HEALTH_INDIVIDUAL policy type
    result = await db.execute(select(PolicyType).where(PolicyType.code == "HEALTH_INDIVIDUAL"))
    policy_type = result.scalar_one_or_none()
    if not policy_type:
        policy_type = PolicyType(
            id=uuid.uuid4(),
            insurer_id=insurer.id,
            category="HEALTH",
            code="HEALTH_INDIVIDUAL",
            name="Health Individual Plan",
            description="Individual health insurance policy with hospitalization coverage",
            config={
                "max_sum_insured": 1000000,
                "covers": ["hospitalization", "pre_post", "ambulance", "daycare"],
                "waiting_period_days": 30,
                "copay_pct": 10,
            },
            is_active=True,
        )
        db.add(policy_type)
        await db.flush()
        print("  + policy_type HEALTH_INDIVIDUAL")
    else:
        print(f"  ~ skip policy_type HEALTH_INDIVIDUAL (exists)")

    # Get or create document requirements
    existing_result = await db.execute(
        select(DocumentRequirement).where(DocumentRequirement.policy_type_id == policy_type.id)
    )
    existing_codes = {r.document_type_code for r in existing_result.scalars().all()}
    created = 0
    for req_data in HEALTH_DOCUMENT_REQUIREMENTS:
        if req_data["document_type_code"] not in existing_codes:
            db.add(DocumentRequirement(id=uuid.uuid4(), policy_type_id=policy_type.id, **req_data))
            created += 1
    if created:
        await db.flush()
        print(f"  + {created} document requirements")
    else:
        print(f"  ~ skip document requirements (all {len(existing_codes)} exist)")

    return insurer, policy_type


async def _get_or_create_user(db: AsyncSession, data: dict) -> tuple[User, bool]:
    result = await db.execute(select(User).where(User.email == data["email"]))
    existing = result.scalar_one_or_none()
    if existing:
        return existing, False
    user = User(
        id=uuid.uuid4(),
        email=data["email"],
        hashed_password=hash_password(data["password"]),
        role=data["role"],
        is_active=True,
        full_name=data.get("full_name"),
        phone=data.get("phone"),
    )
    db.add(user)
    return user, True


async def _get_or_create_policy(
    db: AsyncSession,
    user_id: uuid.UUID,
    policy_number: str,
    policy_type: str,
    sum_insured: float,
    premium_amount: float,
    start_date: date,
    end_date: date,
    meta_data: dict | None = None,
    insured_name: str = "Test Customer One",
    insurer_id: uuid.UUID | None = None,
    policy_type_id: uuid.UUID | None = None,
) -> tuple[Policy, bool]:
    result = await db.execute(select(Policy).where(Policy.policy_number == policy_number))
    existing = result.scalar_one_or_none()
    if existing:
        return existing, False
    policy = Policy(
        id=uuid.uuid4(),
        user_id=user_id,
        policy_number=policy_number,
        policy_type=policy_type,
        status="ACTIVE",
        sum_insured=sum_insured,
        premium_amount=premium_amount,
        start_date=start_date,
        end_date=end_date,
        insured_name=insured_name,
        meta_data=meta_data,
        insurer_id=insurer_id,
        policy_type_id=policy_type_id,
    )
    db.add(policy)
    return policy, True


async def _get_or_create_claim(
    db: AsyncSession,
    user_id: uuid.UUID,
    policy_id: uuid.UUID | None,
    policy_number: str,
    claim_type: str,
    claim_amount: float,
    status: str,
    fraud_score: float | None,
    days_ago: int,
) -> tuple[Claim, bool]:
    # Use a deterministic UUID so the seed is idempotent even when multiple
    # claims share the same policy_number.
    seed_key = f"{user_id}:{policy_number}:{claim_type}:{status}:{int(claim_amount)}:{days_ago}"
    deterministic_id = uuid.uuid5(uuid.NAMESPACE_DNS, seed_key)

    result = await db.execute(select(Claim).where(Claim.id == deterministic_id))
    existing = result.scalar_one_or_none()
    if existing:
        return existing, False
    ts = _utcnow() - timedelta(days=days_ago)
    short = str(deterministic_id).split("-")[0].upper()
    claim = Claim(
        id=deterministic_id,
        user_id=user_id,
        policy_id=policy_id,
        claim_number=f"CLM-{claim_type[:3]}-{short}",
        policy_number=policy_number,
        claim_type=claim_type,
        claim_amount=claim_amount,
        description=f"Test {claim_type.lower()} claim for policy {policy_number}",
        status=status,
        fraud_score=fraud_score,
        verified_data={"policy_snapshot": {"policy_id": str(policy_id), "policy_number": policy_number}} if policy_id else None,
    )
    db.add(claim)
    await db.flush()
    from sqlalchemy import update as sa_update
    await db.execute(
        sa_update(Claim).where(Claim.id == claim.id).values(created_at=ts)
    )
    return claim, True


async def _get_or_create_cashless_claim(
    db: AsyncSession,
    user_id: uuid.UUID,
    provider_id: uuid.UUID,
    policy_id: uuid.UUID | None,
    policy_number: str,
    claim_amount: float,
    status: str,
    days_ago: int,
    seq: int,
) -> tuple[Claim, bool]:
    unique_pol = f"{policy_number}-{seq:02d}"
    seed_key = f"{user_id}:CASHLESS:{unique_pol}:{status}:{int(claim_amount)}:{days_ago}"
    deterministic_id = uuid.uuid5(uuid.NAMESPACE_DNS, seed_key)

    result = await db.execute(select(Claim).where(Claim.id == deterministic_id))
    existing = result.scalar_one_or_none()
    if existing:
        return existing, False
    ts = _utcnow() - timedelta(days=days_ago)
    short = str(deterministic_id).split("-")[0].upper()
    claim = Claim(
        id=deterministic_id,
        user_id=user_id,
        provider_id=provider_id,
        policy_id=policy_id,
        claim_number=f"CLM-CAS-{short}",
        policy_number=unique_pol,
        claim_type="CASHLESS",
        claim_amount=claim_amount,
        description=f"Cashless claim for policy {unique_pol}",
        status=status,
        verified_data={"policy_snapshot": {"policy_id": str(policy_id), "policy_number": policy_number}} if policy_id else None,
    )
    db.add(claim)
    await db.flush()
    from sqlalchemy import update as sa_update
    await db.execute(
        sa_update(Claim).where(Claim.id == claim.id).values(created_at=ts)
    )
    return claim, True


# ────────────────────────────────────────────────────────────────────────────
#  MAIN
# ────────────────────────────────────────────────────────────────────────────

async def seed() -> None:
    async with AsyncSessionLocal() as db:
        print("\n── InsureFlow seed script ──────────────────────")

        # 1. Users
        created_users: dict[str, User] = {}
        users_created = 0
        for u_data in USERS:
            user, created = await _get_or_create_user(db, u_data)
            created_users[u_data["email"]] = user
            if created:
                users_created += 1
                print(f"  + user  {u_data['email']}  ({u_data['role']})")
            else:
                print(f"  ~ skip  {u_data['email']}  (exists)")
        await db.flush()

        # 1b. Seed insurer, policy type, and document requirements (idempotent)
        demo_insurer, health_pt = await _seed_or_get_templates(db)

        # 2. Policies for customer1
        customer = created_users["customer1@test.ai"]
        created_policies: dict[str, Policy] = {}
        policies_created = 0
        for (pol_num, pol_type, sum_ins, premium, start, end, meta) in POLICIES_TEMPLATE:
            _insurer_id = demo_insurer.id if (demo_insurer and pol_type == "HEALTH") else None
            _pt_id = health_pt.id if (health_pt and pol_type == "HEALTH") else None
            policy, created = await _get_or_create_policy(
                db, customer.id, pol_num, pol_type, sum_ins, premium, start, end, meta,
                insured_name=customer.full_name or "Test Customer One",
                insurer_id=_insurer_id,
                policy_type_id=_pt_id,
            )
            created_policies[pol_num] = policy
            if created:
                policies_created += 1
                print(f"  + policy {pol_num:<28} {pol_type}")
            else:
                print(f"  ~ skip  {pol_num:<28} (exists)")

        # 2b. Policies for customer2 (same types, different numbers)
        customer2 = created_users["customer2@test.ai"]
        POLICIES_C2 = [
            ("POL-HEALTH-C2-2026-001",  "HEALTH",        400_000.0, 10_000.0, date(2025, 1, 1), date(2026, 12, 31), {"plan": "Family Floater"}),
            ("POL-MOTOR-C2-2026-001",   "MOTOR",         250_000.0,  7_000.0, date(2025, 6, 1), date(2026, 5, 31),  {"vehicle_reg": "DL01AB5678", "make": "Honda", "model": "City", "year": 2021}),
            ("POL-REIMB-C2-2026-001",   "REIMBURSEMENT", 150_000.0,  4_000.0, date(2025, 3, 1), date(2026, 12, 31), {"plan": "Top-Up"}),
            ("POL-CASHLESS-C2-2026-001","CASHLESS",      350_000.0, 13_000.0, date(2025, 1, 1), date(2026, 12, 31), {"network_hospitals": ["Apollo", "Fortis", "Max"]}),
        ]
        for (pol_num, pol_type, sum_ins, premium, start, end, meta) in POLICIES_C2:
            _insurer_id2 = demo_insurer.id if (demo_insurer and pol_type == "HEALTH") else None
            _pt_id2 = health_pt.id if (health_pt and pol_type == "HEALTH") else None
            policy, created = await _get_or_create_policy(
                db, customer2.id, pol_num, pol_type, sum_ins, premium, start, end, meta,
                insured_name=customer2.full_name or "Test Customer Two",
                insurer_id=_insurer_id2,
                policy_type_id=_pt_id2,
            )
            if created:
                policies_created += 1
                print(f"  + policy {pol_num:<28} {pol_type}  (customer2)")
            else:
                print(f"  ~ skip  {pol_num:<28} (exists)")
        await db.flush()

        # Build lookup: claim_type → policy
        type_to_policy: dict[str, Policy] = {
            "HEALTH": created_policies.get("POL-HEALTH-2026-001"),
            "MOTOR": created_policies.get("POL-MOTOR-2026-001"),
            "REIMBURSEMENT": created_policies.get("POL-REIMB-2026-001"),
            "CASHLESS": created_policies.get("POL-CASHLESS-2026-001"),
        }

        # 3. Claims for customer1
        claims_created = 0
        created_claims: list[Claim] = []
        for (pol_num, ctype, amt, status, fscore, days) in CLAIMS_TEMPLATE:
            policy = type_to_policy.get(ctype)
            claim, created = await _get_or_create_claim(
                db, customer.id,
                policy.id if policy else None,
                pol_num, ctype, amt, status, fscore, days,
            )
            created_claims.append(claim)
            if created:
                claims_created += 1
                print(f"  + claim {pol_num:<28} {status}")
            else:
                print(f"  ~ skip  {pol_num:<28} (exists)")
        await db.flush()

        # 3b. Cashless claims for customer1 assigned to hospital
        hospital = created_users["hospital@provider.ai"]
        cashless_policy = type_to_policy.get("CASHLESS")
        cashless_pol_base = "POL-CASHLESS-2026"
        for seq, (amt, status, days) in enumerate(CASHLESS_CLAIMS_TEMPLATE, start=1):
            claim, created = await _get_or_create_cashless_claim(
                db, customer.id, hospital.id,
                cashless_policy.id if cashless_policy else None,
                cashless_pol_base, amt, status, days, seq,
            )
            created_claims.append(claim)
            pol_display = f"{cashless_pol_base}-{seq:02d}"
            if created:
                claims_created += 1
                print(f"  + claim {pol_display:<28} {status}  (CASHLESS → provider)")
            else:
                print(f"  ~ skip  {pol_display:<28} (exists)")
        await db.flush()

        # 4. Settlement for the SETTLED claim
        settled_claim = next((c for c in created_claims if c.status == "SETTLED"), None)
        settlement_created = 0
        if settled_claim:
            result = await db.execute(
                select(Settlement).where(Settlement.claim_id == settled_claim.id)
            )
            if not result.scalar_one_or_none():
                sett = Settlement(
                    id=uuid.uuid4(),
                    claim_id=settled_claim.id,
                    initiated_by=created_users["admin@insureflow.ai"].id,
                    amount=settled_claim.claim_amount,
                    status="COMPLETED",
                    settlement_reference=f"REF-{str(settled_claim.id)[:8].upper()}",
                    notes="Auto-seeded settlement",
                )
                db.add(sett)
                settlement_created += 1
                print(f"  + settlement for {settled_claim.policy_number}")
            else:
                print(f"  ~ skip  settlement (exists)")

        await db.commit()

        print(f"\n✓ Done — {users_created} users, {policies_created} policies, {claims_created} claims, {settlement_created} settlement(s) created.")
        print("\n── Test credentials ────────────────────────────")
        print("  admin@insureflow.ai     / Admin@123  (INSURER_ADMIN)")
        print("  customer1@test.ai       / Test1234!  (CUSTOMER)")
        print("  customer2@test.ai       / Test1234!  (CUSTOMER)")
        print("  adjuster@insureflow.ai  / Admin@123  (CLAIM_ADJUSTER)")
        print("  hospital@provider.ai    / Provider@123 (PROVIDER)")
        print("\n── Policies seeded for customer1 ───────────────")
        print("  POL-HEALTH-2026-001    HEALTH        ₹5,00,000  (ACTIVE)")
        print("  POL-MOTOR-2026-001     MOTOR         ₹3,00,000  (ACTIVE)")
        print("  POL-REIMB-2026-001     REIMBURSEMENT ₹2,00,000  (ACTIVE)")
        print("  POL-CASHLESS-2026-001  CASHLESS      ₹4,00,000  (ACTIVE)")
        print("\n── Policies seeded for customer2 ───────────────")
        print("  POL-HEALTH-C2-2026-001    HEALTH        ₹4,00,000  (ACTIVE)")
        print("  POL-MOTOR-C2-2026-001     MOTOR         ₹2,50,000  (ACTIVE)")
        print("  POL-REIMB-C2-2026-001     REIMBURSEMENT ₹1,50,000  (ACTIVE)")
        print("  POL-CASHLESS-C2-2026-001  CASHLESS      ₹3,50,000  (ACTIVE)")
        print("\n── Claim wizard notes ──────────────────────────")
        print("  Policy number is NOT needed at ingestion — it is resolved from DB.")
        print("  Just pick claim_type and the right policy is auto-selected.")
        print("────────────────────────────────────────────────\n")


if __name__ == "__main__":
    asyncio.run(seed())
