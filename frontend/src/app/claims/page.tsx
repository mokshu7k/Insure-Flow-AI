"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { claimService } from "@/services/claimService";
import type { Claim, ClaimStatus } from "@/types";
import { demoClaims } from "@/lib/demoData";
import ClaimStatusBadge from "@/components/claims/ClaimStatusBadge";
import FraudScoreGauge from "@/components/fraud/FraudScoreGauge";
import { formatCurrency, formatDate } from "@/lib/utils";
import { Loader2, Plus, ChevronLeft, ChevronRight } from "lucide-react";

const statusOptions: (ClaimStatus | "ALL")[] = [
    "ALL",
    "SUBMITTED",
    "UNDER_REVIEW",
    "APPROVED",
    "REJECTED",
    "MANUAL_REVIEW_REQUIRED",
    "SETTLED",
];

export default function ClaimsListPage() {
    const [claims, setClaims] = useState<Claim[]>([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState<string>("ALL");
    const [page, setPage] = useState(0);
    const [total, setTotal] = useState(0);
    const pageSize = 10;

    useEffect(() => {
        async function load() {
            setLoading(true);
            try {
                const res = await claimService.list({
                    skip: page * pageSize,
                    limit: pageSize,
                    status: filter === "ALL" ? undefined : filter,
                });
                setClaims(res.claims);
                setTotal(res.total);
            } catch {
                // DEMO MODE: use demo data when backend is unavailable
                const filtered = filter === "ALL" ? demoClaims : demoClaims.filter(c => c.status === filter);
                setClaims(filtered.slice(page * pageSize, (page + 1) * pageSize));
                setTotal(filtered.length);
            } finally {
                setLoading(false);
            }
        }
        load();
    }, [page, filter]);

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold">Claims</h1>
                    <p className="text-sm text-[var(--color-muted-foreground)]">
                        Manage and track insurance claims
                    </p>
                </div>
                <Link
                    href="/claims/new"
                    className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-white bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 rounded-lg transition-all shadow-md hover:shadow-lg"
                >
                    <Plus size={16} />
                    New Claim
                </Link>
            </div>

            {/* Filters */}
            <div className="flex flex-wrap gap-2">
                {statusOptions.map((s) => (
                    <button
                        key={s}
                        onClick={() => {
                            setFilter(s);
                            setPage(0);
                        }}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${filter === s
                            ? "bg-indigo-600 text-white"
                            : "bg-[var(--color-muted)] text-[var(--color-muted-foreground)] hover:bg-[var(--color-border)]"
                            }`}
                    >
                        {s === "ALL" ? "All" : s.replace(/_/g, " ")}
                    </button>
                ))}
            </div>

            {/* Table */}
            {loading ? (
                <div className="flex items-center justify-center h-48">
                    <Loader2 size={28} className="animate-spin text-indigo-500" />
                </div>
            ) : claims.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-48 bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl">
                    <p className="text-[var(--color-muted-foreground)]">No claims found</p>
                </div>
            ) : (
                <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl overflow-hidden">
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
                                    <th className="text-left px-4 py-3 font-medium text-[var(--color-muted-foreground)]">
                                        Policy
                                    </th>
                                    <th className="text-left px-4 py-3 font-medium text-[var(--color-muted-foreground)]">
                                        Type
                                    </th>
                                    <th className="text-left px-4 py-3 font-medium text-[var(--color-muted-foreground)]">
                                        Amount
                                    </th>
                                    <th className="text-left px-4 py-3 font-medium text-[var(--color-muted-foreground)]">
                                        Status
                                    </th>
                                    <th className="text-center px-4 py-3 font-medium text-[var(--color-muted-foreground)]">
                                        Fraud
                                    </th>
                                    <th className="text-left px-4 py-3 font-medium text-[var(--color-muted-foreground)]">
                                        Date
                                    </th>
                                </tr>
                            </thead>
                            <tbody>
                                {claims.map((claim) => (
                                    <tr
                                        key={claim.id}
                                        className="border-b border-[var(--color-border)] hover:bg-[var(--color-muted)]/50 transition-colors"
                                    >
                                        <td className="px-4 py-3">
                                            <Link
                                                href={`/claims/${claim.id}`}
                                                className="font-medium text-[var(--color-primary)] hover:underline"
                                            >
                                                {claim.policy_number}
                                            </Link>
                                        </td>
                                        <td className="px-4 py-3 text-[var(--color-muted-foreground)]">
                                            {claim.claim_type}
                                        </td>
                                        <td className="px-4 py-3 font-semibold">
                                            {formatCurrency(claim.claim_amount)}
                                        </td>
                                        <td className="px-4 py-3">
                                            <ClaimStatusBadge status={claim.status} />
                                        </td>
                                        <td className="px-4 py-3">
                                            <div className="flex justify-center">
                                                <FraudScoreGauge score={claim.fraud_score} size={48} />
                                            </div>
                                        </td>
                                        <td className="px-4 py-3 text-[var(--color-muted-foreground)]">
                                            {formatDate(claim.created_at)}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    {/* Pagination */}
                    <div className="flex items-center justify-between px-4 py-3 border-t border-[var(--color-border)]">
                        <p className="text-xs text-[var(--color-muted-foreground)]">
                            Showing {page * pageSize + 1}–{Math.min((page + 1) * pageSize, total)} of {total}
                        </p>
                        <div className="flex gap-2">
                            <button
                                onClick={() => setPage(Math.max(0, page - 1))}
                                disabled={page === 0}
                                className="p-1.5 rounded-lg hover:bg-[var(--color-muted)] disabled:opacity-30 transition-colors"
                            >
                                <ChevronLeft size={16} />
                            </button>
                            <button
                                onClick={() => setPage(page + 1)}
                                disabled={(page + 1) * pageSize >= total}
                                className="p-1.5 rounded-lg hover:bg-[var(--color-muted)] disabled:opacity-30 transition-colors"
                            >
                                <ChevronRight size={16} />
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
