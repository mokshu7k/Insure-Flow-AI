"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CommandLayout } from "@/components/layout/CommandLayout";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { StatCard, StatusPill } from "@/components/ui";
import { useAuthStore } from "@/store/authStore";
import { dashboardService } from "@/services/dashboardService";
import type { OverviewMetrics, FraudDistribution, ComplianceSummary, CustomerMetrics, CustomerRecentClaim } from "@/types";
import {
    BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
    PieChart, Pie, Cell, Legend,
} from "recharts";
import {
    TrendingUp, Bell, ChevronRight, Activity, FileText,
} from "lucide-react";

// ── Shared tokens ─────────────────────────────────────────
const STATUS_COLORS: Record<string, string> = {
    SUBMITTED: "#5a6070", OCR_PROCESSED: "#5a6070",
    UNDER_REVIEW: "#d97706", MANUAL_REVIEW_REQUIRED: "#d97706", FRAUD_ANALYZED: "#d97706",
    APPROVED: "#16a34a", PRE_AUTHORIZED: "#10b981", SETTLED: "#3b82f6",
    REJECTED: "#c0392b",
};

const TYPE_COLORS: Record<string, string> = {
    HEALTH: "#3b82f6",
    MOTOR: "#f59e0b",
    REIMBURSEMENT: "#8b5cf6",
    CASHLESS: "#10b981",
};

function fmt(n: number) {
    return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n);
}
function fmtL(n: number) {
    if (n >= 100000) return `₹${(n / 100000).toFixed(2)}L`;
    if (n >= 1000) return `₹${(n / 1000).toFixed(1)}K`;
    return `₹${n.toFixed(0)}`;
}
function fmtDate(s: string) {
    return new Date(s).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "2-digit" });
}

// ── Entry point — role-switches inside ────────────────────
export default function DashboardPage() {
    return (
        <AuthGuard>
            <DashboardRouter />
        </AuthGuard>
    );
}

function DashboardRouter() {
    const role = useAuthStore((s) => s.user?.role);
    const ADMIN_ROLES = ["INSURER_ADMIN", "AUDITOR", "CLAIM_ADJUSTER"];
    if (role && ADMIN_ROLES.includes(role)) return <AdminDashboardContent />;
    return <CustomerDashboardContent />;
}

