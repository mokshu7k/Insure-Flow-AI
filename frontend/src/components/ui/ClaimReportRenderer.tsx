"use client";
/**
 * ClaimReportRenderer
 *
 * Parses the free-text AI claim report into typed sections and renders each
 * one with distinct visual treatment.
 *
 * Recognised section headers (exact ALL-CAPS strings):
 *   CLAIMANT SUMMARY | CLAIM DETAILS | DOCUMENT ANALYSIS |
 *   DISCREPANCIES FOUND | FRAUD ASSESSMENT BREAKDOWN |
 *   AI RECOMMENDATION | ACTION ITEMS
 */
import React from "react";
import {
    User, FileText, AlertTriangle, ShieldAlert, Lightbulb,
    CheckCircle, XCircle, Clock, FileSearch, ChevronRight,
    AlertCircle, ListChecks,
} from "lucide-react";

// ─── types ───────────────────────────────────────────────────────────────────

type SectionKind =
    | "claimant_summary"
    | "claim_details"
    | "document_analysis"
    | "discrepancies"
    | "fraud_assessment"
    | "recommendation"
    | "action_items"
    | "unknown";

interface KV { key: string; value: string }
interface DocEntry { header: string; bullets: string[] }

interface Section {
    kind: SectionKind;
    rawTitle: string;
    paragraphs: string[];
    bullets: string[];
    kvPairs: KV[];
    documents: DocEntry[];
    recommendation: string | null;
}

// ─── parser ──────────────────────────────────────────────────────────────────

const HEADER_MAP: Record<string, SectionKind> = {
    "CLAIMANT SUMMARY": "claimant_summary",
    "CLAIM DETAILS": "claim_details",
    "DOCUMENT ANALYSIS": "document_analysis",
    "DISCREPANCIES FOUND": "discrepancies",
    "FRAUD ASSESSMENT BREAKDOWN": "fraud_assessment",
    "AI RECOMMENDATION": "recommendation",
    "ACTION ITEMS": "action_items",
};

const KNOWN_HEADERS = new Set(Object.keys(HEADER_MAP));

/** Only treat a line as a section header if it exactly matches one of the
 *  7 known section headings — prevents single-word verdicts like REJECT / APPROVE
 *  from being swallowed as headers. */
function isHeader(line: string): boolean {
    return KNOWN_HEADERS.has(line.trim());
}

function parseReport(text: string): Section[] {
    const lines = text.split("\n");
    const sections: Section[] = [];
    let current: Section | null = null;

    const flush = () => { if (current) sections.push(current); };

    for (const rawLine of lines) {
        const line = rawLine.trimEnd();

        if (isHeader(line)) {
            flush();
            const title = line.trim();
            current = {
                kind: HEADER_MAP[title] ?? "unknown",
                rawTitle: title,
                paragraphs: [],
                bullets: [],
                kvPairs: [],
                documents: [],
                recommendation: null,
            };
            continue;
        }

        if (!current) continue; // preamble before first header — skip

        const trimmed = line.trim();
        if (!trimmed) continue; // blank lines between content — skip

        if (current.kind === "recommendation") {
            // The first non-empty content line is the verdict
            if (!current.recommendation) {
                current.recommendation = trimmed;
            } else {
                current.paragraphs.push(trimmed);
            }
            continue;
        }

        if (trimmed.startsWith("- ")) {
            const body = trimmed.slice(2);

            if (current.kind === "claim_details") {
                // "- Key: Value" → kv pair
                const colon = body.indexOf(":");
                if (colon > 0) {
                    current.kvPairs.push({
                        key: body.slice(0, colon).trim(),
                        value: body.slice(colon + 1).trim(),
                    });
                } else {
                    current.bullets.push(body);
                }
            } else if (current.kind === "document_analysis") {
                // "- DOC_TYPE (filename)" starts a new document sub-section
                const docMatch = body.match(/^([A-Z_]+\s*\([^)]+\))/);
                if (docMatch) {
                    current.documents.push({ header: body, bullets: [] });
                } else {
                    // sub-bullet inside the active document
                    if (current.documents.length > 0) {
                        current.documents[current.documents.length - 1].bullets.push(body);
                    } else {
                        current.bullets.push(body);
                    }
                }
            } else {
                current.bullets.push(body);
            }
        } else {
            // Paragraph text
            current.paragraphs.push(trimmed);
        }
    }

    flush();
    return sections;
}

