// ── Auth ──────────────────────────────────────────
export interface LoginRequest { email: string; password: string; }
export interface RegisterRequest { email: string; password: string; role: UserRole; full_name?: string; }
export interface TokenResponse { access_token: string; refresh_token: string; token_type: string; user: User; }
export interface User { id: string; email: string; role: UserRole; is_active: boolean; created_at: string; }
export type UserRole = "CUSTOMER" | "PROVIDER" | "INSURER_ADMIN" | "AUDITOR" | "CLAIM_ADJUSTER";


// ── Claims ────────────────────────────────────────
export interface ClaimCreate {
    policy_number: string;
    claim_type: ClaimType;
    claim_amount?: number;
    description?: string;
}
export type ClaimType = "HEALTH" | "MOTOR" | "REIMBURSEMENT";
export type ClaimStatus =
    | "SUBMITTED" | "OCR_PROCESSED" | "UNDER_REVIEW" | "FRAUD_ANALYZED"
    | "APPROVED" | "REJECTED" | "MANUAL_REVIEW_REQUIRED" | "SETTLED";

export interface Claim {
    id: string;
    policy_number: string;
    user_id: string;
    claim_type: ClaimType;
    claim_amount: number | null;
    description: string | null;
    status: ClaimStatus;
    fraud_score: number | null;
    created_at: string;
    updated_at: string;
}
export interface ClaimListResponse { items: Claim[]; total: number; page: number; page_size: number; total_pages: number; }
export interface ClaimStatusUpdate { status: string; reason?: string; }

// ── Fraud ─────────────────────────────────────────
export interface LayerScore {
    score: number;
    flags: string[];
    layer: string;
    method?: string;
    ai_degraded?: boolean;
}

export interface FraudAssessment {
    id: string;
    claim_id: string;
    fraud_score: number;
    risk_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | null;
    explanation_text: string | null;
    layer_scores: Record<string, LayerScore> | null;
    layer_details: Record<string, unknown> | null;
    deterministic_signals: string[];
    statistical_signals: string[];
    behavioral_flags: string[];
    document_flags: string[];
    network_flags: string[];
    config_version: string | null;
    ai_degraded_mode: boolean | null;
    ml_model_used: boolean | null;
    created_at: string;
}

// ── Documents ─────────────────────────────────────
export type DocumentType = "INVOICE" | "PRESCRIPTION" | "MEDICAL_REPORT" | "DISCHARGE_SUMMARY" | "POLICE_REPORT" | "VEHICLE_RC" | "ESTIMATE" | "OTHER";
export interface DocumentResponse {
    id: string; claim_id: string; document_type: DocumentType;
    original_filename: string | null;
    content_type: string | null;
    extracted_data: Record<string, unknown> | null;
    extraction_confidence: number | null;
    requires_manual_review: boolean; created_at: string;
}
export interface ExtractionResult { extracted_fields: Record<string, unknown>; raw_text: string; confidence: number; requires_manual_review: boolean; }

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
export interface AdjusterChatResponse { response: string; claim_id?: string; }
export interface AdjusterReportResponse { report: string; claim_id: string; generated_at: string; }
