"use client";

import { useEffect, useState } from "react";
import { complianceService } from "@/services/complianceService";
import type { AuditLogEntry } from "@/types";
import { demoAuditLogs } from "@/lib/demoData";
import { formatDateTime } from "@/lib/utils";
import { Loader2, ClipboardList, ChevronDown, ChevronUp } from "lucide-react";

export default function AuditLogsPage() {
    const [logs, setLogs] = useState<AuditLogEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [entityTypeFilter, setEntityTypeFilter] = useState("");

    useEffect(() => {
        async function load() {
            setLoading(true);
            try {
                const data = await complianceService.getAuditTrail({
                    entity_type: entityTypeFilter || undefined,
                    limit: 100,
                });
                setLogs(data);
            } catch {
                // DEMO MODE
                const filtered = entityTypeFilter ? demoAuditLogs.filter(l => l.entity_type === entityTypeFilter) : demoAuditLogs;
                setLogs(filtered);
            } finally {
                setLoading(false);
            }
        }
        load();
    }, [entityTypeFilter]);

    const entityTypes = ["", "CLAIM", "USER", "DOCUMENT", "SETTLEMENT", "QR_AUTH"];

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold flex items-center gap-2">
                    <ClipboardList size={24} className="text-indigo-500" />
                    Audit Logs
                </h1>
                <p className="text-sm text-[var(--color-muted-foreground)]">
                    Immutable audit trail for compliance and regulatory review
                </p>
            </div>

            {/* Filters */}
            <div className="flex gap-2">
                {entityTypes.map((t) => (
                    <button
                        key={t}
                        onClick={() => setEntityTypeFilter(t)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${entityTypeFilter === t
                            ? "bg-indigo-600 text-white"
                            : "bg-[var(--color-muted)] text-[var(--color-muted-foreground)] hover:bg-[var(--color-border)]"
                            }`}
                    >
                        {t || "All"}
                    </button>
                ))}
            </div>

            {loading ? (
                <div className="flex items-center justify-center h-48">
                    <Loader2 size={28} className="animate-spin text-indigo-500" />
                </div>
            ) : logs.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-48 bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl text-sm text-[var(--color-muted-foreground)]">
                    No audit logs found
                </div>
            ) : (
                <div className="space-y-2">
                    {logs.map((log) => (
                        <div
                            key={log.id}
                            className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl overflow-hidden animate-fade-in"
                        >
                            <button
                                onClick={() =>
                                    setExpandedId(expandedId === log.id ? null : log.id)
                                }
                                className="w-full flex items-center justify-between p-4 hover:bg-[var(--color-muted)]/50 transition-colors text-left"
                            >
                                <div className="flex items-center gap-4 flex-1 min-w-0">
                                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-indigo-50 dark:bg-indigo-950/30 text-indigo-600 dark:text-indigo-300 shrink-0">
                                        {log.action_type}
                                    </span>
                                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-[var(--color-muted)] text-[var(--color-muted-foreground)] shrink-0">
                                        {log.entity_type}
                                    </span>
                                    <span className="text-xs text-[var(--color-muted-foreground)] truncate">
                                        {log.entity_id}
                                    </span>
                                </div>
                                <div className="flex items-center gap-3 shrink-0">
                                    <span className="text-xs text-[var(--color-muted-foreground)]">
                                        {formatDateTime(log.timestamp)}
                                    </span>
                                    {expandedId === log.id ? (
                                        <ChevronUp size={16} />
                                    ) : (
                                        <ChevronDown size={16} />
                                    )}
                                </div>
                            </button>

                            {expandedId === log.id && (
                                <div className="border-t border-[var(--color-border)] p-4 bg-[var(--color-muted)]/30">
                                    <div className="grid sm:grid-cols-2 gap-4 text-sm mb-3">
                                        <div>
                                            <p className="text-xs text-[var(--color-muted-foreground)]">
                                                Actor ID
                                            </p>
                                            <p className="font-mono text-xs">
                                                {log.actor_id || "System"}
                                            </p>
                                        </div>
                                        <div>
                                            <p className="text-xs text-[var(--color-muted-foreground)]">
                                                Entity ID
                                            </p>
                                            <p className="font-mono text-xs">
                                                {log.entity_id || "N/A"}
                                            </p>
                                        </div>
                                    </div>
                                    {log.metadata && Object.keys(log.metadata).length > 0 && (
                                        <div>
                                            <p className="text-xs text-[var(--color-muted-foreground)] mb-1">
                                                Metadata
                                            </p>
                                            <pre className="text-xs bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg p-3 overflow-x-auto">
                                                {JSON.stringify(log.metadata, null, 2)}
                                            </pre>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
