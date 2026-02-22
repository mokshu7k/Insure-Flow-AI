// ── Auth ──────────────────────────────────────────
export interface LoginRequest { email: string; password: string; }
export interface RegisterRequest { email: string; password: string; role: UserRole; full_name?: string; }
export interface TokenResponse { access_token: string; refresh_token: string; token_type: string; user: User; }
export interface User { id: string; email: string; role: UserRole; is_active: boolean; created_at: string; }
export type UserRole = "CUSTOMER" | "PROVIDER" | "INSURER_ADMIN" | "AUDITOR" | "CLAIM_ADJUSTER";


// ── Policies ──────────────────────────────────────
export interface Policy {
    id: string;
    user_id: string;
    policy_number: string;
    policy_type: "HEALTH" | "MOTOR" | "REIMBURSEMENT" | "CASHLESS";
    status: "ACTIVE" | "EXPIRED" | "CANCELLED";
    sum_insured: number;
    premium_amount: number;
    start_date: string;
    end_date: string;
    insured_name: string | null;
    insured_dob: string | null;
    nominee_name: string | null;
    meta_data: Record<string, unknown> | null;
    created_at: string;
    updated_at: string;
}
export interface PolicyListResponse { items: Policy[]; total: number; }

// ── Claims ────────────────────────────────────────
export interface ClaimCreate {
    // policy_number is NOT sent — backend resolves it from the user's active policy
    claim_type: ClaimType;
    claim_amount?: number;
    description?: string;
}
export type ClaimType = "HEALTH" | "MOTOR" | "REIMBURSEMENT";
export type ClaimStatus =
    | "SUBMITTED" | "OCR_PROCESSED" | "UNDER_REVIEW" | "FRAUD_ANALYZED"
    | "APPROVED" | "REJECTED" | "MANUAL_REVIEW_REQUIRED" | "SETTLED" | "PRE_AUTHORIZED";

// Mirrors backend ClaimStatus.TRANSITIONS
const ALLOWED_TRANSITIONS: Record<string, string[]> = {
    SUBMITTED:              ["UNDER_REVIEW", "PRE_AUTHORIZED", "MANUAL_REVIEW_REQUIRED", "APPROVED", "REJECTED"],
    UNDER_REVIEW:           ["APPROVED", "REJECTED", "MANUAL_REVIEW_REQUIRED"],
    MANUAL_REVIEW_REQUIRED: ["APPROVED", "REJECTED", "UNDER_REVIEW"],
    APPROVED:               ["SETTLED"],
    PRE_AUTHORIZED:         ["SETTLED", "REJECTED"],
    REJECTED:               [],
    SETTLED:                [],
};
export function canTransitionTo(currentStatus: string, targetStatus: string): boolean {
    return (ALLOWED_TRANSITIONS[currentStatus] ?? []).includes(targetStatus);
}

export interface Claim {
    id: string;
    policy_id: string | null;
    policy_number: string;  // denormalised from the resolved policy
    user_id: string;
    claim_type: ClaimType;
    claim_amount: number | null;
    description: string | null;
    status: ClaimStatus;
    fraud_score: number | null;
    adjuster_notes: string | null;
    verified_data: Record<string, unknown> | null;
    created_at: string;
    updated_at: string;
}
export interface ClaimListResponse { items: Claim[]; total: number; page: number; page_size: number; total_pages: number; }
export interface ClaimStatusUpdate { status: string; adjuster_notes?: string; }

// ── Fraud ─────────────────────────────────────────
export interface LayerScore {
    score: number;
    flags: string[];
    layer: string;
    weight?: number;
    method?: string;
    ai_degraded?: boolean;
}

export interface FraudAssessment {
    id: string;
    claim_id: string;
    fraud_score: number;
    risk_level: "MINIMAL" | "LOW" | "MEDIUM" | "HIGH" | "VERY_HIGH" | "CRITICAL" | null;
    explanation_text: string | null;
    layer_scores: Record<string, LayerScore> | null;
    layer_details: Record<string, unknown> | null;
    deterministic_signals: string[];
    statistical_signals: string[];
    behavioral_flags: string[];
    document_flags: string[];
    network_flags: string[];
    feature_snapshot: {
        manual_review_required?: boolean;
        manual_review_triggers?: string[];
        critical_signals?: string[];
        analyzed_document_id?: string;
    } | null;
    config_version: string | null;
    ai_degraded_mode: boolean | null;
    ml_model_used: boolean | null;
    created_at: string;
}