// ─── palette helpers ─────────────────────────────────────────────────────────

const SECTION_META: Record<SectionKind, { icon: React.ReactNode; color: string; bg: string; border: string; label: string }> = {
    claimant_summary:  { icon: <User size={15} />,          color: "#2563eb", bg: "rgba(37,99,235,0.06)",   border: "rgba(37,99,235,0.2)",   label: "Claimant Summary" },
    claim_details:     { icon: <FileText size={15} />,      color: "#7c3aed", bg: "rgba(124,58,237,0.06)",  border: "rgba(124,58,237,0.2)",  label: "Claim Details" },
    document_analysis: { icon: <FileSearch size={15} />,    color: "#059669", bg: "rgba(5,150,105,0.06)",   border: "rgba(5,150,105,0.2)",   label: "Document Analysis" },
    discrepancies:     { icon: <AlertTriangle size={15} />, color: "#ea580c", bg: "rgba(234,88,12,0.06)",   border: "rgba(234,88,12,0.2)",   label: "Discrepancies Found" },
    fraud_assessment:  { icon: <ShieldAlert size={15} />,   color: "#dc2626", bg: "rgba(220,38,38,0.06)",   border: "rgba(220,38,38,0.2)",   label: "Fraud Assessment" },
    recommendation:    { icon: <Lightbulb size={15} />,     color: "#ca8a04", bg: "rgba(202,138,4,0.06)",   border: "rgba(202,138,4,0.2)",   label: "AI Recommendation" },
    action_items:      { icon: <ListChecks size={15} />,    color: "#0284c7", bg: "rgba(2,132,199,0.06)",   border: "rgba(2,132,199,0.2)",   label: "Action Items" },
    unknown:           { icon: <FileText size={15} />,      color: "var(--text-muted)", bg: "transparent", border: "var(--border)", label: "Note" },
};

const VERDICT_STYLE: Record<string, { color: string; bg: string; border: string; icon: React.ReactNode }> = {
    REJECT:          { color: "#dc2626", bg: "rgba(220,38,38,0.08)",   border: "rgba(220,38,38,0.3)",   icon: <XCircle size={22} /> },
    REJECTED:        { color: "#dc2626", bg: "rgba(220,38,38,0.08)",   border: "rgba(220,38,38,0.3)",   icon: <XCircle size={22} /> },
    APPROVE:         { color: "#16a34a", bg: "rgba(22,163,74,0.08)",   border: "rgba(22,163,74,0.3)",   icon: <CheckCircle size={22} /> },
    APPROVED:        { color: "#16a34a", bg: "rgba(22,163,74,0.08)",   border: "rgba(22,163,74,0.3)",   icon: <CheckCircle size={22} /> },
    MANUAL_REVIEW:   { color: "#ca8a04", bg: "rgba(202,138,4,0.08)",   border: "rgba(202,138,4,0.3)",   icon: <Clock size={22} /> },
    REVIEW:          { color: "#ca8a04", bg: "rgba(202,138,4,0.08)",   border: "rgba(202,138,4,0.3)",   icon: <Clock size={22} /> },
    INVESTIGATE:     { color: "#ea580c", bg: "rgba(234,88,12,0.08)",   border: "rgba(234,88,12,0.3)",   icon: <AlertCircle size={22} /> },
};

const VERDICT_KEYWORDS = ["APPROVE", "REJECT", "MANUAL REVIEW", "MANUAL_REVIEW", "INVESTIGATE"] as const;

/** Extract the clean verdict keyword from a possibly longer string like
 *  "REJECT the claim because..." → "REJECT" */
function extractVerdict(rec: string): string {
    const upper = rec.toUpperCase();
    for (const kw of VERDICT_KEYWORDS) {
        if (upper === kw || upper.startsWith(kw + " ") || upper.startsWith(kw + ".")) return kw;
        if (upper.includes(kw)) return kw;
    }
    // Fallback: first word
    return rec.split(/\s+/)[0] ?? rec;
}

