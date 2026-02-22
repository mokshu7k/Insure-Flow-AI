"use client";
import { useEffect, useState, useCallback } from "react";
import { CommandLayout } from "@/components/layout/CommandLayout";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { MonoValue } from "@/components/ui";
import { auditService } from "@/services/auditService";
import type { AuditRun, AuditFinding, AuditRunDetail } from "@/types";
import { ShieldAlert, Play, RefreshCw, ChevronDown, ChevronRight, AlertTriangle, AlertCircle, Info, Minus } from "lucide-react";

// ── Helpers ────────────────────────────────────────────────────────────────

function formatDT(ts: string | null | undefined) {
    if (!ts) return "—";
    const d = new Date(ts);
    if (isNaN(d.getTime())) return "—";
    return d.toLocaleString("en-IN", {
        day: "2-digit", month: "short", year: "numeric",
        hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
    });
}

function duration(start: string, end: string | null) {
    if (!end) return "running…";
    const ms = new Date(end).getTime() - new Date(start).getTime();
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
}

const SEV_CONFIG: Record<string, { color: string; bg: string; icon: React.ReactNode }> = {
    CRITICAL: { color: "var(--crimson)", bg: "rgba(220,38,38,0.08)", icon: <AlertTriangle size={12} /> },
    HIGH:     { color: "var(--amber)",   bg: "rgba(217,119,6,0.08)",  icon: <AlertCircle size={12} /> },
    MEDIUM:   { color: "var(--blue)",    bg: "rgba(59,130,246,0.08)", icon: <Info size={12} /> },
    LOW:      { color: "var(--text-muted)", bg: "var(--bg-surface)",  icon: <Minus size={12} /> },
};

function SeverityBadge({ severity }: { severity: string }) {
    const cfg = SEV_CONFIG[severity] ?? SEV_CONFIG.LOW;
    return (
        <span style={{
            display: "inline-flex", alignItems: "center", gap: 4,
            fontFamily: "var(--font-mono)", fontSize: "0.625rem", fontWeight: 700,
            letterSpacing: "0.06em", padding: "2px 7px", borderRadius: 3,
            color: cfg.color, background: cfg.bg, border: `1px solid ${cfg.color}33`,
        }}>
            {cfg.icon}{severity}
        </span>
    );
}

function StatusBadge({ status }: { status: string }) {
    const color = status === "COMPLETED" ? "var(--green)"
        : status === "RUNNING" ? "var(--blue)"
        : status === "COMPLETED_WITH_ERRORS" ? "var(--amber)"
        : "var(--crimson)";
    return (
        <span style={{
            fontFamily: "var(--font-mono)", fontSize: "0.625rem", fontWeight: 700,
            letterSpacing: "0.06em", padding: "2px 7px", borderRadius: 3,
            color, background: `${color}18`, border: `1px solid ${color}44`,
        }}>{status}</span>
    );
}

function FindingCountPills({ run }: { run: AuditRun }) {
    const pills = [
        { label: "C", count: run.critical_count, color: "var(--crimson)" },
        { label: "H", count: run.high_count,     color: "var(--amber)" },
        { label: "M", count: run.medium_count,   color: "var(--blue)" },
        { label: "L", count: run.low_count,      color: "var(--text-muted)" },
    ];
    return (
        <div style={{ display: "flex", gap: 4 }}>
            {pills.map(({ label, count, color }) => (
                <span key={label} style={{
                    fontFamily: "var(--font-mono)", fontSize: "0.6rem", fontWeight: 700,
                    padding: "1px 5px", borderRadius: 3, color,
                    background: `${color}18`, border: `1px solid ${color}33`,
                    opacity: count === 0 ? 0.3 : 1,
                }}>{label}:{count}</span>
            ))}
        </div>
    );
}

// ── Finding row ────────────────────────────────────────────────────────────

