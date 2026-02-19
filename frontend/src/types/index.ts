// ── Auth ──────────────────────────────────────────
export interface LoginRequest {
    email: string;
    password: string;
}

export interface RegisterRequest {
    email: string;
    password: string;
    role: UserRole;
}

export interface TokenResponse {
    access_token: string;
    refresh_token: string;
    token_type: string;
}

export interface User {
    id: string;
    email: string;
    role: UserRole;
    is_active: boolean;
    created_at: string;
}

export type UserRole = "CUSTOMER" | "PROVIDER" | "INSURER_ADMIN" | "AUDITOR";

// ── Claims ────────────────────────────────────────
export interface ClaimCreate {
    policy_number: string;
    claim_type: ClaimType;
    claim_amount?: number;  // Optional during creation, set via update endpoint
}

export type ClaimType = "HEALTH" | "MOTOR" | "REIMBURSEMENT";

export type ClaimStatus =
    | "SUBMITTED"
    | "OCR_PROCESSED"
    | "UNDER_REVIEW"
    | "FRAUD_ANALYZED"
    | "APPROVED"
    | "REJECTED"
    | "MANUAL_REVIEW_REQUIRED"
    | "SETTLED";

export interface Claim {
    id: string;
    policy_number: string;
    user_id: string;
    claim_type: ClaimType;
    claim_amount: number;
    status: ClaimStatus;
    fraud_score: number | null;
    created_at: string;
    updated_at: string;
}

export interface ClaimListResponse {
    claims: Claim[];
    total: number;
    page: number;
    page_size: number;
}

export interface ClaimStatusUpdate {
    status: "APPROVED" | "REJECTED" | "MANUAL_REVIEW_REQUIRED";
    reason?: string;
}

// ── Fraud ─────────────────────────────────────────
export interface FraudAssessment {
    id: string;
    claim_id: string;
    fraud_score: number;
    risk_level: string | null;
    deterministic_signals: string[];
    statistical_signals: string[];
    behavioral_flags: string[];
    document_flags: string[];
    network_flags: string[];
    explanation_text: string;
    config_version: string | null;
    baseline_version: string | null;
    ai_degraded_mode: boolean | null;
    ml_model_used: boolean | null;
    created_at: string;
}

// ── Documents ─────────────────────────────────────
export type DocumentType =
    | "INVOICE"
    | "PRESCRIPTION"
    | "MEDICAL_REPORT"
    | "DISCHARGE_SUMMARY"
    | "POLICE_REPORT"
    | "VEHICLE_RC"
    | "ESTIMATE"
    | "OTHER";

export interface DocumentResponse {
    id: string;
    claim_id: string;
    document_type: DocumentType;
    has_ocr_data: boolean;
    ocr_confidence: number | null;
    requires_manual_review: boolean;
    created_at: string;
}

export interface OCRResult {
    extracted_fields: Record<string, unknown>;
    raw_text: string;
    confidence: number;
    requires_manual_review: boolean;
    ocr_metadata: Record<string, unknown>;
}

// ── QR ────────────────────────────────────────────
export interface QRAuthorizationCreate {
    claim_id: string;
    provider_id: string;
    approved_limit: number;
    expiry_minutes?: number;
}

export interface QRAuthorizationResponse {
    id: string;
    claim_id: string;
    provider_id: string;
    approved_limit: number;
    qr_token: string;
    expires_at: string;
    is_consumed: boolean;
    created_at: string;
}

export interface QRValidationRequest {
    qr_token: string;
}

export interface QRValidationResponse {
    valid: boolean;
    claim_id?: string;
    approved_limit?: number;
    provider_id?: string;
    message: string;
}

// ── Settlements ───────────────────────────────────
export interface SettlementCreate {
    claim_id: string;
    amount: number;
    external_reference?: string;
}

export interface Settlement {
    id: string;
    claim_id: string;
    settlement_reference_id: string;
    amount: number;
    status: "PROCESSING" | "COMPLETED" | "FAILED";
    created_at: string;
    updated_at: string;
}

export interface SettlementStatusUpdate {
    status: "PROCESSING" | "COMPLETED" | "FAILED";
}

// ── Dashboard ─────────────────────────────────────
export interface OverviewMetrics {
    total_claims: number;
    recent_claims_30d: number;
    pending_manual_review: number;
    total_settled_amount: number;
    average_fraud_score: number;
    status_breakdown: Record<string, number>;
    generated_at: string;
}

export interface FraudDistribution {
    buckets: Record<string, number>;
    total_assessed: number;
    high_risk_count: number;
    mean_score: number;
    generated_at: string;
}

export interface SLAMetrics {
    average_days_to_decision: number | null;
    by_type: Record<string, number>;
    claims_analyzed: number;
    generated_at: string;
}

export interface ComplianceSummary {
    claims_with_fraud_analysis: number;
    high_risk_claims: number;
    human_review_required_count: number;
    fraud_score_overrides: number;
    compliance_rate: number;
    generated_at: string;
}

// ── Compliance ────────────────────────────────────
export interface AuditLogEntry {
    id: string;
    actor_id: string | null;
    action_type: string;
    entity_type: string;
    entity_id: string | null;
    metadata: Record<string, unknown>;
    timestamp: string;
}

export interface AccessLogEntry {
    id: string;
    user_id: string;
    document_id: string;
    action: string;
    timestamp: string;
}

export interface ConsentRecord {
    id: string;
    version: string;
    timestamp: string;
    text_hash: string;
}