function verdictStyle(verdict: string) {
    const upper = verdict.toUpperCase().replace(/[\s-]+/g, "_");
    for (const key of Object.keys(VERDICT_STYLE)) {
        if (upper.includes(key)) return VERDICT_STYLE[key];
    }
    return VERDICT_STYLE["REVIEW"];
}

// ─── sub-renderers ───────────────────────────────────────────────────────────

function SectionCard({ section }: { section: Section }) {
    const meta = SECTION_META[section.kind];

    return (
        <div style={{
            border: `1px solid ${meta.border}`,
            borderRadius: 10,
            overflow: "hidden",
            marginBottom: 14,
        }}>
            {/* Section header bar */}
            <div style={{
                background: meta.bg,
                borderBottom: `1px solid ${meta.border}`,
                padding: "10px 16px",
                display: "flex",
                alignItems: "center",
                gap: 9,
            }}>
                <span style={{ color: meta.color, display: "flex", alignItems: "center" }}>{meta.icon}</span>
                <span style={{
                    fontSize: "0.6875rem",
                    fontWeight: 700,
                    letterSpacing: "0.07em",
                    textTransform: "uppercase",
                    color: meta.color,
                }}>
                    {meta.label}
                </span>
            </div>

            <div style={{ padding: "12px 14px", background: "var(--bg-surface)" }}>
                {section.kind === "claim_details"     && <ClaimDetailsBody section={section} />}
                {section.kind === "document_analysis" && <DocumentAnalysisBody section={section} />}
                {section.kind === "recommendation"    && <RecommendationBody section={section} />}
                {section.kind === "discrepancies"     && <BulletBody section={section} color="#ea580c" />}
                {section.kind === "fraud_assessment"  && <BulletBody section={section} color="#dc2626" />}
                {section.kind === "action_items"      && <ActionItemsBody section={section} />}
                {(section.kind === "claimant_summary" || section.kind === "unknown") && (
                    <ParagraphBody section={section} />
                )}
            </div>
        </div>
    );
}

function ParagraphBody({ section }: { section: Section }) {
    return (
        <>
            {section.paragraphs.map((p, i) => (
                <p key={i} style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", lineHeight: 1.75, marginBottom: 8 }}>{p}</p>
            ))}
            {section.bullets.map((b, i) => (
                <div key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start", marginBottom: 6 }}>
                    <ChevronRight size={14} style={{ color: "var(--text-muted)", flexShrink: 0, marginTop: 3 }} />
                    <span style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", lineHeight: 1.7 }}>{b}</span>
                </div>
            ))}
        </>
    );
}

function ClaimDetailsBody({ section }: { section: Section }) {
    return (
        <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
            gap: "10px 20px",
        }}>
            {section.kvPairs.map((kv, i) => (
                <div key={i} style={{
                    background: "var(--bg-panel)",
                    border: "1px solid var(--border)",
                    borderRadius: 7,
                    padding: "9px 12px",
                }}>
                    <div style={{ fontSize: "0.625rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 3, fontWeight: 600 }}>
                        {kv.key}
                    </div>
                    <div style={{ fontSize: "0.8125rem", color: "var(--text-primary)", fontWeight: 600, wordBreak: "break-all" }}>
                        {kv.value || "—"}
                    </div>
                </div>
            ))}
        </div>
    );
}