function FindingRow({ f }: { f: AuditFinding }) {
    const [open, setOpen] = useState(false);
    return (
        <>
            <tr
                style={{ cursor: "pointer" }}
                onClick={() => setOpen((o) => !o)}
            >
                <td>{open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}</td>
                <td><SeverityBadge severity={f.severity} /></td>
                <td>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.7rem" }}>
                        {f.finding_type.replace(/_/g, " ")}
                    </span>
                </td>
                <td>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.7rem",
                        color: "var(--text-secondary)", background: "var(--bg-surface)",
                        border: "1px solid var(--border)", padding: "1px 5px", borderRadius: 3 }}>
                        {f.entity_type}
                    </span>
                </td>
                <td><MonoValue style={{ fontSize: "0.7rem" }}>{f.entity_id.slice(0, 16)}…</MonoValue></td>
                <td style={{ fontSize: "0.75rem", color: "var(--text-secondary)", maxWidth: 300 }}>
                    {f.description}
                </td>
                <td style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>{formatDT(f.created_at)}</td>
            </tr>
            {open && (
                <tr>
                    <td colSpan={7} style={{ padding: "0 0 0 24px", background: "var(--bg-surface)" }}>
                        <div style={{ padding: "12px 16px", borderLeft: `3px solid ${SEV_CONFIG[f.severity]?.color ?? "var(--border)"}` }}>
                            {f.gemini_narrative && (
                                <p style={{ fontSize: "0.8rem", color: "var(--text-primary)", marginBottom: 10, lineHeight: 1.6 }}>
                                    <strong style={{ color: "var(--text-secondary)" }}>Gemini Analysis: </strong>
                                    {f.gemini_narrative}
                                </p>
                            )}
                            {f.recommended_action && (
                                <p style={{ fontSize: "0.8rem", color: "var(--amber)", marginBottom: 10 }}>
                                    <strong>Recommended Action: </strong>{f.recommended_action}
                                </p>
                            )}
                            {f.supporting_entity_ids.length > 0 && (
                                <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: 8 }}>
                                    <strong>Supporting entities: </strong>
                                    {f.supporting_entity_ids.map((id) => (
                                        <MonoValue key={id} style={{ fontSize: "0.7rem", marginRight: 6 }}>{id}</MonoValue>
                                    ))}
                                </p>
                            )}
                            <details style={{ marginTop: 6 }}>
                                <summary style={{ fontSize: "0.7rem", color: "var(--text-muted)", cursor: "pointer" }}>
                                    Raw evidence
                                </summary>
                                <pre style={{
                                    fontSize: "0.65rem", background: "var(--bg-panel)", padding: 10,
                                    borderRadius: 4, marginTop: 6, overflowX: "auto", color: "var(--text-secondary)",
                                    border: "1px solid var(--border)", maxHeight: 200,
                                }}>
                                    {JSON.stringify(f.evidence, null, 2)}
                                </pre>
                            </details>
                        </div>
                    </td>
                </tr>
            )}
        </>
    );
}

// ── Run detail panel ───────────────────────────────────────────────────────

