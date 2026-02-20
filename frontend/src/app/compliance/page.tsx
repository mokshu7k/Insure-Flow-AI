"use client";
import { useEffect, useState } from "react";
import { CommandLayout } from "@/components/layout/CommandLayout";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { MonoValue } from "@/components/ui";
import { complianceService } from "@/services/complianceService";
import type { AuditLogEntry } from "@/types";
import { Shield, Search } from "lucide-react";

function formatAction(a: string) { return a.replace(/_/g, " "); }
function formatDT(ts: string) {
    return new Date(ts).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
}

const ACTION_TYPE_COLOR: Record<string, string> = {
    CLAIM_SUBMITTED: "var(--blue)", CLAIM_STATUS_CHANGED: "var(--amber)",
    FRAUD_ANALYZED: "var(--crimson)", DOCUMENT_UPLOADED: "var(--text-secondary)",
    USER_LOGIN: "var(--text-muted)", USER_REGISTERED: "var(--green)",
};

export default function CompliancePage() {
    const [entries, setEntries] = useState<AuditLogEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState("");

    useEffect(() => {
        complianceService.auditTrail(undefined, 200)
            .then(setEntries)
            .catch(() => setEntries([]))
            .finally(() => setLoading(false));
    }, []);

    const filtered = entries.filter((e) =>
        !search || e.action_type.toLowerCase().includes(search.toLowerCase()) ||
        (e.entity_id || "").toLowerCase().includes(search.toLowerCase()) ||
        (e.actor_id || "").toLowerCase().includes(search.toLowerCase())
    );

    return (
        <AuthGuard requireAdmin>
            <CommandLayout header={
                <div style={{ display: "flex", alignItems: "center", gap: 10, width: "100%" }}>
                    <Shield size={15} color="var(--text-muted)" />
                    <span style={{ fontSize: "0.875rem", fontWeight: 600 }}>Compliance & Audit Trail</span>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.6875rem", color: "var(--text-muted)", background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: 3, padding: "1px 6px" }}>
                        {filtered.length}
                    </span>
                    <div style={{ marginLeft: "auto", position: "relative" }}>
                        <Search size={13} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
                        <input
                            className="input"
                            style={{ paddingLeft: 30, width: 220 }}
                            placeholder="Filter by action, entity, actor…"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                    </div>
                </div>
            }>
                <div style={{ overflowX: "auto" }}>
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>Action</th>
                                <th>Entity Type</th>
                                <th>Entity ID</th>
                                <th>Actor</th>
                                <th>Metadata</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading && [...Array(15)].map((_, i) => (
                                <tr key={i}>
                                    {[100, 160, 80, 120, 120, 200].map((w, j) => (
                                        <td key={j}><div className="skeleton" style={{ height: 10, width: w }} /></td>
                                    ))}
                                </tr>
                            ))}
                            {!loading && filtered.map((entry) => (
                                <tr key={entry.id} style={{ cursor: "default" }}>
                                    <td>
                                        <span className="mono" style={{ fontSize: "0.6875rem", color: "var(--text-muted)" }}>
                                            {formatDT(entry.timestamp)}
                                        </span>
                                    </td>
                                    <td>
                                        <span style={{ fontSize: "0.75rem", fontWeight: 500, color: ACTION_TYPE_COLOR[entry.action_type] || "var(--text-secondary)" }}>
                                            {formatAction(entry.action_type)}
                                        </span>
                                    </td>
                                    <td>
                                        <span style={{ fontSize: "0.6875rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                                            {entry.entity_type}
                                        </span>
                                    </td>
                                    <td>
                                        <MonoValue value={entry.entity_id?.slice(0, 8)} muted size="0.6875rem" />
                                        {entry.entity_id && <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.6875rem", color: "var(--text-muted)" }}>…</span>}
                                    </td>
                                    <td>
                                        <MonoValue value={entry.actor_id?.slice(0, 8)} muted size="0.6875rem" />
                                        {entry.actor_id && <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.6875rem", color: "var(--text-muted)" }}>…</span>}
                                    </td>
                                    <td>
                                        <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.625rem", color: "var(--text-muted)" }}>
                                            {JSON.stringify(entry.metadata).slice(0, 60)}
                                            {JSON.stringify(entry.metadata).length > 60 ? "…" : ""}
                                        </span>
                                    </td>
                                </tr>
                            ))}
                            {!loading && filtered.length === 0 && (
                                <tr>
                                    <td colSpan={6} style={{ textAlign: "center", padding: "40px", color: "var(--text-muted)", fontSize: "0.875rem" }}>
                                        No audit entries found
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </CommandLayout>
        </AuthGuard>
    );
}