function DocumentAnalysisBody({ section }: { section: Section }) {
    if (section.documents.length === 0) return <ParagraphBody section={section} />;
    return (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {section.documents.map((doc, i) => {
                // Try to extract type + filename from header like "DISCHARGE_SUMMARY (discharge.pdf)"
                const match = doc.header.match(/^([^(]+)\(([^)]+)\)/);
                const docType = match ? match[1].trim() : doc.header;
                const fileName = match ? match[2].trim() : "";
                return (
                    <div key={i} style={{
                        background: "var(--bg-panel)",
                        border: "1px solid rgba(52,211,153,0.2)",
                        borderRadius: 8,
                        overflow: "hidden",
                    }}>
                        <div style={{
                            background: "rgba(52,211,153,0.07)",
                            padding: "7px 12px",
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                            borderBottom: "1px solid rgba(52,211,153,0.15)",
                        }}>
                            <FileText size={13} color="#059669" />
                            <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "#059669" }}>{docType}</span>
                            {fileName && (
                                <span style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontStyle: "italic" }}>({fileName})</span>
                            )}
                        </div>
                        <div style={{ padding: "8px 12px" }}>
                            {doc.bullets.map((b, j) => (
                                <div key={j} style={{ display: "flex", gap: 8, alignItems: "flex-start", marginBottom: 5 }}>
                                    <span style={{ color: "#059669", fontSize: "0.75rem", flexShrink: 0, marginTop: 3 }}>•</span>
                                    <span style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", lineHeight: 1.65 }}>{b}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

function BulletBody({ section, color }: { section: Section; color: string }) {
    return (
        <div>
            {section.paragraphs.map((p, i) => (
                <p key={i} style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", lineHeight: 1.75, marginBottom: 8 }}>{p}</p>
            ))}
            {section.bullets.map((b, i) => (
                <div key={i} style={{
                    display: "flex",
                    gap: 10,
                    alignItems: "flex-start",
                    marginBottom: 8,
                    background: `${color}0d`,
                    border: `1px solid ${color}30`,
                    borderRadius: 7,
                    padding: "8px 11px",
                }}>
                    <AlertCircle size={14} style={{ color, flexShrink: 0, marginTop: 2 }} />
                    <span style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", lineHeight: 1.65 }}>{b}</span>
                </div>
            ))}
        </div>
    );
}

function ActionItemsBody({ section }: { section: Section }) {
    return (
        <div>
            {section.bullets.map((b, i) => (
                <div key={i} style={{
                    display: "flex",
                    gap: 10,
                    alignItems: "flex-start",
                    marginBottom: 8,
                    padding: "8px 11px",
                    background: "rgba(56,189,248,0.06)",
                    border: "1px solid rgba(56,189,248,0.2)",
                    borderRadius: 7,
                }}>
                    <div style={{
                        background: "rgba(56,189,248,0.2)",
                        color: "#0284c7",
                        borderRadius: "50%",
                        width: 20,
                        height: 20,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: "0.6875rem",
                        fontWeight: 700,
                        flexShrink: 0,
                    }}>
                        {i + 1}
                    </div>
                    <span style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", lineHeight: 1.65 }}>{b}</span>
                </div>
            ))}
        </div>
    );
}

function RecommendationBody({ section }: { section: Section }) {
    const raw = section.recommendation ?? "";
    const verdict = extractVerdict(raw);
    const style = verdictStyle(verdict);
    // Show remaining text (after the keyword) as inline reasoning if it wasn't on its own line
    const reasoning = raw.trim().toUpperCase() === verdict.toUpperCase() ? "" : raw;
    return (
        <div>
            {/* Verdict badge */}
            <div style={{
                display: "flex",
                alignItems: "center",
                gap: 16,
                background: style.bg,
                border: `2px solid ${style.border}`,
                borderRadius: 10,
                padding: "16px 20px",
                marginBottom: (section.paragraphs.length > 0 || reasoning) ? 14 : 0,
            }}>
                <span style={{ color: style.color }}>{style.icon}</span>
                <div style={{ fontSize: "1rem", fontWeight: 800, color: style.color, letterSpacing: "0.04em", lineHeight: 1 }}>
                    {verdict}
                </div>
            </div>
            {reasoning && (
                <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", lineHeight: 1.75, marginBottom: 8 }}>{reasoning}</p>
            )}
            {section.paragraphs.map((p, i) => (
                <p key={i} style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", lineHeight: 1.75, marginBottom: 8 }}>{p}</p>
            ))}
        </div>
    );
}

// ─── main export ─────────────────────────────────────────────────────────────

export function ClaimReportRenderer({ report }: { report: string }) {
    const sections = parseReport(report);

    if (sections.length === 0) {
        // Fallback: just show raw text nicely
        return (
            <div style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", lineHeight: 1.75, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                {report}
            </div>
        );
    }

    return (
        <div style={{ display: "flex", flexDirection: "column" }}>
            {sections.map((section, i) => (
                <SectionCard key={i} section={section} />
            ))}
        </div>
    );
}