// ═══════════════════════════════════════════════
//  CUSTOMER DASHBOARD
// ═══════════════════════════════════════════════
function CustomerDashboardContent() {
    const user = useAuthStore((s) => s.user);
    const router = useRouter();
    const [metrics, setMetrics] = useState<CustomerMetrics | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        dashboardService.customer().then(setMetrics).catch(console.error).finally(() => setLoading(false));
    }, []);

    const statusData = metrics
        ? Object.entries(metrics.status_breakdown).map(([k, v]) => ({ name: k.replace(/_/g, " "), status: k, count: v }))
        : [];
    const typeData = metrics
        ? Object.entries(metrics.type_breakdown).map(([k, v]) => ({ name: k, value: v }))
        : [];
    const firstName = user?.email?.split("@")[0] ?? "there";

    // Approval rate
    const approvalRate = metrics && metrics.total_claims > 0
        ? Math.round(((metrics.approved_claims + metrics.settled_claims) / metrics.total_claims) * 100)
        : null;
    // Recovery rate — settled vs total claimed
    const recoveryRate = metrics && metrics.total_claimed_amount > 0
        ? Math.round((metrics.total_settled_amount / metrics.total_claimed_amount) * 100)
        : null;

    return (
        <CommandLayout header={
            <div style={{ display: "flex", alignItems: "center", gap: 8, width: "100%" }}>
                <Activity size={15} color="var(--text-muted)" />
                <span style={{ fontSize: "0.875rem", fontWeight: 600 }}>My Dashboard</span>
                {metrics && (
                    <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", fontSize: "0.6875rem", color: "var(--text-muted)" }}>
                        updated {new Date(metrics.generated_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false })}
                    </span>
                )}
            </div>
        }>
            <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 20 }}>

                {/* Greeting */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div>
                        <div style={{ fontSize: "1.125rem", fontWeight: 700, marginBottom: 4 }}>
                            Hello, {firstName}
                        </div>
                        <div style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>
                            Here&apos;s a summary of your insurance activity
                        </div>
                    </div>
                    <button className="btn btn-primary" style={{ gap: 6 }} onClick={() => router.push("/claims")}>
                        <FileText size={13} />
                        My Claims
                    </button>
                </div>

                {/* Attention banner */}
                {metrics && metrics.needs_action.length > 0 && (
                    <div style={{
                        display: "flex", alignItems: "center", gap: 10,
                        background: "rgba(217, 119, 6, 0.08)", border: "1px solid rgba(217,119,6,0.3)",
                        borderRadius: 6, padding: "10px 14px",
                    }}>
                        <Bell size={14} color="var(--amber)" />
                        <span style={{ fontSize: "0.8125rem", color: "var(--amber)" }}>
                            {metrics.needs_action.length} claim{metrics.needs_action.length > 1 ? "s" : ""} require manual review — our team will contact you shortly.
                        </span>
                    </div>
                )}

                {/* Top stat cards */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
                    {loading ? (
                        [...Array(6)].map((_, i) => (
                            <div key={i} className="stat-card">
                                <div className="skeleton" style={{ height: 10, width: "60%", marginBottom: 12 }} />
                                <div className="skeleton" style={{ height: 28, width: "80%" }} />
                            </div>
                        ))
                    ) : (
                        <>
                            <StatCard
                                label="Total Claims"
                                value={metrics?.total_claims ?? 0}
                            />
                            <StatCard
                                label="Active"
                                value={metrics?.active_claims ?? 0}
                                sub="in pipeline"
                                accent={metrics && metrics.active_claims > 0 ? "var(--amber)" : undefined}
                            />
                            <StatCard
                                label="Approved"
                                value={metrics?.approved_claims ?? 0}
                                accent={metrics && metrics.approved_claims > 0 ? "var(--green)" : undefined}
                            />
                            <StatCard
                                label="Settled"
                                value={metrics?.settled_claims ?? 0}
                                accent={metrics && metrics.settled_claims > 0 ? "#3b82f6" : undefined}
                            />
                            <StatCard
                                label="Total Claimed"
                                value={metrics ? fmtL(metrics.total_claimed_amount) : "—"}
                                sub="across all claims"
                            />
                            <StatCard
                                label="Amount Settled"
                                value={metrics ? fmtL(metrics.total_settled_amount) : "—"}
                                sub="disbursed to you"
                                accent={metrics && metrics.total_settled_amount > 0 ? "var(--green)" : undefined}
                            />
                        </>
                    )}
                </div>

                {/* Rate cards */}
                {!loading && metrics && (
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
                        <div className="panel" style={{ padding: 16 }}>
                            <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
                                Approval Rate
                            </div>
                            <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
                                <span style={{ fontSize: "1.75rem", fontWeight: 700, fontFamily: "var(--font-mono)", color: approvalRate !== null && approvalRate >= 50 ? "var(--green)" : "var(--text-primary)" }}>
                                    {approvalRate !== null ? `${approvalRate}%` : "—"}
                                </span>
                            </div>
                            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 4 }}>
                                {metrics.approved_claims + metrics.settled_claims} of {metrics.total_claims} claims approved or settled
                            </div>
                        </div>
                        <div className="panel" style={{ padding: 16 }}>
                            <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
                                Settlement Recovery
                            </div>
                            <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
                                <span style={{ fontSize: "1.75rem", fontWeight: 700, fontFamily: "var(--font-mono)", color: "#3b82f6" }}>
                                    {recoveryRate !== null ? `${recoveryRate}%` : "—"}
                                </span>
                            </div>
                            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 4 }}>
                                {fmtL(metrics.total_settled_amount)} settled of {fmtL(metrics.total_claimed_amount)} claimed
                            </div>
                        </div>
                        <div className="panel" style={{ padding: 16 }}>
                            <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
                                Avg. Claim Size
                            </div>
                            <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
                                <span style={{ fontSize: "1.75rem", fontWeight: 700, fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
                                    {fmtL(metrics.average_claim_amount)}
                                </span>
                            </div>
                            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 4 }}>
                                per claim on average
                            </div>
                        </div>
                    </div>
                )}

                {/* Charts row */}
                {!loading && metrics && (
                    <div style={{ display: "grid", gridTemplateColumns: "1.6fr 1fr", gap: 16 }}>
                        {/* Status bar chart */}
                        <div className="panel" style={{ padding: 20 }}>
                            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 16 }}>
                                Claims by Status
                            </div>
                            {statusData.length === 0 ? (
                                <div style={{ height: 180, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: "0.8125rem" }}>No claims yet</div>
                            ) : (
                                <ResponsiveContainer width="100%" height={190}>
                                    <BarChart data={statusData} margin={{ top: 0, right: 0, left: -20, bottom: 48 }}>
                                        <XAxis dataKey="name" tick={{ fontSize: 9, fill: "#5a6070", fontFamily: "JetBrains Mono, monospace" }} angle={-30} textAnchor="end" />
                                        <YAxis tick={{ fontSize: 9, fill: "#5a6070", fontFamily: "JetBrains Mono, monospace" }} allowDecimals={false} />
                                        <Tooltip contentStyle={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: 4, fontSize: 12 }} cursor={{ fill: "var(--bg-hover)" }} />
                                        <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                                            {statusData.map((entry, i) => (
                                                <Cell key={i} fill={STATUS_COLORS[entry.status] || "#5a6070"} />
                                            ))}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            )}
                        </div>

                        {/* Claim type pie */}
                        <div className="panel" style={{ padding: 20 }}>
                            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 16 }}>
                                By Type
                            </div>
                            {typeData.length === 0 ? (
                                <div style={{ height: 190, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: "0.8125rem" }}>No data</div>
                            ) : (
                                <ResponsiveContainer width="100%" height={190}>
                                    <PieChart>
                                        <Pie data={typeData} dataKey="value" nameKey="name" cx="50%" cy="45%" outerRadius={65} paddingAngle={3}>
                                            {typeData.map(({ name }, i) => (
                                                <Cell key={i} fill={TYPE_COLORS[name] || "#5a6070"} />
                                            ))}
                                        </Pie>
                                        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)" }} />
                                        <Tooltip contentStyle={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: 4, fontSize: 12 }} />
                                    </PieChart>
                                </ResponsiveContainer>
                            )}
                        </div>
                    </div>
                )}

                {/* Recent claims */}
                {!loading && metrics && metrics.recent_claims.length > 0 && (
                    <div className="panel" style={{ padding: 20 }}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
                            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                                Recent Claims
                            </div>
                            <button
                                className="btn btn-ghost"
                                style={{ fontSize: "0.75rem", gap: 4, padding: "4px 8px" }}
                                onClick={() => router.push("/claims")}
                            >
                                View all <ChevronRight size={12} />
                            </button>
                        </div>
                        <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
                            {metrics.recent_claims.map((c: CustomerRecentClaim) => (
                                <div
                                    key={c.id}
                                    onClick={() => router.push(`/claims/${c.id}`)}
                                    style={{
                                        display: "grid",
                                        gridTemplateColumns: "1fr auto auto auto",
                                        alignItems: "center",
                                        gap: 12,
                                        padding: "10px 12px",
                                        borderRadius: 4,
                                        cursor: "pointer",
                                        transition: "background 0.1s",
                                    }}
                                    className="row-hover"
                                >
                                    <div>
                                        <div style={{ fontSize: "0.8125rem", fontWeight: 500 }}>{c.policy_number}</div>
                                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 2 }}>
                                            {c.claim_type} · {fmtDate(c.created_at)}
                                        </div>
                                    </div>
                                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.8125rem" }}>
                                        {c.claim_amount ? fmtL(c.claim_amount) : "—"}
                                    </span>
                                    <StatusPill status={c.status} />
                                    <ChevronRight size={13} color="var(--text-muted)" />
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Empty state */}
                {!loading && metrics && metrics.total_claims === 0 && (
                    <div className="panel" style={{ padding: 40, textAlign: "center" }}>
                        <FileText size={32} color="var(--text-muted)" style={{ marginBottom: 12 }} />
                        <div style={{ fontSize: "0.9375rem", fontWeight: 600, marginBottom: 6 }}>No claims yet</div>
                        <div style={{ fontSize: "0.8125rem", color: "var(--text-muted)", marginBottom: 20 }}>
                            Submit your first insurance claim to get started.
                        </div>
                        <button className="btn btn-primary" onClick={() => router.push("/claims")}>
                            File a Claim
                        </button>
                    </div>
                )}

            </div>
        </CommandLayout>
    );
}

