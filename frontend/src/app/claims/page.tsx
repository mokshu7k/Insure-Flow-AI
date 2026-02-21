"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CommandLayout } from "@/components/layout/CommandLayout";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { RiskBadge, StatusPill, MonoValue } from "@/components/ui";
import { useClaimStore } from "@/store/claimStore";
import { useAuthStore } from "@/store/authStore";
import { claimService } from "@/services/claimService";
import { Plus, Filter, ChevronLeft, ChevronRight, FileText } from "lucide-react";
import type { ClaimStatus, ClaimType } from "@/types";

const STATUSES: ClaimStatus[] = ["SUBMITTED", "UNDER_REVIEW", "FRAUD_ANALYZED", "APPROVED", "PRE_AUTHORIZED", "REJECTED", "MANUAL_REVIEW_REQUIRED", "SETTLED"];

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

export default function ClaimsPage() {
    return (
        <AuthGuard>
            <ClaimsContent />
        </AuthGuard>
    );
}

function ClaimsContent() {
    const router = useRouter();
    const [filterOpen, setFilterOpen] = useState(false);
    const user = useAuthStore((s) => s.user);
    const { claims, total, totalPages, page, pageSize, isLoading, statusFilter, fetchClaims, setPage, setFilter } = useClaimStore();

    useEffect(() => { fetchClaims(); }, []);

    return (
        <CommandLayout header={
                <div style={{ display: "flex", alignItems: "center", gap: 10, width: "100%" }}>
                    <FileText size={15} color="var(--text-muted)" />
                    <span style={{ fontSize: "2rem", fontWeight: 600 }}>Claims</span>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.6875rem", color: "var(--text-muted)", background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: 3, padding: "1px 6px" }}>
                        {total}
                    </span>

                    <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
                        {/* Filter */}
                        <div style={{ position: "relative" }}>
                            <button className="btn btn-ghost" onClick={() => setFilterOpen(!filterOpen)} style={{ gap: 6 }}>
                                <Filter size={13} />
                                {statusFilter ? statusFilter.replace(/_/g, " ") : "All statuses"}
                            </button>
                            {filterOpen && (
                                <div style={{
                                    position: "absolute", top: "calc(100% + 4px)", right: 0, zIndex: 50,
                                    background: "var(--bg-panel)", border: "1px solid var(--border)", borderRadius: 4,
                                    minWidth: 200, boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
                                }}>
                                    <div
                                        onClick={() => { setFilter(undefined); setFilterOpen(false); }}
                                        style={{ padding: "8px 12px", fontSize: "0.813rem", cursor: "pointer", color: !statusFilter ? "var(--blue)" : "var(--text-primary)" }}
                                    >
                                        All statuses
                                    </div>
                                    {STATUSES.map((s) => (
                                        <div key={s} onClick={() => { setFilter(s); setFilterOpen(false); }}
                                            style={{ padding: "8px 12px", fontSize: "0.8125rem", cursor: "pointer", color: statusFilter === s ? "var(--blue)" : "var(--text-primary)" }}>
                                            {s.replace(/_/g, " ")}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                        {user?.role === "CUSTOMER" && (
                            <button className="btn btn-primary" onClick={() => router.push("/claims/new")}>
                                <Plus size={13} />
                                New claim
                            </button>
                        )}
                    </div>
                </div>
            }>
                <div style={{ padding: "0" }}>
                    {/* Table */}
                    <div style={{ overflowX: "auto" }}>
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Claim ID</th>
                                    <th>Policy</th>
                                    <th>Type</th>
                                    <th style={{ textAlign: "right" }}>Amount</th>
                                    <th style={{ textAlign: "center" }}>Fraud Score</th>
                                    <th>Status</th>
                                    <th>Created</th>
                                </tr>
                            </thead>
                            <tbody>
                                {isLoading && [...Array(10)].map((_, i) => (
                                    <tr key={i}>
                                        {[130, 100, 70, 80, 70, 120, 70].map((w, j) => (
                                            <td key={j}><div className="skeleton" style={{ height: 11, width: w }} /></td>
                                        ))}
                                    </tr>
                                ))}
                                {!isLoading && claims.map((claim) => (
                                    <tr key={claim.id} onClick={() => router.push(`/claims/${claim.id}`)}>
                                        <td>
                                            <span className="mono" style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                                                {claim.id.slice(0, 8)}…
                                            </span>
                                        </td>
                                        <td><MonoValue value={claim.policy_number} size="0.8rem" /></td>
                                        <td>
                                            <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em", fontWeight: 500 }}>
                                                {claim.claim_type}
                                            </span>
                                        </td>
                                        <td style={{ textAlign: "right" }}>
                                            <MonoValue value={formatCurrency(claim.claim_amount)} />
                                        </td>
                                        <td style={{ textAlign: "center" }}>
                                            <RiskBadge score={claim.fraud_score} />
                                        </td>
                                        <td><StatusPill status={claim.status} /></td>
                                        <td>
                                            <span className="mono" style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                                                {formatDate(claim.created_at)}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                                {!isLoading && claims.length === 0 && (
                                    <tr>
                                        <td colSpan={7} style={{ textAlign: "center", padding: "40px 20px", color: "var(--text-muted)", fontSize: "0.875rem" }}>
                                            No claims found
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>

                    {/* Pagination */}
                    {totalPages > 1 && (
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 16px", borderTop: "1px solid var(--border)" }}>
                            <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.6875rem", color: "var(--text-muted)" }}>
                                {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total}
                            </span>
                            <div style={{ display: "flex", gap: 4 }}>
                                <button className="btn btn-ghost" style={{ padding: "4px 8px" }} disabled={page <= 1} onClick={() => setPage(page - 1)}>
                                    <ChevronLeft size={14} />
                                </button>
                                {[...Array(Math.min(totalPages, 5))].map((_, i) => {
                                    const p = i + Math.max(1, page - 2);
                                    if (p > totalPages) return null;
                                    return (
                                        <button key={p} className="btn btn-ghost" onClick={() => setPage(p)}
                                            style={{ padding: "4px 10px", background: p === page ? "var(--bg-hover)" : "transparent", color: p === page ? "var(--text-primary)" : "var(--text-muted)" }}>
                                            {p}
                                        </button>
                                    );
                                })}
                                <button className="btn btn-ghost" style={{ padding: "4px 8px" }} disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
                                    <ChevronRight size={14} />
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            </CommandLayout>
    );
}
