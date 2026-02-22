"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CommandLayout } from "@/components/layout/CommandLayout";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { RiskBadge, StatusPill, MonoValue } from "@/components/ui";
import { useClaimStore } from "@/store/claimStore";
import { useAuthStore } from "@/store/authStore";
import { claimService } from "@/services/claimService";
import { Plus, Filter, ChevronLeft, ChevronRight, FileText, Search, ArrowRight, TrendingUp, Clock, ShieldCheck } from "lucide-react";
import type { ClaimStatus, ClaimType } from "@/types";

const STATUS_TABS: { label: string; value: ClaimStatus | undefined }[] = [
    { label: "All", value: undefined },
    { label: "Submitted", value: "SUBMITTED" },
    { label: "Under Review", value: "UNDER_REVIEW" },
    { label: "Fraud Analyzed", value: "FRAUD_ANALYZED" },
    { label: "Approved", value: "APPROVED" },
    { label: "Pre-Authorized", value: "PRE_AUTHORIZED" },
    { label: "Rejected", value: "REJECTED" },
    { label: "Manual Review", value: "MANUAL_REVIEW_REQUIRED" },
    { label: "Settled", value: "SETTLED" },
];

const TYPE_COLORS: Record<string, string> = {
    HEALTH: "var(--green)",
    MOTOR: "var(--blue)",
    REIMBURSEMENT: "var(--amber)",
};

function formatCurrency(amount: number | null) {
    if (!amount) return "—";
    return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(amount);
}

function formatDate(dt: string | null | undefined) {
    if (!dt) return "—";
    const d = new Date(dt);
    if (isNaN(d.getTime())) return "—";
    return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "2-digit" });
}