// ═══════════════════════════════════════════════
//  ADMIN / OPERATIONS DASHBOARD
// ═══════════════════════════════════════════════
function AdminDashboardContent() {
    const [overview, setOverview] = useState<OverviewMetrics | null>(null);
    const [fraud, setFraud] = useState<FraudDistribution | null>(null);
    const [compliance, setCompliance] = useState<ComplianceSummary | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        setLoading(true);
        Promise.allSettled([
            dashboardService.overview(),
            dashboardService.fraudDistribution(),
            dashboardService.compliance(),
        ]).then(([o, f, c]) => {
            if (o.status === "fulfilled") setOverview(o.value);
            if (f.status === "fulfilled") setFraud(f.value);
            if (c.status === "fulfilled") setCompliance(c.value);
        }).finally(() => setLoading(false));
    }, []);

    const statusData = overview
        ? Object.entries(overview.status_breakdown).map(([k, v]) => ({ name: k, count: v }))
        : [];

    const fraudData = fraud
        ? Object.entries(fraud.buckets).map(([range, count]) => ({ range, count }))
        : [];

    return (
        <CommandLayout header={
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <TrendingUp size={15} color="var(--text-muted)" />
                <span style={{ fontSize: "0.875rem", fontWeight: 600 }}>Operations Dashboard</span>
                {overview && (
                    <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", fontSize: "0.6875rem", color: "var(--text-muted)" }}>
                        refreshed {new Date(overview.generated_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false })}
                    </span>
                )}
            </div>
        }>
            <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 20 }}>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
                    {loading ? (
                        [...Array(4)].map((_, i) => (
                            <div key={i} className="stat-card">
                                <div className="skeleton" style={{ height: 10, width: "60%", marginBottom: 12 }} />
                                <div className="skeleton" style={{ height: 28, width: "80%" }} />
                            </div>
                        ))
                    ) : (
                        <>
                            <StatCard label="Total Claims" value={overview?.total_claims ?? "—"} />
                            <StatCard label="Last 30 Days" value={overview?.recent_claims_30d ?? "—"} sub="new claims" />
                            <StatCard label="Pending Review" value={overview?.pending_manual_review ?? "—"} accent={overview && overview.pending_manual_review > 0 ? "var(--amber)" : undefined} />
                            <StatCard
                                label="Settled Amount"
                                value={overview ? `₹${(overview.total_settled_amount / 100000).toFixed(2)}L` : "—"}
                                sub="total disbursed"
                            />
                        </>
                    )}
                </div>

                {compliance && (
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
                        <StatCard label="Fraud Analyzed" value={compliance.claims_with_fraud_analysis} />
                        <StatCard label="High Risk" value={compliance.high_risk_claims} accent={compliance.high_risk_claims > 0 ? "var(--crimson)" : undefined} />
                        <StatCard label="Needs Human Review" value={compliance.human_review_required_count} accent={compliance.human_review_required_count > 0 ? "var(--amber)" : undefined} />
                        <StatCard label="Compliance Rate" value={`${(compliance.compliance_rate * 100).toFixed(1)}%`} accent="var(--green)" />
                    </div>
                )}

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                    <div className="panel" style={{ padding: 20 }}>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 16 }}>
                            Claims by Status
                        </div>
                        {loading ? <div className="skeleton" style={{ height: 200 }} /> : (
                            <ResponsiveContainer width="100%" height={200}>
                                <BarChart data={statusData} margin={{ top: 0, right: 0, left: -20, bottom: 40 }}>
                                    <XAxis dataKey="name" tick={{ fontSize: 9, fill: "#5a6070", fontFamily: "JetBrains Mono, monospace" }} angle={-35} textAnchor="end" />
                                    <YAxis tick={{ fontSize: 9, fill: "#5a6070", fontFamily: "JetBrains Mono, monospace" }} />
                                    <Tooltip contentStyle={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: 4, fontSize: 12 }} cursor={{ fill: "var(--bg-hover)" }} />
                                    <Bar dataKey="count" radius={[2, 2, 0, 0]}>
                                        {statusData.map((entry, i) => (
                                            <Cell key={i} fill={STATUS_COLORS[entry.name] || "#5a6070"} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        )}
                    </div>

                    <div className="panel" style={{ padding: 20 }}>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
                            Fraud Score Distribution
                        </div>
                        {fraud && (
                            <div style={{ marginBottom: 12, display: "flex", gap: 16, flexWrap: "wrap" }}>
                                <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.6875rem", color: "var(--text-muted)" }}>
                                    Assessed: <span style={{ color: "var(--text-primary)" }}>{fraud.total_assessed}</span>
                                </span>
                                <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.6875rem", color: "var(--text-muted)" }}>
                                    High risk: <span style={{ color: "var(--crimson)" }}>{fraud.high_risk_count}</span>
                                </span>
                                <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.6875rem", color: "var(--text-muted)" }}>
                                    Mean: <span style={{ color: "var(--text-primary)" }}>{(fraud.mean_score * 100).toFixed(1)}%</span>
                                </span>
                            </div>
                        )}
                        {loading ? <div className="skeleton" style={{ height: 180 }} /> : (
                            <ResponsiveContainer width="100%" height={180}>
                                <BarChart data={fraudData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                                    <XAxis dataKey="range" tick={{ fontSize: 9, fill: "#5a6070", fontFamily: "JetBrains Mono, monospace" }} />
                                    <YAxis tick={{ fontSize: 9, fill: "#5a6070", fontFamily: "JetBrains Mono, monospace" }} />
                                    <Tooltip contentStyle={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: 4, fontSize: 12 }} cursor={{ fill: "var(--bg-hover)" }} />
                                    <Bar dataKey="count" radius={[2, 2, 0, 0]}>
                                        {fraudData.map(({ range }, i) => {
                                            const n = parseFloat(range);
                                            const color = n >= 0.7 ? "var(--crimson)" : n >= 0.4 ? "var(--amber)" : "var(--green)";
                                            return <Cell key={i} fill={color} />;
                                        })}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                </div>
            </div>
        </CommandLayout>
    );
}
