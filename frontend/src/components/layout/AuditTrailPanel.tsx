"use client";
import { useState, useEffect } from "react";
import { ChevronLeft, ChevronRight, Clock, Filter, Search } from "lucide-react";
import { complianceService } from "@/services/complianceService";
import type { AuditLogEntry } from "@/types";

interface AuditTrailPanelProps { claimId?: string; }

function formatAction(action: string) {
    return action.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatTime(ts: string | null | undefined) {
    if (!ts) return "—";
    const d = new Date(ts);
    if (isNaN(d.getTime())) return "—";
    return d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
}

function formatDate(ts: string | null | undefined) {
    if (!ts) return "—";
    const d = new Date(ts);
    if (isNaN(d.getTime())) return "—";
    return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "2-digit" });
}

function formatFullDate(ts: string | null | undefined) {
    if (!ts) return "—";
    const d = new Date(ts);
    if (isNaN(d.getTime())) return "—";
    return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

// Action badge colors — like the reference image
const ACTION_BADGE: Record<string, { bg: string; color: string; border: string }> = {
    CLAIM_SUBMITTED: { bg: "rgba(16,185,129,0.08)", color: "#059669", border: "rgba(16,185,129,0.2)" },
    CLAIM_STATUS_CHANGED: { bg: "rgba(124,58,237,0.08)", color: "#7c3aed", border: "rgba(124,58,237,0.2)" },
    FRAUD_ANALYZED: { bg: "rgba(220,38,38,0.08)", color: "#dc2626", border: "rgba(220,38,38,0.2)" },
    DOCUMENT_UPLOADED: { bg: "rgba(26,86,219,0.08)", color: "#1a56db", border: "rgba(26,86,219,0.2)" },
    USER_LOGIN: { bg: "rgba(100,116,139,0.08)", color: "#64748b", border: "rgba(100,116,139,0.2)" },
    DOCUMENT_EXTRACTED: { bg: "rgba(217,119,6,0.08)", color: "#d97706", border: "rgba(217,119,6,0.2)" },
    OCR_COMPLETED: { bg: "rgba(13,148,136,0.08)", color: "#0d9488", border: "rgba(13,148,136,0.2)" },
};

function getActionBadge(action: string) {
    return ACTION_BADGE[action] || { bg: "rgba(100,116,139,0.08)", color: "#64748b", border: "rgba(100,116,139,0.2)" };
}

// Simple avatar-like initials circle
function ActionAvatar({ action }: { action: string }) {
    const badge = getActionBadge(action);
    const initials = action.split("_").map(w => w[0]).join("").slice(0, 2);
    return (
        <div style={{
            width: 32, height: 32, borderRadius: "50%",
            background: badge.bg, border: `1px solid ${badge.border}`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: "0.625rem", fontWeight: 700, color: badge.color,
            flexShrink: 0, textTransform: "uppercase",
        }}>
            {initials}
        </div>
    );
}

export function AuditTrailPanel({ claimId }: AuditTrailPanelProps) {
    const [collapsed, setCollapsed] = useState(false);
    const [entries, setEntries] = useState<AuditLogEntry[]>([]);
    const [loading, setLoading] = useState(false);
    const [filterText, setFilterText] = useState("");
    const [page, setPage] = useState(0);
    const pageSize = 15;

    useEffect(() => {
        if (claimId) {
            setLoading(true);
            complianceService.auditTrail(claimId, 50)
                .then(setEntries)
                .catch(() => setEntries([]))
                .finally(() => setLoading(false));
        }
    }, [claimId]);

    // Filter entries
    const filtered = filterText
        ? entries.filter(e =>
            formatAction(e.action_type).toLowerCase().includes(filterText.toLowerCase()) ||
            e.entity_type.toLowerCase().includes(filterText.toLowerCase())
        )
        : entries;

    const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
    const paged = filtered.slice(page * pageSize, (page + 1) * pageSize);

    return (
        <aside style={{
            position: "relative",
            width: collapsed ? 40 : "var(--panel-width)",
            minWidth: collapsed ? 40 : "var(--panel-width)",
            background: "#ffffff",
            borderLeft: "1px solid #e8ecf1",
            display: "flex",
            flexDirection: "column",
            transition: "width 200ms ease",
            overflow: "visible",
        }}>
            {/* Collapse toggle */}
            <button
                onClick={() => setCollapsed(!collapsed)}
                style={{
                    position: "absolute", left: collapsed ? 8 : -12, top: 52,
                    background: "#fff",
                    border: "1px solid #e8ecf1",
                    borderRadius: "50%",
                    width: 24, height: 24,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    cursor: "pointer", zIndex: 10,
                    transition: "left 200ms",
                    boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
                }}
            >
                {collapsed ? <ChevronLeft size={12} /> : <ChevronRight size={12} />}
            </button>

            {!collapsed && (
                <>
                    {/* Header */}
                    <div style={{
                        padding: "16px 18px", borderBottom: "1px solid #e8ecf1",
                        display: "flex", alignItems: "center", gap: 8,
                    }}>
                        <Clock size={14} color="#1a56db" />
                        <span style={{ fontSize: "0.875rem", fontWeight: 700, color: "#0f172a" }}>
                            Audit Logs
                        </span>
                        {entries.length > 0 && (
                            <span style={{
                                marginLeft: "auto",
                                fontFamily: "var(--font-mono)", fontSize: "0.6875rem",
                                background: "#f1f5f9", color: "#64748b",
                                borderRadius: 10, padding: "2px 10px",
                                fontWeight: 600,
                            }}>
                                {entries.length}
                            </span>
                        )}
                    </div>

                    {/* Filter bar — like the reference image */}
                    {entries.length > 0 && (
                        <div style={{
                            padding: "10px 18px", borderBottom: "1px solid #f1f5f9",
                            display: "flex", alignItems: "center", gap: 8,
                        }}>
                            <div style={{
                                flex: 1, display: "flex", alignItems: "center", gap: 6,
                                background: "#f8fafc", border: "1px solid #e8ecf1",
                                borderRadius: 8, padding: "5px 10px",
                            }}>
                                <Search size={12} color="#94a3b8" />
                                <input
                                    type="text"
                                    placeholder="Filter..."
                                    value={filterText}
                                    onChange={(e) => { setFilterText(e.target.value); setPage(0); }}
                                    style={{
                                        border: "none", background: "transparent", outline: "none",
                                        fontSize: "0.75rem", color: "#0f172a", width: "100%",
                                    }}
                                />
                            </div>
                            <Filter size={13} color="#94a3b8" />
                        </div>
                    )}

                    {/* Table header */}
                    {entries.length > 0 && !loading && (
                        <div style={{
                            display: "grid",
                            gridTemplateColumns: "32px 1fr 70px 60px",
                            gap: 8,
                            padding: "8px 18px",
                            borderBottom: "1px solid #f1f5f9",
                            alignItems: "center",
                        }}>
                            <span />
                            <span style={{ fontSize: "0.625rem", color: "#94a3b8", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" }}>Action</span>
                            <span style={{ fontSize: "0.625rem", color: "#94a3b8", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" }}>Type</span>
                            <span style={{ fontSize: "0.625rem", color: "#94a3b8", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", textAlign: "right" }}>Time</span>
                        </div>
                    )}

                    {/* Entries list */}
                    <div style={{ flex: 1, overflowY: "auto", padding: "0" }}>
                        {loading && (
                            <div style={{ padding: "14px 18px" }}>
                                {[...Array(6)].map((_, i) => (
                                    <div key={i} style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 14 }}>
                                        <div className="skeleton" style={{ width: 32, height: 32, borderRadius: "50%", flexShrink: 0 }} />
                                        <div style={{ flex: 1 }}>
                                            <div className="skeleton" style={{ height: 10, width: "70%", marginBottom: 6 }} />
                                            <div className="skeleton" style={{ height: 8, width: "40%" }} />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}

                        {!loading && !claimId && (
                            <div style={{
                                padding: "40px 18px", textAlign: "center",
                            }}>
                                <Clock size={28} color="#cbd5e1" style={{ marginBottom: 10 }} />
                                <div style={{ fontSize: "0.8125rem", color: "#64748b", fontWeight: 500 }}>
                                    Select a claim to view its audit trail
                                </div>
                            </div>
                        )}

                        {!loading && claimId && entries.length === 0 && (
                            <div style={{
                                padding: "40px 18px", textAlign: "center",
                            }}>
                                <Clock size={28} color="#cbd5e1" style={{ marginBottom: 10 }} />
                                <div style={{ fontSize: "0.8125rem", color: "#64748b", fontWeight: 500 }}>
                                    No audit events yet
                                </div>
                            </div>
                        )}

                        {paged.map((entry, i) => {
                            const badge = getActionBadge(entry.action_type);
                            const metaStr = entry.metadata && Object.keys(entry.metadata).length > 0
                                ? JSON.stringify(entry.metadata).slice(0, 60)
                                : null;

                            return (
                                <div
                                    key={entry.id}
                                    style={{
                                        display: "grid",
                                        gridTemplateColumns: "32px 1fr 70px 60px",
                                        gap: 8,
                                        padding: "10px 18px",
                                        borderBottom: "1px solid #f8fafc",
                                        alignItems: "center",
                                        transition: "background 0.12s",
                                        cursor: "default",
                                    }}
                                    onMouseEnter={(e) => { e.currentTarget.style.background = "#f8fafc"; }}
                                    onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                                >
                                    {/* Avatar */}
                                    <ActionAvatar action={entry.action_type} />

                                    {/* Action + meta */}
                                    <div style={{ minWidth: 0 }}>
                                        <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                                            <span style={{
                                                fontSize: "0.8125rem", fontWeight: 600, color: "#0f172a",
                                                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                                            }}>
                                                {formatAction(entry.action_type)}
                                            </span>
                                            <span style={{
                                                fontSize: "0.5625rem", fontWeight: 700,
                                                background: badge.bg, color: badge.color,
                                                border: `1px solid ${badge.border}`,
                                                borderRadius: 4, padding: "1px 6px",
                                                textTransform: "uppercase", letterSpacing: "0.04em",
                                                flexShrink: 0,
                                            }}>
                                                {entry.action_type.split("_").pop()}
                                            </span>
                                        </div>
                                        {metaStr && (
                                            <div style={{
                                                fontSize: "0.625rem", color: "#94a3b8",
                                                fontFamily: "var(--font-mono)",
                                                marginTop: 2, overflow: "hidden",
                                                textOverflow: "ellipsis", whiteSpace: "nowrap",
                                            }}>
                                                {metaStr}{metaStr.length >= 60 ? "…" : ""}
                                            </div>
                                        )}
                                    </div>

                                    {/* Entity type */}
                                    <span style={{
                                        fontSize: "0.6875rem", color: "#64748b",
                                        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                                    }}>
                                        {entry.entity_type}
                                    </span>

                                    {/* Timestamp */}
                                    <div style={{ textAlign: "right" }}>
                                        <div style={{ fontSize: "0.6875rem", fontFamily: "var(--font-mono)", color: "#0f172a", fontWeight: 500 }}>
                                            {formatTime(entry.timestamp)}
                                        </div>
                                        <div style={{ fontSize: "0.5625rem", color: "#94a3b8" }}>
                                            {formatDate(entry.timestamp)}
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>

                    {/* Pagination footer — like the reference image */}
                    {filtered.length > pageSize && (
                        <div style={{
                            padding: "10px 18px", borderTop: "1px solid #e8ecf1",
                            display: "flex", alignItems: "center", justifyContent: "space-between",
                            fontSize: "0.6875rem", color: "#94a3b8",
                        }}>
                            <span>{filtered.length} items</span>
                            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                <span>Page {page + 1} / {totalPages}</span>
                                <button
                                    onClick={() => setPage(Math.max(0, page - 1))}
                                    disabled={page === 0}
                                    style={{
                                        width: 24, height: 24, borderRadius: 6,
                                        border: "1px solid #e8ecf1", background: "#fff",
                                        display: "flex", alignItems: "center", justifyContent: "center",
                                        cursor: page === 0 ? "default" : "pointer",
                                        opacity: page === 0 ? 0.4 : 1,
                                    }}
                                >
                                    <ChevronLeft size={12} />
                                </button>
                                <button
                                    onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
                                    disabled={page >= totalPages - 1}
                                    style={{
                                        width: 24, height: 24, borderRadius: 6,
                                        border: "1px solid #e8ecf1", background: "#fff",
                                        display: "flex", alignItems: "center", justifyContent: "center",
                                        cursor: page >= totalPages - 1 ? "default" : "pointer",
                                        opacity: page >= totalPages - 1 ? 0.4 : 1,
                                    }}
                                >
                                    <ChevronRight size={12} />
                                </button>
                            </div>
                        </div>
                    )}
                </>
            )}
        </aside>
    );
}
