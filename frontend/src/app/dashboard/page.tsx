"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CommandLayout } from "@/components/layout/CommandLayout";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { StatusPill } from "@/components/ui";
import { useAuthStore } from "@/store/authStore";
import { dashboardService } from "@/services/dashboardService";
import type { OverviewMetrics, FraudDistribution, ComplianceSummary, CustomerMetrics, CustomerRecentClaim } from "@/types";
import {
    BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
    PieChart, Pie, Cell, Legend, AreaChart, Area, CartesianGrid,
} from "recharts";
import {
    TrendingUp, TrendingDown, Bell, ChevronRight, Activity, FileText,
    ArrowUpRight, ArrowDownRight, Target, Shield, CheckCircle2,
    DollarSign, Users, AlertTriangle, Clock,
} from "lucide-react";

// ── Shared tokens ─────────────────────────────────────────
const STATUS_COLORS: Record<string, string> = {
    SUBMITTED: "#64748b", OCR_PROCESSED: "#64748b",
    UNDER_REVIEW: "#d97706", MANUAL_REVIEW_REQUIRED: "#d97706", FRAUD_ANALYZED: "#d97706",
    APPROVED: "#16a34a", PRE_AUTHORIZED: "#10b981", SETTLED: "#1a56db",
    REJECTED: "#dc2626",
};

const PIE_COLORS = ["#1a56db", "#10b981", "#f59e0b", "#8b5cf6", "#dc2626", "#64748b"];

function fmt(n: number) {
    return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n);
}
function fmtL(n: number) {
    if (n >= 100000) return `₹${(n / 100000).toFixed(2)}L`;
    if (n >= 1000) return `₹${(n / 1000).toFixed(1)}K`;
    return `₹${n.toFixed(0)}`;
}
function fmtDate(s: string | null | undefined) {
    if (!s) return "—";
    const d = new Date(s);
    if (isNaN(d.getTime())) return "—";
    return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "2-digit" });
}

// ── Mini components ───────────────────────────────────────

function MetricCard({ icon, iconBg, iconColor, label, value, trend, trendUp, badge, badgeColor }: {
    icon: React.ReactNode; iconBg: string; iconColor: string;
    label: string; value: string | number;
    trend?: string; trendUp?: boolean;
    badge?: number; badgeColor?: string;
}) {
    return (
        <div className="animate-fade-up" style={{
            background: "#fff", border: "1px solid #e8ecf1", borderRadius: 14,
            padding: "18px 20px",
            display: "flex", alignItems: "center", gap: 16,
            boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
            transition: "all 0.22s",
            cursor: "default",
        }}
        onMouseEnter={(e) => { e.currentTarget.style.boxShadow = "0 4px 16px rgba(0,0,0,0.07)"; e.currentTarget.style.transform = "translateY(-2px)"; }}
        onMouseLeave={(e) => { e.currentTarget.style.boxShadow = "0 1px 3px rgba(0,0,0,0.04)"; e.currentTarget.style.transform = "translateY(0)"; }}
        >
            <div style={{
                width: 44, height: 44, borderRadius: 12,
                background: iconBg,
                display: "flex", alignItems: "center", justifyContent: "center",
                flexShrink: 0,
            }}>
                {icon}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: "0.6875rem", color: "#94a3b8", textTransform: "uppercase", fontWeight: 600, letterSpacing: "0.06em", marginBottom: 4 }}>
                    {label}
                </div>
                <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                    <span style={{ fontSize: "1.5rem", fontWeight: 800, fontFamily: "var(--font-mono)", color: "#0f172a", lineHeight: 1 }}>
                        {value}
                    </span>
                    {trend && (
                        <span style={{
                            display: "inline-flex", alignItems: "center", gap: 2,
                            fontSize: "0.6875rem", fontWeight: 700,
                            color: trendUp ? "#16a34a" : "#dc2626",
                        }}>
                            {trendUp ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                            {trend}
                        </span>
                    )}
                </div>
            </div>
            {badge !== undefined && (
                <div style={{
                    width: 36, height: 36, borderRadius: "50%",
                    background: badgeColor || "#e0e7ff",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: "0.75rem", fontWeight: 700, color: "#1a56db",
                    flexShrink: 0,
                }}>
                    {badge}
                </div>
            )}
        </div>
    );
}

