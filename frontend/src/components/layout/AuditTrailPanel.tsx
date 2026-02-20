"use client";
import { useState, useEffect } from "react";
import { ChevronLeft, ChevronRight, Clock } from "lucide-react";
import { complianceService } from "@/services/complianceService";
import type { AuditLogEntry } from "@/types";

interface AuditTrailPanelProps { claimId?: string; }

function formatAction(action: string) {
    return action.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatTime(ts: string) {
    return new Date(ts).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
}

function formatDate(ts: string) {
    return new Date(ts).toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}

export function AuditTrailPanel({ claimId }: AuditTrailPanelProps) {
    const [collapsed, setCollapsed] = useState(false);
    const [entries, setEntries] = useState<AuditLogEntry[]>([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (claimId) {
            setLoading(true);
            complianceService.auditTrail(claimId, 50)
                .then(setEntries)
                .catch(() => setEntries([]))
                .finally(() => setLoading(false));
        }
    }, [claimId]);

    return (
        <aside style={{
            position: "relative",
            width: collapsed ? 40 : "var(--panel-width)",
            minWidth: collapsed ? 40 : "var(--panel-width)",
            background: "var(--bg-panel)",
            borderLeft: "1px solid var(--border)",
            display: "flex",
            flexDirection: "column",
            transition: "width 200ms ease",
            overflow: "hidden",
        }}>
            {/* Collapse toggle */}
            <button
                onClick={() => setCollapsed(!collapsed)}
                style={{
                    position: "absolute", left: collapsed ? 8 : -1, top: 52,
                    background: "var(--bg-surface)",
                    border: "1px solid var(--border)",
                    borderRadius: "50%",
                    width: 24, height: 24,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    cursor: "pointer", zIndex: 10,
                    transition: "left 200ms",
                }}
            >
                {collapsed ? <ChevronLeft size={12} /> : <ChevronRight size={12} />}
            </button>

            {!collapsed && (
                <>
                    <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 6 }}>
                        <Clock size={13} color="var(--text-muted)" />
                        <span style={{ fontSize: "0.75rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-muted)" }}>
                            Audit Trail
                        </span>
                        {entries.length > 0 && (
                            <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", fontSize: "0.6875rem", color: "var(--text-muted)" }}>
                                {entries.length}
                            </span>
                        )}
                    </div>

                    <div style={{ flex: 1, overflowY: "auto", padding: "8px 0" }}>
                        {loading && (
                            <div style={{ padding: "12px 16px" }}>
                                {[...Array(6)].map((_, i) => (
                                    <div key={i} className="skeleton" style={{ height: 12, marginBottom: 10, width: i % 2 === 0 ? "80%" : "60%" }} />
                                ))}
                            </div>
                        )}

                        {!loading && !claimId && (
                            <div style={{ padding: "24px 16px", textAlign: "center", color: "var(--text-muted)", fontSize: "0.75rem" }}>
                                Select a claim to view its audit trail
                            </div>
                        )}

                        {!loading && claimId && entries.length === 0 && (
                            <div style={{ padding: "24px 16px", textAlign: "center", color: "var(--text-muted)", fontSize: "0.75rem" }}>
                                No audit events yet
                            </div>
                        )}

                        {entries.map((entry, i) => (
                            <div key={entry.id} style={{
                                padding: "8px 16px",
                                borderBottom: i < entries.length - 1 ? "1px solid var(--border)" : "none",
                            }}>
                                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 2 }}>
                                    <span style={{ fontSize: "0.75rem", fontWeight: 500 }}>{formatAction(entry.action_type)}</span>
                                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.625rem", color: "var(--text-muted)", whiteSpace: "nowrap", marginLeft: 8 }}>
                                        {formatTime(entry.timestamp)}
                                    </span>
                                </div>
                                <div style={{ fontSize: "0.625rem", color: "var(--text-muted)" }}>
                                    {formatDate(entry.timestamp)} · {entry.entity_type}
                                </div>
                                {entry.metadata && Object.keys(entry.metadata).length > 0 && (
                                    <div style={{ marginTop: 4, fontFamily: "var(--font-mono)", fontSize: "0.625rem", color: "var(--text-muted)", background: "var(--bg-surface)", borderRadius: 3, padding: "3px 6px", wordBreak: "break-all" }}>
                                        {JSON.stringify(entry.metadata).slice(0, 80)}
                                        {JSON.stringify(entry.metadata).length > 80 && "…"}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </>
            )}
        </aside>
    );
}