function formatDateLong(dt: string | null | undefined) {
    if (!dt) return "—";
    const d = new Date(dt);
    if (isNaN(d.getTime())) return "—";
    return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export default function ClaimsPage() {
    return (
        <AuthGuard>
            <ClaimsContent />
        </AuthGuard>
    );
}

function ClaimsContent() {
    const router = useRouter();
    const user = useAuthStore((s) => s.user);
    const { claims, total, totalPages, page, pageSize, isLoading, statusFilter, fetchClaims, setPage, setFilter } = useClaimStore();

    useEffect(() => { fetchClaims(); }, []);

    return (
        <CommandLayout header={
            <div style={{ display: "flex", alignItems: "center", gap: 12, width: "100%" }}>
                <div style={{
                    width: 32, height: 32, borderRadius: 10,
                    background: "rgba(26, 86, 219, 0.1)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                    <FileText size={16} color="var(--blue)" />
                </div>
                <div>
                    <span style={{ fontSize: "0.9375rem", fontWeight: 700, color: "var(--text-primary)" }}>Claims</span>
                    <span className="stat-badge" style={{ marginLeft: 10 }}>{total} total</span>
                </div>
                <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
                    {user?.role === "CUSTOMER" && (
                        <button className="btn btn-primary" onClick={() => router.push("/claims/new")} style={{ borderRadius: 10, padding: "8px 18px", fontWeight: 600, gap: 6 }}>
                            <Plus size={14} />
                            New Claim
                        </button>
                    )}
                </div>
            </div>
        }>
            <div className="animate-fade-in" style={{ padding: "20px 24px" }}>

                {/* ── Status filter tabs ──────────────────────────── */}
                <div className="tab-bar" style={{ marginBottom: 20 }}>
                    {STATUS_TABS.map((tab) => (
                        <button
                            key={tab.label}
                            className={`tab-item ${statusFilter === tab.value ? "active" : ""}`}
                            onClick={() => setFilter(tab.value)}
                        >
                            {tab.label}
                        </button>
                    ))}
                </div>

                {/* ── Claim cards ─────────────────────────────────── */}
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    {isLoading && [...Array(6)].map((_, i) => (
                        <div
                            key={i}
                            className={`animate-fade-up stagger-${i + 1}`}
                            style={{
                                padding: "18px 20px", borderRadius: 12,
                                border: "1px solid var(--border)", background: "var(--bg-panel)",
                            }}
                        >
                            <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
                                <div className="skeleton" style={{ width: 42, height: 42, borderRadius: 10 }} />
                                <div style={{ flex: 1 }}>
                                    <div className="skeleton" style={{ height: 12, width: "40%", marginBottom: 8 }} />
                                    <div className="skeleton" style={{ height: 10, width: "70%" }} />
                                </div>
                                <div className="skeleton" style={{ height: 24, width: 80, borderRadius: 20 }} />
                            </div>
                        </div>
                    ))}

                    {!isLoading && claims.map((claim, i) => {
                        const typeColor = TYPE_COLORS[claim.claim_type] || "var(--blue)";
                        return (
                            <div
                                key={claim.id}
                                className={`claim-card animate-fade-up stagger-${Math.min(i + 1, 10)}`}
                                style={{ "--card-accent": typeColor } as React.CSSProperties}
                                onClick={() => router.push(`/claims/${claim.id}`)}
                            >
                                <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                                    {/* Type icon */}
                                    <div style={{
                                        width: 42, height: 42, borderRadius: 10,
                                        background: `${typeColor}14`,
                                        display: "flex", alignItems: "center", justifyContent: "center",
                                        flexShrink: 0,
                                    }}>
                                        {claim.claim_type === "HEALTH" && <ShieldCheck size={20} color={typeColor} />}
                                        {claim.claim_type === "MOTOR" && <TrendingUp size={20} color={typeColor} />}
                                        {claim.claim_type === "REIMBURSEMENT" && <FileText size={20} color={typeColor} />}
                                        {!["HEALTH", "MOTOR", "REIMBURSEMENT"].includes(claim.claim_type) && <FileText size={20} color={typeColor} />}
                                    </div>

                                    {/* Main info */}
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4, flexWrap: "wrap" }}>
                                            <span style={{ fontWeight: 600, fontSize: "0.875rem", color: "var(--text-primary)" }}>
                                                {claim.policy_number}
                                            </span>
                                            <span style={{
                                                fontSize: "0.625rem", fontWeight: 600,
                                                padding: "2px 8px", borderRadius: 99,
                                                background: `${typeColor}15`, color: typeColor,
                                                textTransform: "uppercase", letterSpacing: "0.04em",
                                            }}>
                                                {claim.claim_type}
                                            </span>
                                            <span className="mono" style={{ fontSize: "0.6875rem", color: "var(--text-muted)", marginLeft: "auto" }}>
                                                #{claim.id.slice(0, 8)}
                                            </span>
                                        </div>
                                        <div style={{ display: "flex", alignItems: "center", gap: 16, fontSize: "0.8125rem", flexWrap: "wrap" }}>
                                            <span style={{ fontWeight: 600, color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
                                                {formatCurrency(claim.claim_amount)}
                                            </span>
                                            <span style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--text-muted)", fontSize: "0.75rem" }}>
                                                <Clock size={12} />
                                                {formatDateLong(claim.created_at)}
                                            </span>
                                        </div>
                                    </div>

                                    {/* Right section */}
                                    <div style={{ display: "flex", alignItems: "center", gap: 12, flexShrink: 0 }}>
                                        <RiskBadge score={claim.fraud_score} />
                                        <StatusPill status={claim.status} />
                                        <ArrowRight size={16} color="var(--text-muted)" style={{ opacity: 0.4 }} />
                                    </div>
                                </div>
                            </div>
                        );
                    })}

                    {/* Empty state */}
                    {!isLoading && claims.length === 0 && (
                        <div className="empty-state">
                            <div className="icon-wrap">
                                <FileText size={28} />
                            </div>
                            <div>
                                <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 4 }}>No claims found</h3>
                                <p style={{ color: "var(--text-muted)", fontSize: "0.8125rem", margin: 0, maxWidth: 320 }}>
                                    {statusFilter
                                        ? `No claims with status "${statusFilter.replace(/_/g, " ").toLowerCase()}". Try a different filter.`
                                        : "You haven\u2019t filed any claims yet. Start by filing a new claim."
                                    }
                                </p>
                            </div>
                            {user?.role === "CUSTOMER" && !statusFilter && (
                                <button className="btn btn-primary" onClick={() => router.push("/claims/new")} style={{ marginTop: 8, borderRadius: 10, padding: "10px 24px", gap: 6 }}>
                                    <Plus size={14} /> File a Claim
                                </button>
                            )}
                        </div>
                    )}
                </div>

                {/* ── Pagination ──────────────────────────────────── */}
                {totalPages > 1 && (
                    <div style={{
                        display: "flex", alignItems: "center", justifyContent: "space-between",
                        padding: "16px 0 0", marginTop: 16, borderTop: "1px solid var(--border)",
                    }}>
                        <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "var(--text-muted)" }}>
                            Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total}
                        </span>
                        <div style={{ display: "flex", gap: 4 }}>
                            <button
                                className="btn btn-ghost"
                                style={{ padding: "6px 10px", borderRadius: 8 }}
                                disabled={page <= 1}
                                onClick={() => setPage(page - 1)}
                            >
                                <ChevronLeft size={14} />
                            </button>
                            {[...Array(Math.min(totalPages, 5))].map((_, i) => {
                                const p = i + Math.max(1, page - 2);
                                if (p > totalPages) return null;
                                return (
                                    <button
                                        key={p}
                                        className="btn btn-ghost"
                                        onClick={() => setPage(p)}
                                        style={{
                                            padding: "6px 12px", borderRadius: 8, fontWeight: p === page ? 700 : 400,
                                            background: p === page ? "var(--blue)" : "transparent",
                                            color: p === page ? "#fff" : "var(--text-muted)",
                                        }}
                                    >
                                        {p}
                                    </button>
                                );
                            })}
                            <button
                                className="btn btn-ghost"
                                style={{ padding: "6px 10px", borderRadius: 8 }}
                                disabled={page >= totalPages}
                                onClick={() => setPage(page + 1)}
                            >
                                <ChevronRight size={14} />
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </CommandLayout>
    );
}