function ProgressBar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
    const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
    return (
        <div className="animate-fade-up" style={{
            background: "#fff", border: "1px solid #e8ecf1", borderRadius: 12,
            padding: "16px 20px", flex: 1, minWidth: 140,
        }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 8 }}>
                <span style={{ fontSize: "1.25rem", fontWeight: 800, fontFamily: "var(--font-mono)", color: "#0f172a" }}>
                    {pct}%
                </span>
                <div style={{ height: 4, width: 40, borderRadius: 2, background: `${color}25`, overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${pct}%`, borderRadius: 2, background: color, transition: "width 0.8s ease" }} />
                </div>
            </div>
            <div style={{ fontSize: "0.6875rem", color: "#94a3b8", fontWeight: 500 }}>{label}</div>
        </div>
    );
}

function DonutCenter({ data, total, centerLabel }: { data: { name: string; value: number }[]; total: number; centerLabel: string }) {
    return (
        <div style={{ position: "relative" }}>
            <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                    <Pie
                        data={data}
                        dataKey="value"
                        nameKey="name"
                        cx="50%" cy="50%"
                        innerRadius={62} outerRadius={85}
                        paddingAngle={3}
                        strokeWidth={0}
                    >
                        {data.map((_, i) => (
                            <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                        ))}
                    </Pie>
                    <Tooltip
                        contentStyle={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 10, fontSize: 12, boxShadow: "0 4px 12px rgba(0,0,0,0.06)" }}
                    />
                    <Legend iconType="circle" iconSize={7} wrapperStyle={{ fontSize: "0.6875rem", color: "#64748b" }} />
                </PieChart>
            </ResponsiveContainer>
            {/* Center text */}
            <div style={{
                position: "absolute", top: "38%", left: "50%", transform: "translate(-50%, -50%)",
                textAlign: "center",
            }}>
                <div style={{ fontSize: "0.5625rem", color: "#94a3b8", textTransform: "uppercase", fontWeight: 600, letterSpacing: "0.08em" }}>
                    {centerLabel}
                </div>
                <div style={{ fontSize: "1.625rem", fontWeight: 800, fontFamily: "var(--font-mono)", color: "#0f172a", lineHeight: 1.1 }}>
                    {total}
                </div>
            </div>
        </div>
    );
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

    const approvalRate = metrics && metrics.total_claims > 0
        ? Math.round(((metrics.approved_claims + metrics.settled_claims) / metrics.total_claims) * 100)
        : null;
    const recoveryRate = metrics && metrics.total_claimed_amount > 0
        ? Math.round((metrics.total_settled_amount / metrics.total_claimed_amount) * 100)
        : null;

    // Generate area chart data from status breakdown
    const areaData = statusData.length > 0
        ? statusData.map((s) => ({ name: s.name.slice(0, 10), claims: s.count }))
        : [];

    return (
        <CommandLayout header={
            <div style={{ display: "flex", alignItems: "center", gap: 12, width: "100%" }}>
                <div style={{
                    width: 32, height: 32, borderRadius: 10,
                    background: "rgba(26, 86, 219, 0.08)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                    <Activity size={16} color="#1a56db" />
                </div>
                <div>
                    <span style={{ fontSize: "0.9375rem", fontWeight: 700, color: "#0f172a" }}>My Dashboard</span>
                </div>
                {metrics && (
                    <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", fontSize: "0.6875rem", color: "#94a3b8" }}>
                        Last updated {new Date(metrics.generated_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: true })}
                    </span>
                )}
            </div>
        }>
            <div className="animate-fade-in" style={{ padding: "24px", display: "flex", flexDirection: "column", gap: 20 }}>

                {/* Greeting banner */}
                <div className="animate-fade-up" style={{
                    background: "linear-gradient(135deg, #1a56db, #3b82f6)",
                    borderRadius: 16, padding: "24px 28px",
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                    color: "#fff",
                }}>
                    <div>
                        <div style={{ fontSize: "1.25rem", fontWeight: 800, marginBottom: 4 }}>
                            Welcome back, {firstName}! 👋
                        </div>
                        <div style={{ fontSize: "0.8125rem", opacity: 0.85 }}>
                            Here&apos;s a summary of your insurance activity and claims
                        </div>
                    </div>
                    <button onClick={() => router.push("/claims")} style={{
                        background: "rgba(255,255,255,0.18)", border: "1px solid rgba(255,255,255,0.25)",
                        borderRadius: 10, padding: "9px 20px", color: "#fff",
                        fontSize: "0.8125rem", fontWeight: 600, cursor: "pointer",
                        display: "flex", alignItems: "center", gap: 6,
                        transition: "all 0.15s",
                        backdropFilter: "blur(4px)",
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.28)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.18)"; }}
                    >
                        <FileText size={14} /> My Claims
                    </button>
                </div>

                {/* Attention banner */}
                {metrics && metrics.needs_action.length > 0 && (
                    <div className="animate-fade-up" style={{
                        display: "flex", alignItems: "center", gap: 10,
                        background: "#fffbeb", border: "1px solid #fde68a",
                        borderRadius: 12, padding: "12px 16px",
                    }}>
                        <Bell size={15} color="#d97706" />
                        <span style={{ fontSize: "0.8125rem", color: "#92400e", fontWeight: 500 }}>
                            {metrics.needs_action.length} claim{metrics.needs_action.length > 1 ? "s" : ""} require manual review — our team will contact you shortly.
                        </span>
                    </div>
                )}

                {/* Stat cards row — image style */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14 }}>
                    {loading ? (
                        [...Array(4)].map((_, i) => (
                            <div key={i} className="animate-fade-up" style={{
                                background: "#fff", border: "1px solid #e8ecf1", borderRadius: 14, padding: "18px 20px",
                            }}>
                                <div className="skeleton" style={{ height: 10, width: "50%", marginBottom: 14 }} />
                                <div className="skeleton" style={{ height: 28, width: "70%" }} />
                            </div>
                        ))
                    ) : (
                        <>
                            <MetricCard
                                icon={<FileText size={20} color="#1a56db" />}
                                iconBg="rgba(26,86,219,0.08)" iconColor="#1a56db"
                                label="Total Claims" value={metrics?.total_claims ?? 0}
                                badge={metrics?.active_claims ?? 0} badgeColor="#dbeafe"
                            />
                            <MetricCard
                                icon={<CheckCircle2 size={20} color="#16a34a" />}
                                iconBg="rgba(22,163,74,0.08)" iconColor="#16a34a"
                                label="Approved" value={metrics?.approved_claims ?? 0}
                                trend={approvalRate !== null ? `${approvalRate}%` : undefined}
                                trendUp={approvalRate !== null && approvalRate >= 50}
                            />
                            <MetricCard
                                icon={<DollarSign size={20} color="#7c3aed" />}
                                iconBg="rgba(124,58,237,0.08)" iconColor="#7c3aed"
                                label="Total Claimed" value={metrics ? fmtL(metrics.total_claimed_amount) : "—"}
                            />
                            <MetricCard
                                icon={<TrendingUp size={20} color="#0d9488" />}
                                iconBg="rgba(13,148,136,0.08)" iconColor="#0d9488"
                                label="Settled" value={metrics ? fmtL(metrics.total_settled_amount) : "—"}
                                trend={recoveryRate !== null ? `${recoveryRate}%` : undefined}
                                trendUp={recoveryRate !== null && recoveryRate > 0}
                            />
                        </>
                    )}
                </div>

                {/* Charts row */}
                {!loading && metrics && (
                    <div style={{ display: "grid", gridTemplateColumns: "1.6fr 1fr", gap: 16 }}>
                        {/* Status Area Chart */}
                        <div className="animate-fade-up" style={{
                            background: "#fff", border: "1px solid #e8ecf1", borderRadius: 14,
                            padding: "20px 24px",
                            boxShadow: "0 1px 3px rgba(0,0,0,0.03)",
                        }}>
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                                <div style={{ fontSize: "0.9375rem", fontWeight: 700, color: "#0f172a" }}>
                                    Claims by Status
                                </div>
                                <div style={{
                                    fontSize: "0.6875rem", fontWeight: 600, color: "#1a56db",
                                    background: "rgba(26,86,219,0.06)", padding: "4px 12px", borderRadius: 20,
                                }}>
                                    Overview
                                </div>
                            </div>
                            {areaData.length === 0 ? (
                                <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", color: "#94a3b8", fontSize: "0.8125rem" }}>No claims yet</div>
                            ) : (
                                <ResponsiveContainer width="100%" height={200}>
                                    <AreaChart data={areaData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                                        <defs>
                                            <linearGradient id="claimsGrad" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#1a56db" stopOpacity={0.15} />
                                                <stop offset="95%" stopColor="#1a56db" stopOpacity={0.01} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                                        <XAxis dataKey="name" tick={{ fontSize: 9, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                                        <YAxis tick={{ fontSize: 9, fill: "#94a3b8" }} axisLine={false} tickLine={false} allowDecimals={false} />
                                        <Tooltip contentStyle={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 10, fontSize: 12, boxShadow: "0 4px 12px rgba(0,0,0,0.06)" }} />
                                        <Area type="monotone" dataKey="claims" stroke="#1a56db" strokeWidth={2.5} fill="url(#claimsGrad)" dot={{ fill: "#fff", stroke: "#1a56db", strokeWidth: 2, r: 4 }} activeDot={{ r: 6, fill: "#1a56db", stroke: "#fff", strokeWidth: 2 }} />
                                    </AreaChart>
                                </ResponsiveContainer>
                            )}
                        </div>

                        {/* Claim type donut */}
                        <div className="animate-fade-up" style={{
                            background: "#fff", border: "1px solid #e8ecf1", borderRadius: 14,
                            padding: "20px 24px",
                            boxShadow: "0 1px 3px rgba(0,0,0,0.03)",
                        }}>
                            <div style={{ fontSize: "0.9375rem", fontWeight: 700, color: "#0f172a", marginBottom: 8 }}>
                                By Type
                            </div>
                            {typeData.length === 0 ? (
                                <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", color: "#94a3b8", fontSize: "0.8125rem" }}>No data</div>
                            ) : (
                                <DonutCenter
                                    data={typeData}
                                    total={metrics.total_claims}
                                    centerLabel="Total"
                                />
                            )}
                        </div>
                    </div>
                )}

                {/* Target Section — like the image */}
                {!loading && metrics && (
                    <div className="animate-fade-up">
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                <Target size={16} color="#1a56db" />
                                <span style={{ fontSize: "0.9375rem", fontWeight: 700, color: "#0f172a" }}>Target Section</span>
                            </div>
                            <button className="btn btn-ghost" style={{ fontSize: "0.75rem", gap: 4, padding: "5px 12px", borderRadius: 8 }} onClick={() => router.push("/claims")}>
                                View Details <ChevronRight size={12} />
                            </button>
                        </div>
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
                            <ProgressBar label="Approval Rate" value={metrics.approved_claims + metrics.settled_claims} max={metrics.total_claims} color="#dc2626" />
                            <ProgressBar label="Settlement Rate" value={metrics.settled_claims} max={metrics.total_claims} color="#1a56db" />
                            <ProgressBar label="Recovery Rate" value={metrics.total_settled_amount} max={metrics.total_claimed_amount} color="#d97706" />
                            <ProgressBar label="Active Claims" value={metrics.active_claims} max={metrics.total_claims} color="#16a34a" />
                        </div>
                    </div>
                )}

                {/* Recent claims */}
                {!loading && metrics && metrics.recent_claims.length > 0 && (
                    <div className="animate-fade-up" style={{
                        background: "#fff", border: "1px solid #e8ecf1", borderRadius: 14,
                        padding: "20px 24px",
                        boxShadow: "0 1px 3px rgba(0,0,0,0.03)",
                    }}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                            <div style={{ fontSize: "0.9375rem", fontWeight: 700, color: "#0f172a" }}>
                                Recent Claims
                            </div>
                            <button
                                className="btn btn-ghost"
                                style={{ fontSize: "0.75rem", gap: 4, padding: "5px 12px", borderRadius: 8 }}
                                onClick={() => router.push("/claims")}
                            >
                                View all <ChevronRight size={12} />
                            </button>
                        </div>
                        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                            {metrics.recent_claims.map((c: CustomerRecentClaim, idx: number) => (
                                <div
                                    key={c.id}
                                    className={`animate-fade-up stagger-${Math.min(idx + 1, 10)}`}
                                    onClick={() => router.push(`/claims/${c.id}`)}
                                    style={{
                                        display: "grid",
                                        gridTemplateColumns: "1fr auto auto auto",
                                        alignItems: "center",
                                        gap: 14,
                                        padding: "12px 14px",
                                        borderRadius: 10,
                                        cursor: "pointer",
                                        transition: "background 0.15s",
                                    }}
                                    onMouseEnter={(e) => { e.currentTarget.style.background = "#f8fafc"; }}
                                    onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                                >
                                    <div>
                                        <div style={{ fontSize: "0.8125rem", fontWeight: 600, color: "#0f172a" }}>{c.policy_number}</div>
                                        <div style={{ fontSize: "0.6875rem", color: "#94a3b8", marginTop: 2, display: "flex", alignItems: "center", gap: 4 }}>
                                            <Clock size={10} />
                                            {c.claim_type} · {fmtDate(c.created_at)}
                                        </div>
                                    </div>
                                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.8125rem", fontWeight: 600 }}>
                                        {c.claim_amount ? fmtL(c.claim_amount) : "—"}
                                    </span>
                                    <StatusPill status={c.status} />
                                    <ChevronRight size={14} color="#cbd5e1" />
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Empty state */}
                {!loading && metrics && metrics.total_claims === 0 && (
                    <div className="empty-state">
                        <div className="icon-wrap">
                            <FileText size={28} />
                        </div>
                        <div>
                            <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: 4 }}>No claims yet</h3>
                            <p style={{ color: "#94a3b8", fontSize: "0.8125rem", margin: 0, maxWidth: 320 }}>
                                Submit your first insurance claim to see your dashboard come to life.
                            </p>
                        </div>
                        <button className="btn btn-primary" onClick={() => router.push("/claims")} style={{ marginTop: 8, borderRadius: 10, padding: "10px 24px" }}>
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
    const router = useRouter();

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
        ? Object.entries(overview.status_breakdown).map(([k, v]) => ({ name: k.replace(/_/g, " "), status: k, count: v }))
        : [];
    const areaStatusData = statusData.map((s) => ({ name: s.name.slice(0, 10), claims: s.count }));

    const fraudData = fraud
        ? Object.entries(fraud.buckets).map(([range, count]) => ({ range, count }))
        : [];

    return (
        <CommandLayout header={
            <div style={{ display: "flex", alignItems: "center", gap: 12, width: "100%" }}>
                <div style={{
                    width: 32, height: 32, borderRadius: 10,
                    background: "rgba(26, 86, 219, 0.08)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                    <TrendingUp size={16} color="#1a56db" />
                </div>
                <div>
                    <span style={{ fontSize: "0.9375rem", fontWeight: 700, color: "#0f172a" }}>Operations Dashboard</span>
                </div>
                {overview && (
                    <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", fontSize: "0.6875rem", color: "#94a3b8" }}>
                        Refreshed {new Date(overview.generated_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: true })}
                    </span>
                )}
            </div>
        }>
            <div className="animate-fade-in" style={{ padding: "24px", display: "flex", flexDirection: "column", gap: 20 }}>

                {/* Info banner */}
                <div className="animate-fade-up" style={{
                    display: "flex", alignItems: "center", gap: 10,
                    background: "#eff6ff", border: "1px solid #bfdbfe",
                    borderRadius: 12, padding: "12px 16px",
                }}>
                    <Shield size={15} color="#1a56db" />
                    <span style={{ fontSize: "0.8125rem", color: "#1e40af", fontWeight: 500 }}>
                        This dashboard provides a portfolio overview of all claims, fraud analysis, and compliance metrics.
                    </span>
                </div>

                {/* Top metric cards */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14 }}>
                    {loading ? (
                        [...Array(4)].map((_, i) => (
                            <div key={i} style={{
                                background: "#fff", border: "1px solid #e8ecf1", borderRadius: 14, padding: "18px 20px",
                            }}>
                                <div className="skeleton" style={{ height: 10, width: "50%", marginBottom: 14 }} />
                                <div className="skeleton" style={{ height: 28, width: "70%" }} />
                            </div>
                        ))
                    ) : (
                        <>
                            <MetricCard
                                icon={<FileText size={20} color="#1a56db" />}
                                iconBg="rgba(26,86,219,0.08)" iconColor="#1a56db"
                                label="Total Claims" value={overview?.total_claims ?? 0}
                                badge={overview?.recent_claims_30d ?? 0} badgeColor="#dbeafe"
                            />
                            <MetricCard
                                icon={<Clock size={20} color="#d97706" />}
                                iconBg="rgba(217,119,6,0.08)" iconColor="#d97706"
                                label="Pending Review" value={overview?.pending_manual_review ?? 0}
                                trend={overview && overview.pending_manual_review > 3 ? "action needed" : undefined}
                                trendUp={false}
                            />
                            <MetricCard
                                icon={<DollarSign size={20} color="#16a34a" />}
                                iconBg="rgba(22,163,74,0.08)" iconColor="#16a34a"
                                label="Settled Amount" value={overview ? `₹${(overview.total_settled_amount / 100000).toFixed(2)}L` : "—"}
                            />
                            <MetricCard
                                icon={<Users size={20} color="#7c3aed" />}
                                iconBg="rgba(124,58,237,0.08)" iconColor="#7c3aed"
                                label="Last 30 Days" value={overview?.recent_claims_30d ?? 0}
                                trend="new" trendUp={true}
                            />
                        </>
                    )}
                </div>

                {/* Compliance metrics */}
                {compliance && (
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14 }}>
                        <MetricCard
                            icon={<Shield size={20} color="#1a56db" />}
                            iconBg="rgba(26,86,219,0.08)" iconColor="#1a56db"
                            label="Fraud Analyzed" value={compliance.claims_with_fraud_analysis}
                        />
                        <MetricCard
                            icon={<AlertTriangle size={20} color="#dc2626" />}
                            iconBg="rgba(220,38,38,0.08)" iconColor="#dc2626"
                            label="High Risk" value={compliance.high_risk_claims}
                            trend={compliance.high_risk_claims > 0 ? "critical" : undefined}
                            trendUp={false}
                        />
                        <MetricCard
                            icon={<Activity size={20} color="#d97706" />}
                            iconBg="rgba(217,119,6,0.08)" iconColor="#d97706"
                            label="Needs Review" value={compliance.human_review_required_count}
                        />
                        <MetricCard
                            icon={<CheckCircle2 size={20} color="#16a34a" />}
                            iconBg="rgba(22,163,74,0.08)" iconColor="#16a34a"
                            label="Compliance Rate" value={`${(compliance.compliance_rate * 100).toFixed(1)}%`}
                            trend={compliance.compliance_rate >= 0.9 ? "healthy" : undefined}
                            trendUp={compliance.compliance_rate >= 0.9}
                        />
                    </div>
                )}

                {/* Charts */}
                <div style={{ display: "grid", gridTemplateColumns: "1.6fr 1fr", gap: 16 }}>
                    {/* Claims by status — area chart */}
                    <div className="animate-fade-up" style={{
                        background: "#fff", border: "1px solid #e8ecf1", borderRadius: 14,
                        padding: "20px 24px",
                        boxShadow: "0 1px 3px rgba(0,0,0,0.03)",
                    }}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                            <div style={{ fontSize: "0.9375rem", fontWeight: 700, color: "#0f172a" }}>
                                Claims by Status
                            </div>
                            <div style={{
                                fontSize: "0.6875rem", fontWeight: 600, color: "#1a56db",
                                background: "rgba(26,86,219,0.06)", padding: "4px 12px", borderRadius: 20,
                            }}>
                                Overview
                            </div>
                        </div>
                        {loading ? <div className="skeleton" style={{ height: 210 }} /> : areaStatusData.length === 0 ? (
                            <div style={{ height: 210, display: "flex", alignItems: "center", justifyContent: "center", color: "#94a3b8" }}>No data</div>
                        ) : (
                            <ResponsiveContainer width="100%" height={210}>
                                <AreaChart data={areaStatusData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                                    <defs>
                                        <linearGradient id="adminClaimsGrad" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#1a56db" stopOpacity={0.15} />
                                            <stop offset="95%" stopColor="#1a56db" stopOpacity={0.01} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                                    <XAxis dataKey="name" tick={{ fontSize: 9, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                                    <YAxis tick={{ fontSize: 9, fill: "#94a3b8" }} axisLine={false} tickLine={false} allowDecimals={false} />
                                    <Tooltip contentStyle={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 10, fontSize: 12, boxShadow: "0 4px 12px rgba(0,0,0,0.06)" }} />
                                    <Area type="monotone" dataKey="claims" stroke="#1a56db" strokeWidth={2.5} fill="url(#adminClaimsGrad)" dot={{ fill: "#fff", stroke: "#1a56db", strokeWidth: 2, r: 4 }} activeDot={{ r: 6, fill: "#1a56db", stroke: "#fff", strokeWidth: 2 }} />
                                </AreaChart>
                            </ResponsiveContainer>
                        )}
                    </div>

                    {/* Fraud score donut */}
                    <div className="animate-fade-up" style={{
                        background: "#fff", border: "1px solid #e8ecf1", borderRadius: 14,
                        padding: "20px 24px",
                        boxShadow: "0 1px 3px rgba(0,0,0,0.03)",
                    }}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                            <div style={{ fontSize: "0.9375rem", fontWeight: 700, color: "#0f172a" }}>
                                Fraud Distribution
                            </div>
                        </div>
                        {fraud && (
                            <div style={{ marginBottom: 8, display: "flex", gap: 14, flexWrap: "wrap" }}>
                                <span style={{ fontSize: "0.6875rem", color: "#94a3b8", fontFamily: "var(--font-mono)" }}>
                                    Assessed: <span style={{ color: "#0f172a", fontWeight: 600 }}>{fraud.total_assessed}</span>
                                </span>
                                <span style={{ fontSize: "0.6875rem", color: "#94a3b8", fontFamily: "var(--font-mono)" }}>
                                    Mean: <span style={{ color: "#0f172a", fontWeight: 600 }}>{(fraud.mean_score * 100).toFixed(1)}%</span>
                                </span>
                            </div>
                        )}
                        {loading ? <div className="skeleton" style={{ height: 190 }} /> : fraudData.length === 0 ? (
                            <div style={{ height: 190, display: "flex", alignItems: "center", justifyContent: "center", color: "#94a3b8" }}>No data</div>
                        ) : (
                            <ResponsiveContainer width="100%" height={190}>
                                <BarChart data={fraudData} margin={{ top: 0, right: 5, left: -20, bottom: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                                    <XAxis dataKey="range" tick={{ fontSize: 9, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                                    <YAxis tick={{ fontSize: 9, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                                    <Tooltip contentStyle={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 10, fontSize: 12, boxShadow: "0 4px 12px rgba(0,0,0,0.06)" }} />
                                    <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                                        {fraudData.map(({ range }, i) => {
                                            const n = parseFloat(range);
                                            const color = n >= 0.7 ? "#dc2626" : n >= 0.4 ? "#f59e0b" : "#10b981";
                                            return <Cell key={i} fill={color} />;
                                        })}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                </div>

                {/* Target Section — Compliance targets */}
                {compliance && (
                    <div className="animate-fade-up">
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                <Target size={16} color="#1a56db" />
                                <span style={{ fontSize: "0.9375rem", fontWeight: 700, color: "#0f172a" }}>Target Section</span>
                            </div>
                            <button className="btn btn-ghost" style={{ fontSize: "0.75rem", gap: 4, padding: "5px 12px", borderRadius: 8 }} onClick={() => router.push("/adjuster")}>
                                View Details <ChevronRight size={12} />
                            </button>
                        </div>
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
                            <ProgressBar
                                label="Compliance Rate"
                                value={Math.round(compliance.compliance_rate * 100)}
                                max={100}
                                color="#dc2626"
                            />
                            <ProgressBar
                                label="Fraud Analysis"
                                value={compliance.claims_with_fraud_analysis}
                                max={overview?.total_claims ?? 1}
                                color="#1a56db"
                            />
                            <ProgressBar
                                label="High Risk Ratio"
                                value={compliance.high_risk_claims}
                                max={compliance.claims_with_fraud_analysis || 1}
                                color="#d97706"
                            />
                            <ProgressBar
                                label="Auto-Resolved"
                                value={(overview?.total_claims ?? 0) - (compliance.human_review_required_count ?? 0)}
                                max={overview?.total_claims ?? 1}
                                color="#16a34a"
                            />
                        </div>
                    </div>
                )}

            </div>
        </CommandLayout>
    );
}
