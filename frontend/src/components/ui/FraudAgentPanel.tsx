"use client";
import { useState } from "react";
import {
    Zap, ChevronDown, ChevronUp, ShieldAlert, AlertTriangle, CheckCircle,
    XCircle, FileText, Activity, Brain, Eye, BarChart3, Loader2, Search,
} from "lucide-react";
import { FraudScoreBadge } from "@/components/ui";
import type { FraudAssessment, ClaimDocumentResponse } from "@/types";
import { fraudService } from "@/services/fraudService";

// ── Node metadata ───────────────────────────────────────────────────────────

const NODE_META: Record<string, { label: string; icon: React.ReactNode; description: string }> = {
    extraction_integrity: {
        label: "Extraction Integrity",
        icon: <FileText size={14} />,
        description: "PyMuPDF + Gemini dual extraction with reconciliation checks",
    },
    cross_document_consistency: {
        label: "Cross-Document Consistency",
        icon: <Search size={14} />,
        description: "Timeline, name matching, policy window & financial validation",
    },
    document_intelligence: {
        label: "Document Intelligence",
        icon: <Eye size={14} />,
        description: "Redaction detection, hallucination checks, PAN/Aadhaar validation",
    },
    image_forensics: {
        label: "Image Forensics",
        icon: <Activity size={14} />,
        description: "Metadata analysis, ELA, perceptual hashing, copy-move detection",
    },
    document_content_fraud: {
        label: "Content Analysis (AI)",
        icon: <Brain size={14} />,
        description: "Gemini-powered arithmetic/GST validation + medical plausibility",
    },
    behavioral_risk: {
        label: "Behavioral Risk",
        icon: <BarChart3 size={14} />,
        description: "Claim timing, frequency, amount ratios & policyholder history",
    },
};

const NODE_ORDER = [
    "extraction_integrity",
    "cross_document_consistency",
    "document_intelligence",
    "image_forensics",
    "document_content_fraud",
    "behavioral_risk",
];

// ── Helpers ──────────────────────────────────────────────────────────────────

function riskColor(score: number): string {
    if (score >= 70) return "var(--crimson)";
    if (score >= 40) return "var(--amber)";
    return "var(--green)";
}

function riskLabel(level: string | null): { text: string; cls: string } {
    switch (level) {
        case "CRITICAL":
        case "VERY_HIGH": return { text: `${level} RISK`, cls: "pill-rejected" };
        case "HIGH": return { text: "HIGH RISK", cls: "pill-rejected" };
        case "MEDIUM": return { text: "MEDIUM RISK", cls: "pill-review" };
        case "LOW": return { text: "LOW RISK", cls: "pill-approved" };
        case "MINIMAL": return { text: "MINIMAL RISK", cls: "pill-approved" };
        default: return { text: "UNKNOWN", cls: "" };
    }
}

function formatNodeScore(score: number): string {
    return `${Math.round(score)}`;
}

function formatDateTime(dt: string | null | undefined) {
    if (!dt) return "—";
    const d = new Date(dt);
    if (isNaN(d.getTime())) return "—";
    return d.toLocaleDateString("en-IN", {
        day: "2-digit", month: "short", year: "numeric",
        hour: "2-digit", minute: "2-digit",
    });
}

// ── Node Score Row (expandable) ─────────────────────────────────────────────

