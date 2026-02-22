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
import { complianceService } from "@/services/complianceService";
import type { Claim, FraudAssessment, ClaimDocumentResponse, AuditLogEntry } from "@/types";
import { canTransitionTo } from "@/types";
import {
    ArrowLeft, Upload, FileText, CheckCircle, XCircle, AlertTriangle,
    ChevronDown, ChevronUp, Send, Loader2, RefreshCw, Flag, Clock,
    CircleDot, CircleCheck, CircleX, FileUp, ShieldAlert, Sparkles, X
} from "lucide-react";
import { ClaimReportRenderer } from "@/components/ui/ClaimReportRenderer";
import { FraudAgentPanel } from "@/components/ui/FraudAgentPanel";

function formatCurrency(n: number | null) {
    if (!n) return "—";
    return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n);
}
function formatDateTime(dt: string | null | undefined) {
    if (!dt) return "—";
    const d = new Date(dt);
    if (isNaN(d.getTime())) return "—";
    return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

/* LayerScoreRow removed — replaced by FraudAgentPanel component */

function composeFlagReason(assessment: FraudAssessment | null, claim: { claim_type: string; description?: string | null } | null): string {
    if (!assessment) return "";
    const layerLabels: Record<string, string> = {
        deterministic: "Rule violations", statistical: "Statistical anomalies", behavioral: "Behavioral flags",
        document: "Document issues", network: "Network signals", narrative: "AI narrative",
    };

    const parts: string[] = [];

    // Risk headline
    const risk = assessment.risk_level?.replace(/_/g, " ") ?? null;
    const score = assessment.fraud_score ? `${(assessment.fraud_score * 100).toFixed(0)}%` : null;
    if (risk || score) {
        parts.push(`Fraud risk assessed as ${[risk, score ? `(score: ${score})` : null].filter(Boolean).join(" ")}.`);
    }

    // Collect all concrete flags from every channel
    const allFlags: { source: string; flags: string[] }[] = [
        { source: "Deterministic rules", flags: assessment.deterministic_signals ?? [] },
        { source: "Statistical signals",  flags: assessment.statistical_signals ?? [] },
        { source: "Behavioural",          flags: assessment.behavioral_flags ?? [] },
        { source: "Documents",            flags: assessment.document_flags ?? [] },
        { source: "Network",              flags: assessment.network_flags ?? [] },
    ];
    for (const { source, flags } of allFlags) {
        if (flags.length) {
            parts.push(`${source}: ${flags.slice(0, 4).map(f => f.replace(/_/g, " ").toLowerCase()).join("; ")}${flags.length > 4 ? " (+more)" : ""}.`);
        }
    }

    // High-scoring layer callout
    if (assessment.layer_scores) {
        const highLayers = Object.entries(assessment.layer_scores)
            .filter(([, l]) => l.score >= 0.6)
            .sort(([, a], [, b]) => b.score - a.score)
            .map(([k, l]) => `${layerLabels[k] ?? k} (${(l.score * 100).toFixed(0)}%)`);
        if (highLayers.length) {
            parts.push(`High-scoring layers: ${highLayers.join(", ")}.`);
        }
    }

    // Missing description nudge
    if (!claim?.description) {
        parts.push("No claim description was provided.");
    }

    return parts.join("\n");
}

export default function ClaimDetailPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = use(params);
    const router = useRouter();
    const isAdmin = useIsAdmin();
    const isAdjuster = useIsAdjuster();
    const canAction = isAdmin || isAdjuster;
    const [claim, setClaim] = useState<Claim | null>(null);
    const [assessment, setAssessment] = useState<FraudAssessment | null>(null);
    const [documents, setDocuments] = useState<ClaimDocumentResponse[]>([]);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [uploadFile, setUploadFile] = useState<File | null>(null);
    const [uploadType, setUploadType] = useState("INVOICE");
    const [uploading, setUploading] = useState(false);
    const [expandedDocIds, setExpandedDocIds] = useState<Set<string>>(new Set());
    const toggleDoc = (docId: string) => setExpandedDocIds((prev) => { const next = new Set(prev); next.has(docId) ? next.delete(docId) : next.add(docId); return next; });
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
    // Drag-resizable panels
    const [rightPanelWidth, setRightPanelWidth] = useState(460);
    const [reportPanelHeight, setReportPanelHeight] = useState(440);
    const horizDragging = useRef(false);
    const vertDragging = useRef(false);
    const horizStart = useRef({ x: 0, w: 460 });
    const vertStart = useRef({ y: 0, h: 440 });
    useEffect(() => {
        const onMove = (e: MouseEvent) => {
            if (horizDragging.current) {
                const delta = horizStart.current.x - e.clientX;
                setRightPanelWidth(Math.max(320, Math.min(800, horizStart.current.w + delta)));
            }
            if (vertDragging.current) {
                const delta = e.clientY - vertStart.current.y;
                setReportPanelHeight(Math.max(180, Math.min(740, vertStart.current.h + delta)));
            }
        };
        const onUp = () => { horizDragging.current = false; vertDragging.current = false; document.body.style.cursor = ""; document.body.style.userSelect = ""; };
        window.addEventListener("mousemove", onMove);
        window.addEventListener("mouseup", onUp);
        return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); };
    }, []);
    // Flag modal
    const [showFlagModal, setShowFlagModal] = useState(false);
    const [flagReason, setFlagReason] = useState("");
    // Reject modal
    const [showRejectModal, setShowRejectModal] = useState(false);
    const [rejectReason, setRejectReason] = useState("");
    // Timeline
    const [timelineEntries, setTimelineEntries] = useState<AuditLogEntry[]>([]);
    const [timelineLoading, setTimelineLoading] = useState(false);

    // ── Polling for background Gemini extraction ───────────────────────────
    const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const stopPolling = useCallback(() => {
        if (pollTimerRef.current) {
            clearInterval(pollTimerRef.current);
            pollTimerRef.current = null;
        }
    }, []);

    const startPollingIfNeeded = useCallback((docs: ClaimDocumentResponse[]) => {
        const hasPending = docs.some((d) => (d.ocr_status ?? d.validation_status ?? "").toUpperCase() === "PENDING");
        if (!hasPending) { stopPolling(); return; }
        if (pollTimerRef.current) return; // already running
        pollTimerRef.current = setInterval(async () => {
            try {
                const refreshed = await documentService.listClaimDocs(id);
                setDocuments(refreshed);
                if (!refreshed.some((d) => (d.ocr_status ?? d.validation_status ?? "").toUpperCase() === "PENDING")) stopPolling();
            } catch { /* ignore transient poll errors */ }
        }, 3000);
    }, [id, stopPolling]);

    const load = async () => {
        setLoading(true);
        try {
            const [c, docs] = await Promise.all([
                claimService.get(id),
                documentService.listClaimDocs(id),
            ]);
            setClaim(c);
            setDocuments(docs);
            startPollingIfNeeded(docs);
            // Fetch existing fraud assessment only for admins/adjusters
            if (canAction) {
                const a = await fraudService.getAssessment(id);
                if (a) setAssessment(a);
            }
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

    // Force-regenerate the report (bypass cache)
    const regenerateReport = useCallback(async () => {
        if (!id || reportLoading) return;
        setReportLoading(true);
        try {
            const res = await adjusterService.regenerateReport(id);
            setClaimReport(res.report || null);
        } catch {
            setClaimReport(null);
        } finally {
            setReportLoading(false);
        }
    }, [id, reportLoading]);

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
    // Stop polling when component unmounts (navigation away from the page)
    useEffect(() => () => { stopPolling(); }, [stopPolling]);

    // Load timeline from audit trail
    useEffect(() => {
        if (!id) return;
        setTimelineLoading(true);
        complianceService.auditTrail(id, 100)
            .then(setTimelineEntries)
            .catch(() => setTimelineEntries([]))
            .finally(() => setTimelineLoading(false));
    }, [id, claim?.status]); // re-fetch when status changes

    /* runFraud removed — FraudAgentPanel handles analysis internally */

    const changeStatus = async (status: string, adjuster_notes?: string) => {
        setActionLoading(true);
        try {
            const updated = await claimService.updateStatus(id, { status, adjuster_notes });
            setClaim(updated);
            // Refresh timeline
            complianceService.auditTrail(id, 100).then(setTimelineEntries).catch(() => {});
        } catch (e: unknown) {
            const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
            setError(msg || "Status update failed");
        } finally {
            setActionLoading(false);
        }
    };

    const submitFlag = async () => {
        await changeStatus("MANUAL_REVIEW_REQUIRED", flagReason.trim() || undefined);
        setShowFlagModal(false);
        setFlagReason("");
    };

    const submitReject = async () => {
        await changeStatus("REJECTED", rejectReason.trim() || undefined);
        setShowRejectModal(false);
        setRejectReason("");
    };

    const handleUpload = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!uploadFile) return;
        setUploading(true);
        try {
            const doc = await documentService.uploadClaimDoc(id, uploadFile, uploadType);
            setDocuments((prev) => {
                const next = [doc, ...prev];
                startPollingIfNeeded(next);
                return next;
            });
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
                                {canTransitionTo(claim.status, "APPROVED") && (
                                    <button className="btn btn-ghost" onClick={() => changeStatus("APPROVED")} disabled={actionLoading} style={{ color: "var(--green)", borderColor: "var(--green-border)" }}>
                                        <CheckCircle size={13} /> Approve
                                    </button>
                                )}
                                {canTransitionTo(claim.status, "MANUAL_REVIEW_REQUIRED") && (
                                    <button className="btn btn-warning" onClick={() => {
                                            setFlagReason(composeFlagReason(assessment, claim));
                                            setShowFlagModal(true);
                                        }} disabled={actionLoading}>
                                            <Flag size={13} /> Flag
                                    </button>
                                )}
                                {canTransitionTo(claim.status, "REJECTED") && (
                                    <button className="btn btn-danger" onClick={() => {
                                        setRejectReason("");
                                        setShowRejectModal(true);
                                    }} disabled={actionLoading}>
                                        <XCircle size={13} /> Reject
                                    </button>
                                )}
                                {canTransitionTo(claim.status, "SETTLED") && (
                                    <button className="btn btn-ghost" onClick={() => changeStatus("SETTLED")} disabled={actionLoading} style={{ color: "var(--blue)", borderColor: "var(--blue-border, var(--border))" }}>
                                        <CircleCheck size={13} /> Settle
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
                    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
                        {/* Left: Claim Details + Documents */}
                        <div style={{ flex: 1, minWidth: 0, padding: 20, overflowY: "auto", borderRight: "1px solid var(--border)" }}>

                            {/* Adjuster notes banner — visible to all roles */}
                            {claim.adjuster_notes && (claim.status === "MANUAL_REVIEW_REQUIRED" || claim.status === "REJECTED") && (
                                <div style={{
                                    background: claim.status === "REJECTED" ? "var(--crimson-bg, rgba(220,38,38,0.08))" : "var(--amber-bg)",
                                    border: `1px solid ${claim.status === "REJECTED" ? "var(--crimson-border, rgba(220,38,38,0.25))" : "var(--amber-border)"}`,
                                    borderRadius: 8, padding: "14px 16px", marginBottom: 16,
                                    display: "flex", gap: 12, alignItems: "flex-start",
                                }}>
                                    {claim.status === "REJECTED"
                                        ? <XCircle size={15} color="var(--crimson)" style={{ flexShrink: 0, marginTop: 2 }} />
                                        : <Flag size={15} color="var(--amber)" style={{ flexShrink: 0, marginTop: 2 }} />}
                                    <div style={{ flex: 1 }}>
                                        <div style={{ fontSize: "0.75rem", fontWeight: 700, color: claim.status === "REJECTED" ? "var(--crimson)" : "var(--amber)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                                            {claim.status === "REJECTED" ? "Claim Rejected" : "Flagged for Review"}
                                        </div>
                                        <p style={{ fontSize: "0.875rem", color: "var(--text-primary)", lineHeight: 1.65, margin: 0 }}>
                                            {claim.adjuster_notes}
                                        </p>
                                        {!canAction && claim.status === "MANUAL_REVIEW_REQUIRED" && (
                                            <p style={{ fontSize: "0.8125rem", color: "var(--text-muted)", marginTop: 8, marginBottom: 0 }}>
                                                Please upload any missing or additional documents below to continue processing your claim.
                                            </p>
                                        )}
                                    </div>
                                </div>
                            )}
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
                                            onClick={() => toggleDoc(doc.id.toString())}
                                            style={{
                                                width: "100%",
                                                display: "flex",
                                                alignItems: "center",
                                                gap: 10,
                                                padding: "8px 0",
                                                background: "transparent",
                                                border: "none",
                                                borderBottom: "1px solid var(--border)",
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
                                            {(doc.ocr_status ?? "").toUpperCase() === "PENDING" ? (
                                                <Loader2 size={12} color="var(--blue)" style={{ animation: "spin 1s linear infinite", flexShrink: 0 }} />
                                            ) : doc.extracted_data && Object.keys(doc.extracted_data).length > 0 ? (
                                                <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.625rem", color: "var(--green)" }}>
                                                    {doc.extraction_confidence ? `${(doc.extraction_confidence * 100).toFixed(0)}%` : "✓"}
                                                </span>
                                            ) : null}
                                            {expandedDocIds.has(doc.id.toString())
                                                ? <ChevronUp size={13} color="var(--text-muted)" style={{ flexShrink: 0 }} />
                                                : <ChevronDown size={13} color="var(--text-muted)" style={{ flexShrink: 0 }} />
                                            }
                                        </button>
                                        {expandedDocIds.has(doc.id.toString()) && (
                                            <div style={{ padding: "12px 0", borderBottom: "1px solid var(--border)" }}>
                                                {(doc.ocr_status ?? "").toUpperCase() === "PENDING" ? (
                                                    <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--blue)", fontSize: "0.75rem" }}>
                                                        <Loader2 size={13} style={{ animation: "spin 1s linear infinite" }} />
                                                        AI extraction in progress — this usually takes 20–40 s…
                                                    </div>
                                                ) : (doc.validation_status ?? "").toUpperCase() === "EXTRACTION_FAILED" || doc.ocr_status.toUpperCase() === "FAILED" ? (
                                                    <div>
                                                        <div style={{ fontSize: "0.75rem", color: "var(--crimson)", marginBottom: 8 }}>
                                                            Automated extraction failed — add data manually below.
                                                        </div>
                                                        <EditableExtractedData
                                                            document={doc}
                                                            onUpdate={(updated) => {
                                                                setDocuments((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
                                                            }}
                                                            onError={(error) => setDocError(error)}
                                                        />
                                                    </div>
                                                ) : doc.extracted_data && Object.keys(doc.extracted_data).length > 0 ? (
                                                    <EditableExtractedData
                                                        document={doc}
                                                        onUpdate={(updated) => {
                                                            setDocuments((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
                                                        }}
                                                        onError={(error) => setDocError(error)}
                                                    />
                                                ) : (
                                                    <div>
                                                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: 8 }}>
                                                            No data extracted — add fields manually.
                                                        </div>
                                                        <EditableExtractedData
                                                            document={doc}
                                                            onUpdate={(updated) => {
                                                                setDocuments((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
                                                            }}
                                                            onError={(error) => setDocError(error)}
                                                        />
                                                    </div>
                                                )}
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
                            {/* Claim Timeline */}
                            <ClaimTimeline entries={timelineEntries} loading={timelineLoading} documents={documents} claimCreatedAt={claim.created_at} />

                        </div>

                        {/* Horizontal drag handle */}
                        {canAction && (
                            <div
                                onMouseDown={(e) => { horizDragging.current = true; horizStart.current = { x: e.clientX, w: rightPanelWidth }; document.body.style.cursor = "col-resize"; document.body.style.userSelect = "none"; }}
                                style={{ width: 5, flexShrink: 0, cursor: "col-resize", background: "transparent", transition: "background 150ms" }}
                                onMouseEnter={(e) => ((e.currentTarget as HTMLDivElement).style.background = "var(--blue)")}
                                onMouseLeave={(e) => { if (!horizDragging.current) (e.currentTarget as HTMLDivElement).style.background = "transparent"; }}
                            />
                        )}
                        {/* Right: Tabbed panel — Fraud | AI Assistant (admins/adjusters only) */}
                        {canAction && (<div style={{ width: rightPanelWidth, flexShrink: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
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
                            <FraudAgentPanel
                                claimId={id}
                                assessment={assessment}
                                documents={documents}
                                loading={false}
                                onAssessmentChange={(a) => { setAssessment(a); }}
                                onFraudScoreChange={(s) => { setClaim((prev) => prev ? { ...prev, fraud_score: s } : prev); }}
                            />
                        </div>{/* end fraud tab */}

                            {/* Claim Report tab — auto-generated report + follow-up chat */}
                            {canAction && (
                                <div style={{ flex: 1, display: rightTab === "agent" ? "flex" : "none", flexDirection: "column", overflow: "hidden" }}>
                                    {/* Report section */}
                                    <div style={{ height: claimReport ? reportPanelHeight : undefined, flexGrow: claimReport ? 0 : 1, flexShrink: 0, flexBasis: claimReport ? 'auto' : 0, overflowY: "auto", padding: "16px 18px", borderBottom: (claimReport || reportLoading) ? "1px solid var(--border)" : "none" }}>
                                        {/* Header with regenerate button */}
                                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                                            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                                <Sparkles size={16} color="var(--blue)" />
                                                <span style={{ fontSize: "0.8125rem", color: "var(--text-primary)", fontWeight: 700 }}>
                                                    AI Claim Report
                                                </span>
                                            </div>
                                            {(claimReport || reportLoaded) && (
                                                <button
                                                    className="btn btn-ghost"
                                                    onClick={regenerateReport}
                                                    disabled={reportLoading}
                                                    style={{ padding: "5px 10px", fontSize: "0.75rem", display: "flex", alignItems: "center", gap: 5 }}
                                                >
                                                    <RefreshCw size={13} style={reportLoading ? { animation: "spin 1s linear infinite" } : undefined} />
                                                    {reportLoading ? "Generating…" : "Regenerate"}
                                                </button>
                                            )}
                                        </div>
                                        {reportLoading && (
                                            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                                                <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--text-muted)", fontSize: "0.8125rem" }}>
                                                    <Loader2 size={13} style={{ animation: "spin 1s linear infinite" }} />
                                                    Generating claim report…
                                                </div>
                                                {[...Array(8)].map((_, i) => <div key={i} className="skeleton" style={{ height: 11, marginBottom: 6 }} />)}
                                            </div>
                                        )}
                                        {!reportLoading && claimReport && (
                                            <ClaimReportRenderer report={claimReport} />
                                        )}
                                        {!reportLoading && !claimReport && reportLoaded && (
                                            <div style={{ textAlign: "center", padding: "20px 0", color: "var(--text-muted)", fontSize: "0.8125rem" }}>
                                                Report generation failed. Ask a question below.
                                            </div>
                                        )}
                                    </div>
                                    {/* Vertical drag handle between report and chat */}
                                    {claimReport && (
                                        <div
                                            onMouseDown={(e) => { vertDragging.current = true; vertStart.current = { y: e.clientY, h: reportPanelHeight }; document.body.style.cursor = "row-resize"; document.body.style.userSelect = "none"; }}
                                            style={{ height: 5, flexShrink: 0, cursor: "row-resize", background: "transparent", transition: "background 150ms" }}
                                            onMouseEnter={(e) => ((e.currentTarget as HTMLDivElement).style.background = "var(--blue)")}
                                            onMouseLeave={(e) => { if (!vertDragging.current) (e.currentTarget as HTMLDivElement).style.background = "transparent"; }}
                                        />
                                    )}
                                    {/* Follow-up chat — only shown once report is loaded */}
                                    {(claimReport || reportLoaded) && (
                                        <div style={{ flex: 1, overflowY: "auto", padding: "10px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
                                            {agentMessages.length === 0 && claimReport && (
                                                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textAlign: "center", padding: "8px 0" }}>
                                                    Ask a follow-up question about this report
                                                </div>
                                            )}
                                            {agentMessages.map((m, i) => {
                                                // Format content: ensure → markers are on new lines
                                                const formatContent = (text: string) => {
                                                    return text
                                                        .split('\n')
                                                        .map((line) => {
                                                            const trimmed = line.trim();
                                                            if (trimmed.startsWith('→')) {
                                                                return trimmed;
                                                            }
                                                            return line;
                                                        })
                                                        .join('\n');
                                                };
                                                const formattedContent = formatContent(m.content);
                                                
                                                return (
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
                                                    {formattedContent}
                                                </div>
                                                );
                                            })}
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
                        </div>)}{/* end right tabbed panel */}
                    </div>
                )}
            </CommandLayout>

            {/* Reject Modal */}
            {showRejectModal && (
                <div style={{
                    position: "fixed", inset: 0, zIndex: 50,
                    background: "rgba(0,0,0,0.55)", display: "flex",
                    alignItems: "center", justifyContent: "center", padding: 24,
                }} onClick={(e) => { if (e.target === e.currentTarget) setShowRejectModal(false); }}>
                    <div style={{
                        background: "var(--bg-panel)", border: "1px solid var(--border)",
                        borderRadius: 10, width: "100%", maxWidth: 520,
                        display: "flex", flexDirection: "column", overflow: "hidden",
                        boxShadow: "0 24px 60px rgba(0,0,0,0.4)",
                    }}>
                        <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 10 }}>
                            <XCircle size={15} color="var(--crimson)" />
                            <span style={{ fontWeight: 700, fontSize: "0.9375rem", flex: 1 }}>Reject Claim</span>
                            <button onClick={() => setShowRejectModal(false)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-muted)", display: "flex" }}>
                                <X size={16} />
                            </button>
                        </div>
                        <div style={{ padding: "20px" }}>
                            <p style={{ fontSize: "0.8125rem", color: "var(--text-muted)", marginBottom: 14, marginTop: 0, lineHeight: 1.6 }}>
                                Optionally provide a reason for rejection. The policyholder will see this message.
                            </p>
                            {assessment?.explanation_text && (
                                <button
                                    onClick={() => setRejectReason(assessment.explanation_text || "")}
                                    style={{
                                        width: "100%", textAlign: "left", background: "var(--bg-surface)",
                                        border: "1px solid var(--border)", borderRadius: 6,
                                        padding: "10px 14px", marginBottom: 12, cursor: "pointer",
                                        display: "flex", gap: 10, alignItems: "flex-start",
                                    }}
                                >
                                    <Sparkles size={14} color="var(--blue)" style={{ flexShrink: 0, marginTop: 2 }} />
                                    <div>
                                        <div style={{ fontSize: "0.6875rem", color: "var(--blue)", fontWeight: 600, marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.05em" }}>Use AI reasoning</div>
                                        <div style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>{assessment.explanation_text.slice(0, 180)}{assessment.explanation_text.length > 180 ? "\u2026" : ""}</div>
                                    </div>
                                </button>
                            )}
                            <textarea
                                className="input"
                                rows={4}
                                style={{ width: "100%", resize: "vertical", fontSize: "0.9rem", lineHeight: 1.65, padding: "10px 12px", boxSizing: "border-box" }}
                                placeholder="Reason for rejection (optional)\u2026"
                                value={rejectReason}
                                onChange={(e) => setRejectReason(e.target.value)}
                                autoFocus
                            />
                        </div>
                        <div style={{ padding: "12px 20px", borderTop: "1px solid var(--border)", display: "flex", justifyContent: "flex-end", gap: 8 }}>
                            <button className="btn btn-ghost" onClick={() => setShowRejectModal(false)}>Cancel</button>
                            <button
                                className="btn btn-danger"
                                onClick={submitReject}
                                disabled={actionLoading}
                                style={{ display: "flex", alignItems: "center", gap: 6 }}
                            >
                                {actionLoading ? <Loader2 size={13} style={{ animation: "spin 1s linear infinite" }} /> : <XCircle size={13} />}
                                Confirm Reject
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Flag Modal */}
            {showFlagModal && (
                <div style={{
                    position: "fixed", inset: 0, zIndex: 50,
                    background: "rgba(0,0,0,0.55)", display: "flex",
                    alignItems: "center", justifyContent: "center", padding: 24,
                }} onClick={(e) => { if (e.target === e.currentTarget) setShowFlagModal(false); }}>
                    <div style={{
                        background: "var(--bg-panel)", border: "1px solid var(--border)",
                        borderRadius: 10, width: "100%", maxWidth: 520,
                        display: "flex", flexDirection: "column", overflow: "hidden",
                        boxShadow: "0 24px 60px rgba(0,0,0,0.4)",
                    }}>
                        {/* Header */}
                        <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 10 }}>
                            <Flag size={15} color="var(--amber)" />
                            <span style={{ fontWeight: 700, fontSize: "0.9375rem", flex: 1 }}>Flag Claim for Review</span>
                            <button onClick={() => setShowFlagModal(false)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-muted)", display: "flex" }}>
                                <X size={16} />
                            </button>
                        </div>

                        {/* Body */}
                        <div style={{ padding: "20px" }}>
                            <p style={{ fontSize: "0.8125rem", color: "var(--text-muted)", marginBottom: 14, marginTop: 0, lineHeight: 1.6 }}>
                                Provide a reason for flagging this claim. The policyholder will see this message and can upload additional documents.
                            </p>

                            {/* AI suggestion */}
                            {assessment?.explanation_text && flagReason !== assessment.explanation_text && (
                                <button
                                    onClick={() => setFlagReason(assessment.explanation_text || "")}
                                    style={{
                                        width: "100%", textAlign: "left", background: "var(--bg-surface)",
                                        border: "1px solid var(--border)", borderRadius: 6,
                                        padding: "10px 14px", marginBottom: 12, cursor: "pointer",
                                        display: "flex", gap: 10, alignItems: "flex-start",
                                    }}
                                >
                                    <Sparkles size={14} color="var(--blue)" style={{ flexShrink: 0, marginTop: 2 }} />
                                    <div>
                                        <div style={{ fontSize: "0.6875rem", color: "var(--blue)", fontWeight: 600, marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.05em" }}>Use AI reasoning</div>
                                        <div style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>{assessment.explanation_text.slice(0, 180)}{assessment.explanation_text.length > 180 ? "…" : ""}</div>
                                    </div>
                                </button>
                            )}

                            <textarea
                                className="input"
                                rows={5}
                                style={{ width: "100%", resize: "vertical", fontSize: "0.9rem", lineHeight: 1.65, padding: "10px 12px", boxSizing: "border-box" }}
                                placeholder="Describe what is missing or needs clarification…"
                                value={flagReason}
                                onChange={(e) => setFlagReason(e.target.value)}
                                autoFocus
                            />
                        </div>

                        {/* Footer */}
                        <div style={{ padding: "12px 20px", borderTop: "1px solid var(--border)", display: "flex", justifyContent: "flex-end", gap: 8 }}>
                            <button className="btn btn-ghost" onClick={() => setShowFlagModal(false)}>Cancel</button>
                            <button
                                className="btn btn-warning"
                                onClick={submitFlag}
                                disabled={actionLoading}
                                style={{ display: "flex", alignItems: "center", gap: 6 }}
                            >
                                {actionLoading ? <Loader2 size={13} style={{ animation: "spin 1s linear infinite" }} /> : <Flag size={13} />}
                                Flag Claim
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </AuthGuard>
    );
}

// ── Timeline Component ──────────────────────────────────────────────────────
const ACTION_ICON: Record<string, React.ReactNode> = {
    CLAIM_SUBMITTED: <CircleDot size={14} color="var(--blue)" />,
    CLAIM_STATUS_CHANGED: <CircleCheck size={14} color="var(--green)" />,
    FRAUD_ANALYZED: <ShieldAlert size={14} color="var(--amber)" />,
    DOCUMENT_UPLOADED: <FileUp size={14} color="var(--text-muted)" />,
    USER_LOGIN: <CircleDot size={14} color="var(--text-muted)" />,
};

const STATUS_LABEL: Record<string, string> = {
    SUBMITTED: "Claim Submitted",
    OCR_PROCESSED: "Documents Processed",
    UNDER_REVIEW: "Under Review",
    FRAUD_ANALYZED: "Fraud Analysis Complete",
    APPROVED: "Claim Approved",
    REJECTED: "Claim Rejected",
    MANUAL_REVIEW_REQUIRED: "Flagged for Manual Review",
    SETTLED: "Claim Settled",
};

function formatTimelineDate(ts: string | null | undefined) {
    if (!ts) return "";
    const d = new Date(ts);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });
}

function ClaimTimeline({ entries, loading, documents, claimCreatedAt }: {
    entries: AuditLogEntry[]; loading: boolean;
    documents: ClaimDocumentResponse[]; claimCreatedAt: string;
}) {
    // Build timeline events from audit entries
    const events = entries
        .filter((e) => e.action_type !== "USER_LOGIN")
        .map((e) => {
            let title = e.action_type.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
            let detail = "";
            let color = "var(--text-muted)";
            let icon = ACTION_ICON[e.action_type] || <CircleDot size={14} color="var(--text-muted)" />;

            if (e.action_type === "CLAIM_STATUS_CHANGED" && e.metadata) {
                const to = e.metadata.to as string;
                const from = e.metadata.from as string;
                title = STATUS_LABEL[to] || to.replace(/_/g, " ");
                detail = from ? `Status changed from ${from.replace(/_/g, " ")}` : "";
                if (e.metadata.notes) detail = e.metadata.notes as string;
                color = to === "APPROVED" || to === "SETTLED" ? "var(--green)"
                    : to === "REJECTED" ? "var(--crimson)"
                    : to === "MANUAL_REVIEW_REQUIRED" ? "var(--amber)"
                    : "var(--blue)";
                icon = to === "APPROVED" || to === "SETTLED"
                    ? <CircleCheck size={14} color="var(--green)" />
                    : to === "REJECTED" ? <CircleX size={14} color="var(--crimson)" />
                    : to === "MANUAL_REVIEW_REQUIRED" ? <Flag size={14} color="var(--amber)" />
                    : <CircleDot size={14} color="var(--blue)" />;
            } else if (e.action_type === "DOCUMENT_UPLOADED") {
                const docType = e.metadata?.document_type as string | undefined;
                detail = docType ? docType.replace(/_/g, " ") : "";
            } else if (e.action_type === "FRAUD_ANALYZED") {
                const score = e.metadata?.fraud_score as number | undefined;
                detail = score !== undefined ? `Score: ${(score * 100).toFixed(0)}%` : "";
                color = "var(--amber)";
            }

            return { id: e.id, title, detail, color, icon, timestamp: e.timestamp };
        })
        .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

    return (
        <div className="panel" style={{ padding: 18, marginTop: 16 }}>
            <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 16, display: "flex", alignItems: "center", gap: 6 }}>
                <Clock size={12} />
                Claim Timeline
            </div>

            {loading && (
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    {[...Array(4)].map((_, i) => (
                        <div key={i} style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
                            <div className="skeleton" style={{ width: 14, height: 14, borderRadius: "50%", flexShrink: 0 }} />
                            <div style={{ flex: 1 }}><div className="skeleton" style={{ height: 12, width: "60%", marginBottom: 6 }} /><div className="skeleton" style={{ height: 10, width: "40%" }} /></div>
                        </div>
                    ))}
                </div>
            )}

            {!loading && events.length === 0 && (
                <div style={{ color: "var(--text-muted)", fontSize: "0.8125rem", textAlign: "center", padding: "12px 0" }}>No events yet</div>
            )}

            {!loading && events.length > 0 && (
                <div style={{ position: "relative" }}>
                    {/* Vertical line */}
                    <div style={{ position: "absolute", left: 7, top: 16, bottom: 4, width: 1, background: "var(--border)" }} />

                    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
                        {events.map((evt, idx) => (
                            <div key={evt.id} style={{ display: "flex", gap: 14, paddingBottom: idx < events.length - 1 ? 18 : 0, position: "relative" }}>
                                {/* Dot */}
                                <div style={{ flexShrink: 0, width: 15, display: "flex", justifyContent: "center", paddingTop: 1, zIndex: 1, background: "var(--bg-panel)" }}>
                                    {evt.icon}
                                </div>
                                {/* Content */}
                                <div style={{ flex: 1, minWidth: 0 }}>
                                    <div style={{ fontSize: "0.875rem", fontWeight: 600, color: evt.color, lineHeight: 1.4 }}>{evt.title}</div>
                                    {evt.detail && (
                                        <div style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", marginTop: 3, lineHeight: 1.55 }}>{evt.detail}</div>
                                    )}
                                    <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", marginTop: 4, fontFamily: "var(--font-mono)" }}>
                                        {formatTimelineDate(evt.timestamp)}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
