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
        <div style={{ padding: 20 }}>
            {/* Header + run button */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                <div style={{
                    fontSize: "0.6875rem", color: "var(--text-muted)", fontWeight: 600,
                    textTransform: "uppercase", letterSpacing: "0.06em",
                    display: "flex", alignItems: "center", gap: 6,
                }}>
                    <ShieldAlert size={13} />
                    Fraud Agent Intelligence
                </div>
            </div>

            {/* Document selector + run button */}
            <div style={{ display: "flex", gap: 6, marginBottom: 14, alignItems: "flex-end" }}>
                <div style={{ flex: 1 }}>
                    <div style={{
                        fontSize: "0.625rem", color: "var(--text-muted)",
                        textTransform: "uppercase", letterSpacing: "0.04em",
                        marginBottom: 4,
                    }}>
                        Target document
                    </div>
                    <select
                        className="input"
                        style={{ width: "100%", fontSize: "0.75rem", height: 30 }}
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
                    className="btn btn-ghost"
                    onClick={runAgentAnalysis}
                    disabled={isLoading || documents.length === 0}
                    style={{ padding: "4px 12px", height: 30, display: "flex", alignItems: "center", gap: 5 }}
                >
                    {analyzing ? <Loader2 size={13} style={{ animation: "spin 1s linear infinite" }} /> : <Zap size={13} />}
                    {analyzing ? "Analyzing…" : assessment ? "Re-run" : "Analyze"}
                </button>
            </div>

            {/* Error */}
            {error && (
                <div style={{
                    background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)",
                    borderRadius: 6, padding: "8px 12px", marginBottom: 14,
                    fontSize: "0.75rem", color: "var(--crimson)",
                }}>
                    {error}
                </div>
            )}

            {/* Empty state */}
            {!assessment && !isLoading && (
                <div style={{ textAlign: "center", padding: "30px 0", color: "var(--text-muted)", fontSize: "0.8125rem" }}>
                    {documents.length === 0
                        ? "Upload documents first, then run fraud analysis"
                        : "Run fraud analysis to see per-node intelligence"}
                </div>
            )}

            {/* Loading skeleton */}
            {isLoading && !assessment && (
                <div style={{ textAlign: "center", padding: "20px 0" }}>
                    <div className="skeleton" style={{ height: 80, marginBottom: 12 }} />
                    {[...Array(6)].map((_, i) => (
                        <div key={i} className="skeleton" style={{ height: 14, marginBottom: 10 }} />
                    ))}
                </div>
            )}

            {/* Results */}
            {assessment && !analyzing && (
                <>
                    {/* Fraud score badge */}
                    <div style={{ display: "flex", justifyContent: "center", marginBottom: 16 }}>
                        <FraudScoreBadge score={assessment.fraud_score} label />
                    </div>

                    {/* Risk level */}
                    {assessment.risk_level && (
                        <div style={{ textAlign: "center", marginBottom: 14 }}>
                            <span className={`pill ${riskLabel(assessment.risk_level).cls}`}>
                                {riskLabel(assessment.risk_level).text}
                            </span>
                        </div>
                    )}

                    {/* Manual review banner */}
                    {manualReview && (
                        <div style={{
                            background: "var(--amber-bg, rgba(234,179,8,0.06))",
                            border: "1px solid var(--amber-border, rgba(234,179,8,0.25))",
                            borderRadius: 8, padding: "12px 14px", marginBottom: 14,
                        }}>
                            <div style={{
                                display: "flex", alignItems: "center", gap: 6, marginBottom: 6,
                                fontSize: "0.6875rem", fontWeight: 700, color: "var(--amber)",
                                textTransform: "uppercase", letterSpacing: "0.05em",
                            }}>
                                <AlertTriangle size={13} />
                                Manual Review Required
                            </div>
                            {triggers.length > 0 && (
                                <ul style={{
                                    margin: 0, padding: "0 0 0 16px",
                                    fontSize: "0.75rem", color: "var(--text-secondary)", lineHeight: 1.7,
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
                            borderRadius: 8, padding: "12px 14px", marginBottom: 14,
                        }}>
                            <div style={{
                                display: "flex", alignItems: "center", gap: 6, marginBottom: 6,
                                fontSize: "0.6875rem", fontWeight: 700, color: "var(--crimson)",
                                textTransform: "uppercase", letterSpacing: "0.05em",
                            }}>
                                <XCircle size={13} />
                                Critical Signals
                            </div>
                            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                                {criticalSignals.map((s: string, i: number) => (
                                    <span key={i} style={{
                                        fontFamily: "var(--font-mono)", fontSize: "0.6875rem",
                                        background: "rgba(220,38,38,0.06)",
                                        border: "1px solid rgba(220,38,38,0.15)",
                                        borderRadius: 3, padding: "2px 6px",
                                        color: "var(--crimson)",
                                    }}>
                                        {s}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Per-node breakdown */}
                    {assessment.layer_scores && (
                        <div style={{ marginBottom: 14 }}>
                            <div style={{
                                fontSize: "0.6875rem", color: "var(--text-muted)",
                                textTransform: "uppercase", letterSpacing: "0.06em",
                                marginBottom: 8, fontWeight: 600,
                                display: "flex", alignItems: "center", gap: 6,
                            }}>
                                Agent Node Breakdown
                                <span style={{
                                    fontFamily: "var(--font-mono)", fontSize: "0.5625rem",
                                    color: "var(--text-muted)", opacity: 0.6,
                                }}>
                                    (6 nodes)
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
                            background: "var(--bg-surface)", border: "1px solid var(--border)",
                            borderRadius: 6, padding: 14, marginBottom: 14,
                        }}>
                            <div style={{
                                fontSize: "0.6875rem", color: "var(--text-muted)",
                                textTransform: "uppercase", letterSpacing: "0.06em",
                                marginBottom: 8, fontWeight: 600,
                                display: "flex", alignItems: "center", gap: 6,
                            }}>
                                <Brain size={12} />
                                AI Risk Explanation
                            </div>
                            <p style={{
                                fontSize: "0.8125rem", color: "var(--text-secondary)",
                                lineHeight: 1.7, margin: 0, whiteSpace: "pre-wrap",
                            }}>
                                {assessment.explanation_text}
                            </p>
                        </div>
                    )}

                    {/* Analyzed document info */}
                    {analyzedDoc && (
                        <div style={{
                            fontSize: "0.6875rem", color: "var(--text-muted)",
                            fontFamily: "var(--font-mono)", display: "flex", alignItems: "center", gap: 4,
                            marginBottom: 6,
                        }}>
                            <FileText size={10} />
                            Analyzed: {analyzedDoc.document_type.replace(/_/g, " ")}
                            {analyzedDoc.original_filename && ` (${analyzedDoc.original_filename})`}
                        </div>
                    )}

                    {/* Meta */}
                    <div style={{
                        fontSize: "0.6875rem", color: "var(--text-muted)",
                        fontFamily: "var(--font-mono)", display: "flex", flexDirection: "column",
                        gap: 3, borderTop: "1px solid var(--border)", paddingTop: 10,
                    }}>
                        {assessment.config_version && (
                            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                                <CheckCircle size={10} color="var(--green)" />
                                Engine: {assessment.config_version}
                            </span>
                        )}
                        {assessment.ai_degraded_mode && (
                            <span style={{ color: "var(--amber)" }}>
                                <AlertTriangle size={10} /> AI degraded mode
                            </span>
                        )}
                        <span>Assessed: {formatDateTime(assessment.created_at)}</span>
                    </div>
                </>
            )}
        </div>
    );
}