function NodeScoreRow({
    nodeName,
    score,
    weight,
    flags,
    details,
}: {
    nodeName: string;
    score: number;
    weight: number;
    flags: string[];
    details: Record<string, unknown> | null;
}) {
    const [expanded, setExpanded] = useState(false);
    const meta = NODE_META[nodeName] || { label: nodeName, icon: <FileText size={14} />, description: "" };
    const normalizedScore = score; // scores are 0-100 from nodes
    const color = riskColor(normalizedScore);
    const hasContent = flags.length > 0 || (details && Object.keys(details).length > 0);

    return (
        <div style={{ borderBottom: "1px solid var(--border)" }}>
            <button
                type="button"
                onClick={() => hasContent && setExpanded(!expanded)}
                style={{
                    width: "100%", display: "flex", alignItems: "center", gap: 10,
                    padding: "10px 0", background: "transparent", border: "none",
                    cursor: hasContent ? "pointer" : "default", color: "inherit", textAlign: "left",
                }}
            >
                <span style={{ color: "var(--text-muted)", display: "flex", flexShrink: 0 }}>
                    {meta.icon}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: "0.8125rem", fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}>
                        {meta.label}
                        <span style={{
                            fontSize: "0.625rem", color: "var(--text-muted)",
                            fontWeight: 400, opacity: 0.7,
                        }}>
                            ×{weight.toFixed(2)}
                        </span>
                    </div>
                    {/* Score bar */}
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
                        <div style={{
                            flex: 1, height: 4, borderRadius: 2,
                            background: "var(--bg-surface)", overflow: "hidden",
                        }}>
                            <div style={{
                                width: `${Math.min(normalizedScore, 100)}%`, height: "100%",
                                borderRadius: 2, background: color,
                                transition: "width 600ms ease-out",
                            }} />
                        </div>
                        <span style={{
                            fontFamily: "var(--font-mono)", fontSize: "0.75rem",
                            color, fontWeight: 700, minWidth: 32, textAlign: "right",
                        }}>
                            {formatNodeScore(normalizedScore)}
                        </span>
                    </div>
                </div>
                {flags.length > 0 && (
                    <span style={{
                        fontFamily: "var(--font-mono)", fontSize: "0.625rem",
                        color: "var(--amber)", fontWeight: 600, flexShrink: 0,
                    }}>
                        {flags.length} flag{flags.length !== 1 ? "s" : ""}
                    </span>
                )}
                {hasContent && (
                    <span style={{ color: "var(--text-muted)", display: "flex", flexShrink: 0 }}>
                        {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    </span>
                )}
            </button>

            {/* Expanded details */}
            {expanded && (
                <div style={{ padding: "0 0 12px 24px" }}>
                    {/* Description */}
                    <p style={{
                        fontSize: "0.6875rem", color: "var(--text-muted)",
                        margin: "0 0 8px 0", lineHeight: 1.5, fontStyle: "italic",
                    }}>
                        {meta.description}
                    </p>

                    {/* Flags */}
                    {flags.length > 0 && (
                        <div style={{ marginBottom: 8 }}>
                            <div style={{
                                fontSize: "0.625rem", color: "var(--text-muted)",
                                textTransform: "uppercase", letterSpacing: "0.06em",
                                marginBottom: 4, fontWeight: 600,
                            }}>
                                Signals
                            </div>
                            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                                {flags.map((f, i) => (
                                    <span key={i} style={{
                                        fontFamily: "var(--font-mono)", fontSize: "0.6875rem",
                                        background: normalizedScore >= 70
                                            ? "rgba(220,38,38,0.08)"
                                            : normalizedScore >= 40
                                                ? "rgba(234,179,8,0.08)"
                                                : "var(--bg-surface)",
                                        border: `1px solid ${normalizedScore >= 70
                                            ? "rgba(220,38,38,0.2)"
                                            : normalizedScore >= 40
                                                ? "rgba(234,179,8,0.2)"
                                                : "var(--border)"}`,
                                        borderRadius: 3, padding: "2px 6px",
                                        color: "var(--text-secondary)",
                                    }}>
                                        {f}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Detailed checks */}
                    {details && typeof details === "object" && Object.keys(details).length > 0 && (
                        <div>
                            <div style={{
                                fontSize: "0.625rem", color: "var(--text-muted)",
                                textTransform: "uppercase", letterSpacing: "0.06em",
                                marginBottom: 4, fontWeight: 600,
                            }}>
                                Checks
                            </div>
                            <div style={{
                                fontFamily: "var(--font-mono)", fontSize: "0.6875rem",
                                background: "var(--bg-surface)", border: "1px solid var(--border)",
                                borderRadius: 4, padding: "8px 10px",
                                maxHeight: 200, overflowY: "auto",
                                lineHeight: 1.6, color: "var(--text-secondary)",
                            }}>
                                {Object.entries(details)
                                    .filter(([k]) => !["score", "flags", "details"].includes(k))
                                    .map(([key, val]) => (
                                        <div key={key} style={{ display: "flex", gap: 8 }}>
                                            <span style={{ color: "var(--text-muted)", flexShrink: 0 }}>{key}:</span>
                                            <span style={{ wordBreak: "break-all" }}>
                                                {typeof val === "object" ? JSON.stringify(val, null, 0) : String(val)}
                                            </span>
                                        </div>
                                    ))}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// ── Main panel ──────────────────────────────────────────────────────────────

interface FraudAgentPanelProps {
    claimId: string;
    assessment: FraudAssessment | null;
    documents: ClaimDocumentResponse[];
    loading: boolean;
    onAssessmentChange: (a: FraudAssessment) => void;
    onFraudScoreChange?: (score: number) => void;
}

export function FraudAgentPanel({
    claimId,
    assessment,
    documents,
    loading: externalLoading,
    onAssessmentChange,
    onFraudScoreChange,
}: FraudAgentPanelProps) {
    const [analyzing, setAnalyzing] = useState(false);
    const [selectedDocId, setSelectedDocId] = useState<string>("");
    const [error, setError] = useState<string | null>(null);

    const completedDocs = documents.filter(
        (d) => d.ocr_status?.toUpperCase() === "COMPLETED" || (d.extracted_data && Object.keys(d.extracted_data).length > 0)
    );

    const runAgentAnalysis = async () => {
        setAnalyzing(true);
        setError(null);
        try {
            let result: FraudAssessment;
            if (selectedDocId) {
                result = await fraudService.agentAnalyze(claimId, selectedDocId);
            } else {
                // Use the main analyze endpoint (auto-picks first document)
                result = await fraudService.analyze(claimId);
            }
            onAssessmentChange(result);
            onFraudScoreChange?.(result.fraud_score);
        } catch (e: unknown) {
            const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
            setError(msg || "Fraud analysis failed. Ensure documents are uploaded.");
        } finally {
            setAnalyzing(false);
        }
    };

    const isLoading = externalLoading || analyzing;
    const manualReview = assessment?.feature_snapshot?.manual_review_required;
    const triggers: string[] = assessment?.feature_snapshot?.manual_review_triggers || [];
    const criticalSignals: string[] = assessment?.feature_snapshot?.critical_signals || [];
    const analyzedDocId = assessment?.feature_snapshot?.analyzed_document_id;
    const analyzedDoc = documents.find((d) => d.id === analyzedDocId);

    return (
        <div style={{ padding: "24px 28px" }}>
            {/* Hero header */}
            <div style={{
                background: "linear-gradient(135deg, rgba(124,58,237,0.06), rgba(26,86,219,0.06))",
                border: "1px solid rgba(124,58,237,0.12)",
                borderRadius: 14, padding: "20px 22px", marginBottom: 20,
            }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
                    <div style={{
                        width: 38, height: 38, borderRadius: 10,
                        background: "linear-gradient(135deg, #7c3aed, #1a56db)",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        flexShrink: 0,
                    }}>
                        <ShieldAlert size={18} color="#fff" />
                    </div>
                    <div>
                        <div style={{ fontSize: "1rem", fontWeight: 800, color: "#0f172a" }}>
                            Fraud Agent Intelligence
                        </div>
                        <div style={{ fontSize: "0.6875rem", color: "#64748b", marginTop: 2 }}>
                            6-layer AI-powered fraud detection engine
                        </div>
                    </div>
                </div>

                {/* Document selector + run button */}
                <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
                    <div style={{ flex: 1 }}>
                        <div style={{
                            fontSize: "0.625rem", color: "#64748b",
                            textTransform: "uppercase", letterSpacing: "0.05em",
                            marginBottom: 5, fontWeight: 600,
                        }}>
                            Target document
                        </div>
                        <select
                            className="input"
                            style={{
                                width: "100%", fontSize: "0.8125rem", height: 36,
                                borderRadius: 10, background: "#fff", border: "1px solid #e2e8f0",
                            }}
                            value={selectedDocId}
                            onChange={(e) => setSelectedDocId(e.target.value)}
                            disabled={isLoading}
                        >
                            <option value="">Auto (first completed)</option>
                            {completedDocs.map((d) => (
                                <option key={d.id} value={d.id}>
                                    {d.document_type.replace(/_/g, " ")}
                                    {d.original_filename ? ` — ${d.original_filename}` : ""}
                                </option>
                            ))}
                        </select>
                    </div>
                    <button
                        onClick={runAgentAnalysis}
                        disabled={isLoading || documents.length === 0}
                        style={{
                            padding: "0 20px", height: 36, display: "flex", alignItems: "center", gap: 6,
                            background: "linear-gradient(135deg, #7c3aed, #1a56db)",
                            color: "#fff", border: "none", borderRadius: 10,
                            fontSize: "0.8125rem", fontWeight: 700, cursor: "pointer",
                            opacity: (isLoading || documents.length === 0) ? 0.5 : 1,
                            transition: "all 0.15s",
                            boxShadow: "0 2px 8px rgba(124,58,237,0.25)",
                        }}
                    >
                        {analyzing ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : <Zap size={14} />}
                        {analyzing ? "Analyzing…" : assessment ? "Re-run" : "Analyze"}
                    </button>
                </div>
            </div>

            {/* Error */}
            {error && (
                <div style={{
                    background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.18)",
                    borderRadius: 10, padding: "12px 16px", marginBottom: 18,
                    fontSize: "0.8125rem", color: "#dc2626",
                    display: "flex", alignItems: "center", gap: 8,
                }}>
                    <XCircle size={14} />
                    {error}
                </div>
            )}

            {/* Empty state */}
            {!assessment && !isLoading && (
                <div style={{
                    textAlign: "center", padding: "48px 20px", color: "#94a3b8",
                    background: "#f8fafc", borderRadius: 14, border: "1px dashed #e2e8f0",
                }}>
                    <ShieldAlert size={32} color="#cbd5e1" style={{ marginBottom: 12 }} />
                    <div style={{ fontSize: "0.9375rem", fontWeight: 600, color: "#64748b", marginBottom: 4 }}>
                        {documents.length === 0 ? "Upload documents first" : "Ready to analyze"}
                    </div>
                    <div style={{ fontSize: "0.8125rem" }}>
                        {documents.length === 0
                            ? "Upload supporting documents, then run the fraud analysis engine"
                            : "Click Analyze above to run the 6-layer fraud detection pipeline"}
                    </div>
                </div>
            )}

            {/* Loading skeleton */}
            {isLoading && !assessment && (
                <div style={{ padding: "16px 0" }}>
                    <div className="skeleton" style={{ height: 100, borderRadius: 14, marginBottom: 16 }} />
                    {[...Array(6)].map((_, i) => (
                        <div key={i} className="skeleton" style={{ height: 16, marginBottom: 12, borderRadius: 8 }} />
                    ))}
                </div>
            )}

            {/* Results */}
            {assessment && !analyzing && (
                <>
                    {/* Score hero card */}
                    <div style={{
                        background: "#fff", border: "1px solid #e8ecf1", borderRadius: 14,
                        padding: "24px", marginBottom: 20,
                        display: "flex", alignItems: "center", gap: 24,
                        boxShadow: "0 2px 10px rgba(0,0,0,0.04)",
                    }}>
                        <div style={{ flexShrink: 0 }}>
                            <FraudScoreBadge score={assessment.fraud_score} label />
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                            {assessment.risk_level && (
                                <div style={{ marginBottom: 8 }}>
                                    <span className={`pill ${riskLabel(assessment.risk_level).cls}`} style={{ fontSize: "0.75rem", padding: "4px 14px" }}>
                                        {riskLabel(assessment.risk_level).text}
                                    </span>
                                </div>
                            )}
                            <div style={{ fontSize: "0.8125rem", color: "#64748b", lineHeight: 1.6 }}>
                                Fraud probability score based on analysis across 6 independent detection nodes.
                            </div>
                        </div>
                    </div>

                    {/* Manual review banner */}
                    {manualReview && (
                        <div style={{
                            background: "rgba(234,179,8,0.05)",
                            border: "1px solid rgba(234,179,8,0.22)",
                            borderRadius: 12, padding: "16px 18px", marginBottom: 18,
                        }}>
                            <div style={{
                                display: "flex", alignItems: "center", gap: 8, marginBottom: 8,
                                fontSize: "0.8125rem", fontWeight: 700, color: "#d97706",
                            }}>
                                <AlertTriangle size={15} />
                                Manual Review Required
                            </div>
                            {triggers.length > 0 && (
                                <ul style={{
                                    margin: 0, padding: "0 0 0 20px",
                                    fontSize: "0.8125rem", color: "#475569", lineHeight: 1.8,
                                }}>
                                    {triggers.map((t: string, i: number) => <li key={i}>{t}</li>)}
                                </ul>
                            )}
                        </div>
                    )}

                    {/* Critical signals */}
                    {criticalSignals.length > 0 && (
                        <div style={{
                            background: "rgba(220,38,38,0.04)",
                            border: "1px solid rgba(220,38,38,0.15)",
                            borderRadius: 12, padding: "16px 18px", marginBottom: 18,
                        }}>
                            <div style={{
                                display: "flex", alignItems: "center", gap: 8, marginBottom: 8,
                                fontSize: "0.8125rem", fontWeight: 700, color: "#dc2626",
                            }}>
                                <XCircle size={15} />
                                Critical Signals
                            </div>
                            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                                {criticalSignals.map((s: string, i: number) => (
                                    <span key={i} style={{
                                        fontFamily: "var(--font-mono)", fontSize: "0.75rem",
                                        background: "rgba(220,38,38,0.06)",
                                        border: "1px solid rgba(220,38,38,0.15)",
                                        borderRadius: 6, padding: "4px 10px",
                                        color: "#dc2626",
                                    }}>
                                        {s}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Per-node breakdown — expanded with more breathing room */}
                    {assessment.layer_scores && (
                        <div style={{
                            background: "#fff", border: "1px solid #e8ecf1", borderRadius: 14,
                            padding: "20px 22px", marginBottom: 18,
                            boxShadow: "0 1px 4px rgba(0,0,0,0.03)",
                        }}>
                            <div style={{
                                fontSize: "0.8125rem", color: "#0f172a",
                                marginBottom: 16, fontWeight: 700,
                                display: "flex", alignItems: "center", gap: 8,
                            }}>
                                <Activity size={14} color="#7c3aed" />
                                Agent Node Breakdown
                                <span style={{
                                    fontFamily: "var(--font-mono)", fontSize: "0.625rem",
                                    color: "#94a3b8", marginLeft: "auto",
                                    background: "#f1f5f9", borderRadius: 10, padding: "2px 10px",
                                }}>
                                    6 nodes
                                </span>
                            </div>
                            {NODE_ORDER.map((nodeName) => {
                                const layer = assessment.layer_scores?.[nodeName];
                                if (!layer) return null;
                                const nodeDetails = (assessment.layer_details as Record<string, Record<string, unknown>> | null)?.[nodeName];
                                return (
                                    <NodeScoreRow
                                        key={nodeName}
                                        nodeName={nodeName}
                                        score={layer.score}
                                        weight={layer.weight ?? 0}
                                        flags={layer.flags || []}
                                        details={nodeDetails?.details as Record<string, unknown> | null ?? null}
                                    />
                                );
                            })}
                        </div>
                    )}

                    {/* AI Risk Explanation */}
                    {assessment.explanation_text && (
                        <div style={{
                            background: "linear-gradient(135deg, rgba(26,86,219,0.03), rgba(124,58,237,0.03))",
                            border: "1px solid #e2e8f0",
                            borderRadius: 12, padding: "18px 20px", marginBottom: 18,
                        }}>
                            <div style={{
                                fontSize: "0.8125rem", color: "#0f172a",
                                marginBottom: 10, fontWeight: 700,
                                display: "flex", alignItems: "center", gap: 8,
                            }}>
                                <Brain size={14} color="#1a56db" />
                                AI Risk Explanation
                            </div>
                            <p style={{
                                fontSize: "0.875rem", color: "#475569",
                                lineHeight: 1.75, margin: 0, whiteSpace: "pre-wrap",
                            }}>
                                {assessment.explanation_text}
                            </p>
                        </div>
                    )}

                    {/* Footer meta */}
                    <div style={{
                        display: "flex", flexWrap: "wrap", gap: 16, alignItems: "center",
                        padding: "14px 0", borderTop: "1px solid #e8ecf1",
                        fontSize: "0.75rem", color: "#94a3b8", fontFamily: "var(--font-mono)",
                    }}>
                        {analyzedDoc && (
                            <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
                                <FileText size={11} />
                                {analyzedDoc.document_type.replace(/_/g, " ")}
                                {analyzedDoc.original_filename && ` (${analyzedDoc.original_filename})`}
                            </span>
                        )}
                        {assessment.config_version && (
                            <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
                                <CheckCircle size={11} color="#16a34a" />
                                {assessment.config_version}
                            </span>
                        )}
                        {assessment.ai_degraded_mode && (
                            <span style={{ display: "flex", alignItems: "center", gap: 5, color: "#d97706" }}>
                                <AlertTriangle size={11} /> Degraded
                            </span>
                        )}
                        <span style={{ marginLeft: "auto" }}>
                            {formatDateTime(assessment.created_at)}
                        </span>
                    </div>
                </>
            )}
        </div>
    );
}
