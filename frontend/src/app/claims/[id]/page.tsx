"use client";
import { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";
import { CommandLayout } from "@/components/layout/CommandLayout";
import { AuditTrailPanel } from "@/components/layout/AuditTrailPanel";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { FraudScoreBadge, StatusPill, MonoValue } from "@/components/ui";
import { useAuthStore, useIsAdmin } from "@/store/authStore";
import { fraudService } from "@/services/fraudService";
import { claimService } from "@/services/claimService";
import { documentService } from "@/services/documentService";
import type { Claim, FraudAssessment, DocumentResponse } from "@/types";
import {
    ArrowLeft, Zap, Upload, FileText, CheckCircle, XCircle, AlertTriangle,
    ChevronDown, ChevronUp, Lock
} from "lucide-react";

function formatCurrency(n: number | null) {
    if (!n) return "—";
    return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n);
}
function formatDateTime(dt: string) {
    return new Date(dt).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

const LAYER_LABELS: Record<string, string> = {
    deterministic: "Rules", statistical: "Statistics", behavioral: "Behavior",
    document: "Documents", network: "Network", narrative: "Narrative (AI)",
};

function LayerScoreRow({ name, score, flags }: { name: string; score: number; flags: string[] }) {
    const [expanded, setExpanded] = useState(false);
    const color = score >= 0.7 ? "var(--crimson)" : score >= 0.4 ? "var(--amber)" : "var(--green)";
    return (
        <div className="layer-row" style={{ display: "block", padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
            <div style={{ display: "grid", gridTemplateColumns: "130px 1fr 60px 20px", alignItems: "center", gap: 10 }}>
                <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 500 }}>{LAYER_LABELS[name] || name}</span>
                <div className="score-bar">
                    <div className="score-bar-fill" style={{ width: `${score * 100}%`, background: color }} />
                </div>
                <span className="mono" style={{ fontSize: "0.75rem", color, textAlign: "right" }}>{(score * 100).toFixed(0)}%</span>
                {flags.length > 0 && (
                    <button onClick={() => setExpanded(!expanded)} style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", display: "flex" }}>
                        {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    </button>
                )}
            </div>
            {expanded && flags.length > 0 && (
                <div style={{ marginTop: 6, paddingLeft: 0, display: "flex", flexWrap: "wrap", gap: 4 }}>
                    {flags.map((f, i) => (
                        <span key={i} style={{ fontFamily: "var(--font-mono)", fontSize: "0.625rem", background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: 3, padding: "2px 6px", color: "var(--text-secondary)" }}>
                            {f}
                        </span>
                    ))}
                </div>
            )}
        </div>
    );
}

export default function ClaimDetailPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = use(params);
    const router = useRouter();
    const isAdmin = useIsAdmin();
    const [claim, setClaim] = useState<Claim | null>(null);
    const [assessment, setAssessment] = useState<FraudAssessment | null>(null);
    const [documents, setDocuments] = useState<DocumentResponse[]>([]);
    const [loading, setLoading] = useState(true);
    const [fraudLoading, setFraudLoading] = useState(false);
    const [actionLoading, setActionLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [uploadFile, setUploadFile] = useState<File | null>(null);
    const [uploadType, setUploadType] = useState("INVOICE");
    const [uploading, setUploading] = useState(false);

    const load = async () => {
        setLoading(true);
        try {
            const [c, docs] = await Promise.all([
                claimService.get(id),
                documentService.list(id),
            ]);
            setClaim(c);
            setDocuments(docs);
            // Try to fetch existing fraud assessment
            try {
                const a = await fraudService.getAssessment(id);
                setAssessment(a);
            } catch { /* 404 is fine */ }
        } catch (e: unknown) {
            setError("Claim not found");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { load(); }, [id]);

    const runFraud = async () => {
        setFraudLoading(true);
        try {
            const a = await fraudService.analyze(id);
            setAssessment(a);
            setClaim((prev) => prev ? { ...prev, fraud_score: a.fraud_score } : prev);
        } catch (e: unknown) {
            setError("Fraud analysis failed");
        } finally {
            setFraudLoading(false);
        }
    };

    const changeStatus = async (status: string) => {
        setActionLoading(true);
        try {
            const updated = await claimService.updateStatus(id, { status });
            setClaim(updated);
        } catch (e: unknown) {
            const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
            setError(msg || "Status update failed");
        } finally {
            setActionLoading(false);
        }
    };

    const handleUpload = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!uploadFile) return;
        setUploading(true);
        try {
            const doc = await documentService.upload(id, uploadFile, uploadType);
            setDocuments((prev) => [doc, ...prev]);
            setUploadFile(null);
        } catch {
            setError("Upload failed");
        } finally {
            setUploading(false);
        }
    };

    if (error) return (
        <AuthGuard><CommandLayout>
            <div style={{ padding: 40, textAlign: "center", color: "var(--crimson)" }}>{error}</div>
        </CommandLayout></AuthGuard>
    );

    return (
        <AuthGuard>
            <CommandLayout
                rightPanel={<AuditTrailPanel claimId={id} />}
                header={
                    <div style={{ display: "flex", alignItems: "center", gap: 10, width: "100%" }}>
                        <button onClick={() => router.push("/claims")} className="btn btn-ghost" style={{ padding: "4px 8px" }}>
                            <ArrowLeft size={14} />
                        </button>
                        <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "var(--text-muted)" }}>
                            {claim?.id.slice(0, 8)}…
                        </span>
                        {claim && <StatusPill status={claim.status} />}
                        {isAdmin && claim && (
                            <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
                                {claim.status !== "APPROVED" && claim.status !== "SETTLED" && (
                                    <button className="btn btn-ghost" onClick={() => changeStatus("APPROVED")} disabled={actionLoading} style={{ color: "var(--green)", borderColor: "var(--green-border)" }}>
                                        <CheckCircle size={13} /> Approve
                                    </button>
                                )}
                                <button className="btn btn-warning" onClick={() => changeStatus("MANUAL_REVIEW_REQUIRED")} disabled={actionLoading}>
                                    <AlertTriangle size={13} /> Flag
                                </button>
                                {claim.status !== "REJECTED" && (
                                    <button className="btn btn-danger" onClick={() => changeStatus("REJECTED")} disabled={actionLoading}>
                                        <XCircle size={13} /> Reject
                                    </button>
                                )}
                            </div>
                        )}
                    </div>
                }
            >
                {loading ? (
                    <div style={{ padding: 20 }}>
                        {[...Array(6)].map((_, i) => <div key={i} className="skeleton" style={{ height: 14, marginBottom: 12, width: `${70 + (i % 3) * 10}%` }} />)}
                    </div>
                ) : claim && (
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 0, height: "100%" }}>
                        {/* Left: Claim Details + Documents */}
                        <div style={{ padding: 20, overflowY: "auto", borderRight: "1px solid var(--border)" }}>
                            {/* Claim metadata */}
                            <div className="panel" style={{ padding: 18, marginBottom: 16 }}>
                                <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 14 }}>
                                    Claim Details
                                </div>
                                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px 20px" }}>
                                    {[
                                        ["Policy", claim.policy_number, true],
                                        ["Type", claim.claim_type, false],
                                        ["Amount", formatCurrency(claim.claim_amount), true],
                                        ["Status", null, false],
                                        ["Filed", formatDateTime(claim.created_at), true],
                                        ["Updated", formatDateTime(claim.updated_at), true],
                                    ].map(([label, value, mono]) => (
                                        <div key={label as string}>
                                            <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", marginBottom: 3, textTransform: "uppercase", letterSpacing: "0.04em" }}>{label}</div>
                                            {label === "Status" ? <StatusPill status={claim.status} /> :
                                                mono ? <MonoValue value={value as string} /> : <span style={{ fontSize: "0.8125rem" }}>{value}</span>
                                            }
                                        </div>
                                    ))}
                                </div>
                                {claim.description && (
                                    <div style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--border)" }}>
                                        <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.04em" }}>Description</div>
                                        <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>{claim.description}</p>
                                    </div>
                                )}
                            </div>

                            {/* Documents */}
                            <div className="panel" style={{ padding: 18, marginBottom: 16 }}>
                                <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 14, display: "flex", justifyContent: "space-between" }}>
                                    Documents
                                    <span style={{ color: "var(--text-primary)" }}>{documents.length}</span>
                                </div>
                                {documents.length === 0 && (
                                    <div style={{ color: "var(--text-muted)", fontSize: "0.8125rem", textAlign: "center", padding: "16px 0" }}>No documents uploaded</div>
                                )}
                                {documents.map((doc) => (
                                    <div key={doc.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
                                        <FileText size={14} color="var(--text-muted)" />
                                        <div style={{ flex: 1 }}>
                                            <div style={{ fontSize: "0.8125rem", fontWeight: 500 }}>{doc.document_type.replace(/_/g, " ")}</div>
                                            {doc.original_filename && <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.625rem", color: "var(--text-muted)" }}>{doc.original_filename}</div>}
                                        </div>
                                        {doc.requires_manual_review && <AlertTriangle size={13} color="var(--amber)" />}
                                        {doc.has_ocr_data && (
                                            <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.625rem", color: "var(--text-muted)" }}>
                                                OCR {doc.ocr_confidence ? `${(doc.ocr_confidence * 100).toFixed(0)}%` : "✓"}
                                            </span>
                                        )}
                                    </div>
                                ))}

                                {/* Upload form */}
                                <form onSubmit={handleUpload} style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--border)", display: "flex", gap: 8, alignItems: "flex-end" }}>
                                    <div style={{ flex: 1 }}>
                                        <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.04em" }}>Upload document</div>
                                        <input type="file" onChange={(e) => setUploadFile(e.target.files?.[0] || null)} style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }} />
                                    </div>
                                    <select className="input" style={{ width: "auto" }} value={uploadType} onChange={(e) => setUploadType(e.target.value)}>
                                        {["INVOICE", "PRESCRIPTION", "MEDICAL_REPORT", "DISCHARGE_SUMMARY", "POLICE_REPORT", "VEHICLE_RC", "ESTIMATE", "OTHER"].map((t) => (
                                            <option key={t} value={t}>{t.replace(/_/g, " ")}</option>
                                        ))}
                                    </select>
                                    <button type="submit" className="btn btn-ghost" disabled={!uploadFile || uploading}>
                                        <Upload size={13} />
                                        {uploading ? "…" : "Upload"}
                                    </button>
                                </form>
                            </div>
                        </div>

                        {/* Right: Fraud Analysis Panel */}
                        <div style={{ padding: 20, overflowY: "auto" }}>
                            {/* Fraud score header */}
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                                <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                                    Fraud Intelligence
                                </div>
                                {isAdmin && (
                                    <button className="btn btn-ghost" onClick={runFraud} disabled={fraudLoading} style={{ padding: "4px 10px" }}>
                                        <Zap size={13} />
                                        {fraudLoading ? "Analyzing…" : assessment ? "Re-run" : "Analyze"}
                                    </button>
                                )}
                            </div>

                            {!assessment && !fraudLoading && (
                                <div style={{ textAlign: "center", padding: "30px 0", color: "var(--text-muted)", fontSize: "0.8125rem" }}>
                                    {isAdmin ? "Run fraud analysis to see intelligence" : "No fraud assessment available"}
                                </div>
                            )}

                            {fraudLoading && (
                                <div style={{ textAlign: "center", padding: "20px 0", color: "var(--text-muted)", fontSize: "0.8125rem" }}>
                                    <div className="skeleton" style={{ height: 80, marginBottom: 12 }} />
                                    {[...Array(6)].map((_, i) => <div key={i} className="skeleton" style={{ height: 12, marginBottom: 10 }} />)}
                                </div>
                            )}

                            {assessment && !fraudLoading && (
                                <>
                                    <div style={{ display: "flex", justifyContent: "center", marginBottom: 20 }}>
                                        <FraudScoreBadge score={assessment.fraud_score} label />
                                    </div>

                                    {/* Risk level */}
                                    {assessment.risk_level && (
                                        <div style={{ textAlign: "center", marginBottom: 16 }}>
                                            <span className={`pill ${assessment.risk_level === "HIGH" || assessment.risk_level === "CRITICAL" ? "pill-rejected" : assessment.risk_level === "MEDIUM" ? "pill-review" : "pill-approved"}`}>
                                                {assessment.risk_level} RISK
                                            </span>
                                        </div>
                                    )}

                                    {/* Layer scores */}
                                    {assessment.layer_scores && (
                                        <div style={{ marginBottom: 16 }}>
                                            <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8, fontWeight: 600 }}>
                                                Layer Breakdown
                                            </div>
                                            {Object.entries(assessment.layer_scores).map(([name, layer]) => (
                                                <LayerScoreRow key={name} name={name} score={layer.score} flags={layer.flags || []} />
                                            ))}
                                        </div>
                                    )}

                                    {/* AI Explanation */}
                                    {assessment.explanation_text && (
                                        <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: 4, padding: 14, marginBottom: 14 }}>
                                            <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8, fontWeight: 600 }}>
                                                AI Explanation
                                            </div>
                                            <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", lineHeight: 1.7 }}>{assessment.explanation_text}</p>
                                        </div>
                                    )}

                                    {/* Meta */}
                                    <div style={{ fontSize: "0.625rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)", display: "flex", flexDirection: "column", gap: 3 }}>
                                        {assessment.config_version && <span>Config: {assessment.config_version}</span>}
                                        {assessment.ai_degraded_mode && <span style={{ color: "var(--amber)" }}>⚠ AI degraded mode</span>}
                                        <span>Assessed: {formatDateTime(assessment.created_at)}</span>
                                    </div>
                                </>
                            )}
                        </div>
                    </div>
                )}
            </CommandLayout>
        </AuthGuard>
    );
}