function RunDetail({ runId, onBack }: { runId: string; onBack: () => void }) {
    const [run, setRun] = useState<AuditRunDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [sevFilter, setSevFilter] = useState("ALL");

    useEffect(() => {
        setLoading(true);
        auditService.getRun(runId)
            .then(setRun)
            .catch(() => setRun(null))
            .finally(() => setLoading(false));
    }, [runId]);

    const findings = (run?.findings ?? []).filter(
        (f) => sevFilter === "ALL" || f.severity === sevFilter
    );

    return (
        <div>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                <button
                    onClick={onBack}
                    style={{ background: "none", border: "1px solid var(--border)", borderRadius: 4,
                        padding: "4px 12px", cursor: "pointer", color: "var(--text-secondary)",
                        fontSize: "0.8rem" }}>
                    ← Back
                </button>
                {run && (
                    <>
                        <MonoValue style={{ fontSize: "0.8rem" }}>{run.run_id}</MonoValue>
                        <StatusBadge status={run.status} />
                        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                            {formatDT(run.started_at)} · {duration(run.started_at, run.completed_at)}
                        </span>
                        <FindingCountPills run={run} />
                    </>
                )}
            </div>

            {loading && <div style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>Loading…</div>}
            {!loading && run && (
                <>
                    {run.summary_narrative && (
                        <div style={{
                            background: "var(--bg-surface)", border: "1px solid var(--border)",
                            borderRadius: 6, padding: "12px 16px", marginBottom: 16,
                        }}>
                            <p style={{ fontWeight: 600, fontSize: "0.75rem", color: "var(--text-secondary)", marginBottom: 6 }}>
                                Executive Summary
                            </p>
                            <p style={{ fontSize: "0.8rem", lineHeight: 1.7, color: "var(--text-primary)" }}>
                                {run.summary_narrative}
                            </p>
                        </div>
                    )}

                    {/* Severity filter */}
                    <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
                        {["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"].map((s) => {
                            const isActive = sevFilter === s;
                            const cfg = SEV_CONFIG[s];
                            return (
                                <button
                                    key={s}
                                    onClick={() => setSevFilter(s)}
                                    style={{
                                        fontFamily: "var(--font-mono)", fontSize: "0.7rem", fontWeight: 600,
                                        padding: "3px 10px", borderRadius: 4, cursor: "pointer",
                                        border: `1px solid ${isActive ? (cfg?.color ?? "var(--text-primary)") : "var(--border)"}`,
                                        background: isActive ? (cfg?.bg ?? "var(--bg-surface)") : "transparent",
                                        color: isActive ? (cfg?.color ?? "var(--text-primary)") : "var(--text-muted)",
                                    }}
                                >{s}</button>
                            );
                        })}
                    </div>

                    {findings.length === 0 ? (
                        <div style={{ textAlign: "center", color: "var(--text-muted)", padding: "32px 0", fontSize: "0.85rem" }}>
                            No findings{sevFilter !== "ALL" ? ` with severity ${sevFilter}` : ""}.
                        </div>
                    ) : (
                        <div style={{ overflowX: "auto" }}>
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th style={{ width: 24 }} />
                                        <th>Severity</th>
                                        <th>Finding Type</th>
                                        <th>Entity</th>
                                        <th>Entity ID</th>
                                        <th>Description</th>
                                        <th>Detected</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {findings.map((f) => <FindingRow key={f.id} f={f} />)}
                                </tbody>
                            </table>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}

// ── Main page ──────────────────────────────────────────────────────────────

export default function AuditPage() {
    const [runs, setRuns] = useState<AuditRun[]>([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [triggering, setTriggering] = useState(false);
    const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
    const [triggerMsg, setTriggerMsg] = useState<string | null>(null);

    const load = useCallback(() => {
        setLoading(true);
        auditService.listRuns(1, 50)
            .then((r) => { setRuns(r.items); setTotal(r.total); })
            .catch(() => { setRuns([]); setTotal(0); })
            .finally(() => setLoading(false));
    }, []);

    useEffect(() => { load(); }, [load]);

    const trigger = async () => {
        setTriggering(true);
        setTriggerMsg(null);
        try {
            const res = await auditService.triggerSweep();
            setTriggerMsg(`Sweep started: ${res.run_id}`);
            // Poll after 3s for the new run to appear
            setTimeout(load, 3000);
        } catch {
            setTriggerMsg("Failed to start sweep.");
        } finally {
            setTriggering(false);
        }
    };

    if (selectedRunId) {
        return (
            <AuthGuard requireAdmin>
                <CommandLayout header={
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <ShieldAlert size={15} color="var(--text-muted)" />
                        <span style={{ fontSize: "0.875rem", fontWeight: 600 }}>Audit Sweep — Run Detail</span>
                    </div>
                }>
                    <RunDetail runId={selectedRunId} onBack={() => setSelectedRunId(null)} />
                </CommandLayout>
            </AuthGuard>
        );
    }

    return (
        <AuthGuard requireAdmin>
            <CommandLayout header={
                <div style={{ display: "flex", alignItems: "center", gap: 10, width: "100%" }}>
                    <ShieldAlert size={15} color="var(--text-muted)" />
                    <span style={{ fontSize: "0.875rem", fontWeight: 600 }}>Audit Sweeps</span>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.6875rem",
                        color: "var(--text-muted)", background: "var(--bg-surface)",
                        border: "1px solid var(--border)", borderRadius: 3, padding: "1px 6px" }}>
                        {total}
                    </span>

                    <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
                        {triggerMsg && (
                            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                                {triggerMsg}
                            </span>
                        )}
                        <button
                            onClick={load}
                            title="Refresh"
                            style={{ background: "none", border: "1px solid var(--border)", borderRadius: 4,
                                padding: "4px 8px", cursor: "pointer", color: "var(--text-muted)",
                                display: "flex", alignItems: "center" }}>
                            <RefreshCw size={13} />
                        </button>
                        <button
                            onClick={trigger}
                            disabled={triggering}
                            style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.8rem",
                                fontWeight: 600, padding: "5px 14px", borderRadius: 4, cursor: "pointer",
                                background: triggering ? "var(--bg-surface)" : "var(--crimson)",
                                color: triggering ? "var(--text-muted)" : "#fff",
                                border: "none", opacity: triggering ? 0.6 : 1 }}>
                            {triggering ? <RefreshCw size={13} style={{ animation: "spin 1s linear infinite" }} /> : <Play size={13} />}
                            {triggering ? "Starting…" : "Run Audit Sweep"}
                        </button>
                    </div>
                </div>
            }>
                {loading ? (
                    <table className="data-table">
                        <thead><tr><th>Run ID</th><th>Status</th><th>Started</th><th>Duration</th><th>Findings</th><th>Summary</th></tr></thead>
                        <tbody>
                            {[...Array(8)].map((_, i) => (
                                <tr key={i}>
                                    {[180, 100, 130, 60, 120, 260].map((w, j) => (
                                        <td key={j}><div className="skeleton" style={{ height: 10, width: w }} /></td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                ) : runs.length === 0 ? (
                    <div style={{ textAlign: "center", padding: "60px 0" }}>
                        <ShieldAlert size={32} color="var(--text-muted)" style={{ marginBottom: 12 }} />
                        <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>No audit sweeps yet.</p>
                        <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginTop: 4 }}>
                            Click <strong>Run Audit Sweep</strong> to start the first one.
                        </p>
                    </div>
                ) : (
                    <div style={{ overflowX: "auto" }}>
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Run ID</th>
                                    <th>Status</th>
                                    <th>Started</th>
                                    <th>Duration</th>
                                    <th>Findings</th>
                                    <th>Summary</th>
                                </tr>
                            </thead>
                            <tbody>
                                {runs.map((run) => (
                                    <tr
                                        key={run.id}
                                        style={{ cursor: "pointer" }}
                                        onClick={() => setSelectedRunId(run.id)}
                                    >
                                        <td>
                                            <MonoValue style={{ fontSize: "0.75rem" }}>{run.run_id}</MonoValue>
                                        </td>
                                        <td><StatusBadge status={run.status} /></td>
                                        <td style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                                            {formatDT(run.started_at)}
                                        </td>
                                        <td>
                                            <MonoValue style={{ fontSize: "0.75rem" }}>
                                                {duration(run.started_at, run.completed_at)}
                                            </MonoValue>
                                        </td>
                                        <td><FindingCountPills run={run} /></td>
                                        <td style={{ fontSize: "0.75rem", color: "var(--text-muted)",
                                            maxWidth: 320, overflow: "hidden", textOverflow: "ellipsis",
                                            whiteSpace: "nowrap" }}>
                                            {run.summary_narrative ?? "—"}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </CommandLayout>
        </AuthGuard>
    );
}
