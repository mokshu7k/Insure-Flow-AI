"use client";
import { useEffect, useState, use, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { CommandLayout } from "@/components/layout/CommandLayout";
import { AuditTrailPanel } from "@/components/layout/AuditTrailPanel";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { FraudScoreBadge, StatusPill, MonoValue } from "@/components/ui";
import { EditableExtractedData } from "@/components/ui/EditableExtractedData";
import { useIsAdmin, useIsAdjuster } from "@/store/authStore";
import { fraudService } from "@/services/fraudService";
import { claimService } from "@/services/claimService";
import { documentService } from "@/services/documentService";
import { adjusterService } from "@/services/adjusterService";
import type { Claim, FraudAssessment, DocumentResponse } from "@/types";
import {
    ArrowLeft, Zap, Upload, FileText, CheckCircle, XCircle, AlertTriangle,
    ChevronDown, ChevronUp, Send, Loader2
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
    const isAdjuster = useIsAdjuster();
    const canAction = isAdmin || isAdjuster;
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
    const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
    const [docError, setDocError] = useState<string | null>(null);
    // Right-panel tabs
    const [rightTab, setRightTab] = useState<"fraud" | "agent">("fraud");
    // Adjuster report + follow-up chat state
    const [claimReport, setClaimReport] = useState<string | null>(null);
    const [reportLoading, setReportLoading] = useState(false);
    const [reportLoaded, setReportLoaded] = useState(false);
    const [agentMessages, setAgentMessages] = useState<{ role: "user" | "ai"; content: string }[]>([]);
    const [agentInput, setAgentInput] = useState("");
    const [agentSending, setAgentSending] = useState(false);
    const agentBottomRef = useRef<HTMLDivElement>(null);

    const load = async () => {
        setLoading(true);
        try {
            const [c, docs] = await Promise.all([
                claimService.get(id),
                documentService.listForClaim(id),
            ]);
            setClaim(c);
            setDocuments(docs);
            // Fetch existing fraud assessment (null if none yet)
            const a = await fraudService.getAssessment(id);
            if (a) setAssessment(a);
        } catch (e: unknown) {
            setError("Claim not found");
        } finally {
            setLoading(false);
        }
    };

    // Scroll agent chat to bottom
    useEffect(() => { agentBottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [agentMessages]);

    // Load the AI claim report when the tab is first opened (returns cached if already generated)
    const loadReport = useCallback(async () => {
        if (reportLoaded || !id) return;
        setReportLoaded(true);
        setReportLoading(true);
        try {
            const res = await adjusterService.generateReport(id);
            setClaimReport(res.report || null);
        } catch {
            setClaimReport(null);
        } finally {
            setReportLoading(false);
        }
    }, [reportLoaded, id]);

    useEffect(() => {
        if (rightTab === "agent" && canAction) loadReport();
    }, [rightTab, canAction, loadReport]);

    const sendAgentMessage = useCallback(async (text: string) => {
        const trimmed = text.trim();
        if (!trimmed || agentSending) return;
        setAgentInput("");
        setAgentMessages((prev) => [...prev, { role: "user", content: trimmed }]);
        setAgentSending(true);
        try {
            const res = await adjusterService.chat({ message: trimmed, claim_id: id });
            setAgentMessages((prev) => [...prev, { role: "ai", content: res.response }]);
        } catch {
            setAgentMessages((prev) => [...prev, { role: "ai", content: "Error processing request. Please try again." }]);
        } finally {
            setAgentSending(false);
        }
    }, [agentSending, id]);

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
                        {canAction && claim && (
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
                                    <div key={doc.id}>
                                        <button
                                            type="button"
                                            onClick={() => setSelectedDocId(selectedDocId === doc.id.toString() ? null : doc.id.toString())}
                                            style={{
                                                width: "100%",
                                                display: "flex",
                                                alignItems: "center",
                                                gap: 10,
                                                padding: "8px 0",
                                                borderBottom: "1px solid var(--border)",
                                                background: selectedDocId === doc.id.toString() ? "var(--bg-surface)" : "transparent",
                                                border: "none",
                                                cursor: "pointer",
                                                color: "inherit",
                                                textAlign: "left",
                                            }}
                                        >
                                            <FileText size={14} color="var(--text-muted)" />
                                            <div style={{ flex: 1 }}>
                                                <div style={{ fontSize: "0.8125rem", fontWeight: 500 }}>{doc.document_type.replace(/_/g, " ")}</div>
                                                {doc.original_filename && <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.625rem", color: "var(--text-muted)" }}>{doc.original_filename}</div>}
                                            </div>
                                            {doc.requires_manual_review && <AlertTriangle size={13} color="var(--amber)" />}
                                            {doc.extracted_data && Object.keys(doc.extracted_data).length > 0 && (
                                                <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.625rem", color: "var(--text-muted)" }}>
                                                    {doc.extraction_confidence ? `${(doc.extraction_confidence * 100).toFixed(0)}%` : "✓"}
                                                </span>
                                            )}
                                        </button>
                                        {selectedDocId === doc.id.toString() && doc.extracted_data && Object.keys(doc.extracted_data).length > 0 && (
                                            <div style={{ padding: "12px 0", borderBottom: "1px solid var(--border)" }}>
                                                <EditableExtractedData
                                                    document={doc}
                                                    onUpdate={(updated) => {
                                                        setDocuments((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
                                                        setSelectedDocId(null);
                                                    }}
                                                    onError={(error) => setDocError(error)}
                                                />
                                            </div>
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

                        {/* Right: Tabbed panel — Fraud | AI Assistant */}
                        <div style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
                            {/* Tab bar */}
                            {canAction && (
                                <div style={{ display: "flex", borderBottom: "1px solid var(--border)", flexShrink: 0 }}>
                                    {(["fraud", "agent"] as const).map((tab) => (
                                        <button
                                            key={tab}
                                            onClick={() => setRightTab(tab)}
                                            style={{
                                                flex: 1,
                                                padding: "9px 0",
                                                fontSize: "0.6875rem",
                                                fontWeight: 600,
                                                textTransform: "uppercase",
                                                letterSpacing: "0.06em",
                                                background: "none",
                                                border: "none",
                                                borderBottom: rightTab === tab ? "2px solid var(--blue)" : "2px solid transparent",
                                                color: rightTab === tab ? "var(--blue)" : "var(--text-muted)",
                                                cursor: "pointer",
                                            }}
                                        >
                                            {tab === "fraud" ? "Fraud" : "Claim Report"}
                                        </button>
                                    ))}
                                </div>
                            )}
                        <div style={{ flex: 1, overflowY: "auto", padding: 20, display: rightTab === "fraud" || !canAction ? "block" : "none" }}>
                            {/* Fraud score header */}
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                                <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                                    Fraud Intelligence
                                </div>
                                {canAction && (
                                    <button className="btn btn-ghost" onClick={runFraud} disabled={fraudLoading} style={{ padding: "4px 10px" }}>
                                        <Zap size={13} />
                                        {fraudLoading ? "Analyzing…" : assessment ? "Re-run" : "Analyze"}
                                    </button>
                                )}
                            </div>

                            {!assessment && !fraudLoading && (
                                <div style={{ textAlign: "center", padding: "30px 0", color: "var(--text-muted)", fontSize: "0.8125rem" }}>
                                    {canAction ? "Run fraud analysis to see intelligence" : "No fraud assessment available"}
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
                        </div>{/* end fraud tab */}

                            {/* Claim Report tab — auto-generated report + follow-up chat */}
                            {canAction && (
                                <div style={{ flex: 1, display: rightTab === "agent" ? "flex" : "none", flexDirection: "column", overflow: "hidden" }}>
                                    {/* Report section */}
                                    <div style={{ flex: claimReport ? "0 0 55%" : 1, overflowY: "auto", padding: "14px 16px", borderBottom: (claimReport || reportLoading) ? "1px solid var(--border)" : "none" }}>
                                        {reportLoading && (
                                            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                                                <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--text-muted)", fontSize: "0.75rem" }}>
                                                    <Loader2 size={13} style={{ animation: "spin 1s linear infinite" }} />
                                                    Generating claim report…
                                                </div>
                                                {[...Array(8)].map((_, i) => <div key={i} className="skeleton" style={{ height: 11, marginBottom: 6 }} />)}
                                            </div>
                                        )}
                                        {!reportLoading && claimReport && (
                                            <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", lineHeight: 1.75, whiteSpace: "pre-wrap", wordBreak: "break-word", fontFamily: "inherit" }}>
                                                {claimReport}
                                            </div>
                                        )}
                                        {!reportLoading && !claimReport && reportLoaded && (
                                            <div style={{ textAlign: "center", padding: "20px 0", color: "var(--text-muted)", fontSize: "0.8125rem" }}>
                                                Report generation failed. Ask a question below.
                                            </div>
                                        )}
                                    </div>
                                    {/* Follow-up chat — only shown once report is loaded */}
                                    {(claimReport || reportLoaded) && (
                                        <div style={{ flex: 1, overflowY: "auto", padding: "10px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
                                            {agentMessages.length === 0 && claimReport && (
                                                <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", textAlign: "center", padding: "8px 0" }}>
                                                    Ask a follow-up question about this report
                                                </div>
                                            )}
                                            {agentMessages.map((m, i) => (
                                                <div key={i} style={{
                                                    alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                                                    maxWidth: "92%",
                                                    background: m.role === "user" ? "var(--blue)" : "var(--bg-surface)",
                                                    color: m.role === "user" ? "#fff" : "var(--text-primary)",
                                                    border: m.role === "user" ? "none" : "1px solid var(--border)",
                                                    borderRadius: m.role === "user" ? "10px 4px 10px 10px" : "4px 10px 10px 10px",
                                                    padding: "7px 11px",
                                                    fontSize: "0.75rem",
                                                    lineHeight: 1.5,
                                                    whiteSpace: "pre-wrap",
                                                    wordBreak: "break-word",
                                                }}>
                                                    {m.content}
                                                </div>
                                            ))}
                                            {agentSending && (
                                                <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--text-muted)", fontSize: "0.75rem", alignSelf: "flex-start" }}>
                                                    <Loader2 size={12} style={{ animation: "spin 1s linear infinite" }} />
                                                    Thinking…
                                                </div>
                                            )}
                                            <div ref={agentBottomRef} />
                                        </div>
                                    )}
                                    {/* Input */}
                                    <div style={{ padding: "8px 12px", borderTop: "1px solid var(--border)", display: "flex", gap: 6 }}>
                                        <input
                                            className="input"
                                            style={{ flex: 1, height: 32, fontSize: "0.8125rem" }}
                                            value={agentInput}
                                            onChange={(e) => setAgentInput(e.target.value)}
                                            onKeyDown={(e) => { if (e.key === "Enter") sendAgentMessage(agentInput); }}
                                            placeholder="Ask a follow-up about this claim…"
                                            disabled={agentSending || reportLoading}
                                        />
                                        <button
                                            className="btn btn-primary"
                                            style={{ height: 32, padding: "0 10px" }}
                                            disabled={!agentInput.trim() || agentSending || reportLoading}
                                            onClick={() => sendAgentMessage(agentInput)}
                                        >
                                            <Send size={13} />
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>{/* end right tabbed panel */}
                    </div>
                )}
            </CommandLayout>
        </AuthGuard>
    );
}