// ── Documents ─────────────────────────────────────
// Legacy document type union — used in the new-claim wizard DocSpec.
export type DocumentType = "AADHAAR" | "PAN" | "HOSPITAL_BILL" | "DISCHARGE_SUMMARY" | "PRESCRIPTION" | "CLAIM_FORM" | "LAB_REPORT" | "PHARMACY_BILL" | "PREAUTH_LETTER" | "FIR_REPORT" | "DEATH_CERTIFICATE" | "AMBULANCE_RECEIPT" | "OTHER";

// ── ClaimDocumentResponse — new template-aware OCR pipeline ──
export interface ClaimDocumentResponse {
    id: string;
    claim_id: string;
    document_type: string;         // alias for document_type_code (set by backend)
    document_type_code: string;
    document_requirement_id: string | null;
    original_filename: string | null;
    content_type: string | null;
    storage_path: string;
    // OCR / Extraction
    ocr_status: string;            // PENDING | PROCESSING | COMPLETED | FAILED
    extracted_data: Record<string, unknown> | null;
    extraction_confidence: number | null;
    extraction_template_used: Record<string, unknown> | null;
    // Promoted columns (visible in review step)
    patient_name: string | null;
    hospital_name: string | null;
    doctor_name: string | null;
    diagnosis: string | null;
    admission_date: string | null;
    discharge_date: string | null;
    total_amount: number | null;
    document_date: string | null;
    document_number: string | null;
    entity_gstin: string | null;
    entity_registration_no: string | null;
    // Validation
    validation_status: string | null;
    validation_reason: string | null;
    missing_fields: string[] | null;
    requires_manual_review: boolean;
    // Fraud / Authenticity
    authenticity_metadata_json: Record<string, unknown> | null;
    fraud_signal_weight: number | null;
    rejection_reason: string | null;
    created_at: string;
}

export interface ClaimDocumentListResponse {
    items: ClaimDocumentResponse[];
    total: number;
}

// ── Document requirements per policy ──
export interface DocumentRequirement {
    id: string;
    document_type_code: string;
    display_name: string;
    is_compulsory: boolean;
    allowed_mime_types: string[] | null;
    max_file_size_mb: number | null;
    instructions: string | null;
    field_keys: string[];          // required field keys (for hints)
}

export interface DocumentRequirementsListResponse {
    policy_id: string;
    policy_type_id: string | null;
    items: DocumentRequirement[];
    total: number;
}

// ── QR ────────────────────────────────────────────
export interface QRAuthorizationCreate { claim_id: string; provider_id: string; approved_limit: number; expiry_minutes?: number; }
export interface QRAuthorizationResponse { id: string; claim_id: string; provider_id: string; approved_limit: number; qr_token: string; expires_at: string; is_consumed: boolean; created_at: string; }
export interface QRValidationRequest { qr_token: string; }
export interface QRValidationResponse { valid: boolean; claim_id?: string; approved_limit?: number; provider_id?: string; message: string; }

// ── Settlements ───────────────────────────────────
export interface SettlementCreate { claim_id: string; amount: number; external_reference?: string; }
export interface Settlement { id: string; claim_id: string; settlement_reference_id: string; amount: number; status: "PROCESSING" | "COMPLETED" | "FAILED"; created_at: string; updated_at: string; }

// ── Dashboard ─────────────────────────────────────
export interface OverviewMetrics {
    total_claims: number; recent_claims_30d: number; pending_manual_review: number;
    total_settled_amount: number; average_fraud_score: number;
    status_breakdown: Record<string, number>; generated_at: string;
}
export interface FraudDistribution { buckets: Record<string, number>; total_assessed: number; high_risk_count: number; mean_score: number; generated_at: string; }
export interface SLAMetrics { average_days_to_decision: number | null; by_type: Record<string, number>; claims_analyzed: number; generated_at: string; }
export interface ComplianceSummary { claims_with_fraud_analysis: number; high_risk_claims: number; human_review_required_count: number; compliance_rate: number; generated_at: string; }

export interface CustomerRecentClaim {
    id: string;
    policy_number: string;
    claim_type: string;
    claim_amount: number | null;
    status: string;
    created_at: string;
    updated_at: string;
}
export interface CustomerMetrics {
    total_claims: number;
    active_claims: number;
    approved_claims: number;
    settled_claims: number;
    rejected_claims: number;
    total_claimed_amount: number;
    total_settled_amount: number;
    average_claim_amount: number;
    status_breakdown: Record<string, number>;
    type_breakdown: Record<string, number>;
    recent_claims: CustomerRecentClaim[];
    needs_action: string[];   // claim IDs needing manual review
    generated_at: string;
}

// ── Compliance ────────────────────────────────────
export interface AuditLogEntry { id: string; actor_id: string | null; action_type: string; entity_type: string; entity_id: string | null; metadata: Record<string, unknown>; timestamp: string; }
export interface ConsentRecord { id: string; version: string; timestamp: string; text_hash: string; }

// ── Adjuster Agent ────────────────────────────────
export interface AdjusterChatRequest { message: string; claim_id?: string; }
export interface AdjusterChatResponse { response: string; report?: string | null; }
export interface AdjusterReportResponse { report: string | null; claim_id: string; cached: boolean; generated_at?: string; }

// ── Cashless ──────────────────────────────────────
export interface CashlessQRRequest {
    claim_id: string;
    estimate_amount: number;
    patient_name: string;
    procedure_name: string;
    hospital_name: string;
    estimate_data?: Record<string, unknown>;
}
export interface CashlessQRResponse {
    id: string;
    claim_id: string;
    provider_id: string;
    token: string;
    approved_amount: number;
    patient_name: string | null;
    procedure_name: string | null;
    hospital_name: string | null;
    estimate_data: Record<string, unknown> | null;
    status: string;
    expires_at: string;
    qr_image_base64: string;
}
export interface CashlessScanResponse {
    qr_token_id: string;
    claim_id: string;
    policy_number: string;
    claim_type: string;
    patient_name: string | null;
    procedure_name: string | null;
    hospital_name: string | null;
    estimate_amount: number;
    estimate_data: Record<string, unknown> | null;
    status: string;
    expires_at: string;
}
export interface CashlessAcceptRequest { token: string; }
export interface CashlessAcceptResponse { message: string; claim_id: string; status: string; }
export interface CashlessAuthorizationRequest {
    qr_token_id: string;
    decision: "PRE_AUTHORIZED" | "REJECTED";
    approved_amount?: number;
    notes?: string;
}
export interface CashlessAuthorizationResponse {
    message: string;
    claim_id: string;
    qr_token_id: string;
    status: string;
    approved_amount: number | null;
}
export interface CashlessPendingItem {
    qr_token_id: string;
    claim_id: string;
    policy_number: string;
    claim_type: string;
    patient_name: string | null;
    procedure_name: string | null;
    hospital_name: string | null;
    estimate_amount: number;
    estimate_data: Record<string, unknown> | null;
    status: string;
    accepted_at: string | null;
    expires_at: string;
}
export interface NetworkClaimItem {
    id: string;
    user_id: string;
    policy_number: string;
    claim_type: string;
    claim_amount: number | null;
    description: string | null;
    status: string;
    created_at: string;
    has_documents: boolean;
    has_qr: boolean;
}
export interface NetworkClaimsResponse { items: NetworkClaimItem[]; total: number; }

// ── Audit Agent ───────────────────────────────────
export interface AuditFinding {
    id: string;
    audit_run_id: string;
    finding_type: string;
    severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
    entity_type: string;
    entity_id: string;
    supporting_entity_ids: string[];
    description: string;
    gemini_narrative: string | null;
    recommended_action: string | null;
    evidence: Record<string, unknown>;
    created_at: string;
}
export interface AuditRun {
    id: string;
    run_id: string;
    status: "RUNNING" | "COMPLETED" | "COMPLETED_WITH_ERRORS" | "FAILED";
    started_at: string;
    completed_at: string | null;
    total_findings: number;
    critical_count: number;
    high_count: number;
    medium_count: number;
    low_count: number;
    summary_narrative: string | null;
    errors: Record<string, string>;
    created_at: string;
}
export interface AuditRunDetail extends AuditRun { findings: AuditFinding[]; }
export interface AuditRunListResponse { items: AuditRun[]; total: number; page: number; page_size: number; }
export interface AuditFindingListResponse { items: AuditFinding[]; total: number; page: number; page_size: number; }
export interface AuditTriggerResponse { run_id: string; status: string; message: string; }
