"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { claimService } from "@/services/claimService";
import type { Claim } from "@/types";
import { demoClaims } from "@/lib/demoData";
import ClaimStatusBadge from "@/components/claims/ClaimStatusBadge";
import FraudScoreGauge from "@/components/fraud/FraudScoreGauge";
import { formatCurrency, formatDate } from "@/lib/utils";
import { Loader2, Shield } from "lucide-react";

export default function ReviewQueuePage() {
    const [claims, setClaims] = useState<Claim[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function load() {
            try {
                const res = await claimService.list({
                    status: "MANUAL_REVIEW_REQUIRED",
                    limit: 50,
                });
                setClaims(res.claims);
            } catch {
                // DEMO MODE
                setClaims(demoClaims.filter(c => c.status === "MANUAL_REVIEW_REQUIRED"));
            } finally {
                setLoading(false);
            }
        }
        load();
    }, []);

    const handleAction = async (id: string, status: "APPROVED" | "REJECTED") => {
        try {
            const updated = await claimService.updateStatus(id, { status });
            setClaims((prev) => prev.filter((c) => c.id !== updated.id));
        } catch {
            // handle error
        }
    };

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold flex items-center gap-2">
                    <Shield size={24} className="text-purple-500" />
                    Review Queue
                </h1>
                <p className="text-sm text-[var(--color-muted-foreground)]">
                    Claims requiring manual human-in-the-loop review
                </p>
            </div>

            {loading ? (
                <div className="flex items-center justify-center h-48">
                    <Loader2 size={28} className="animate-spin text-indigo-500" />
                </div>
            ) : claims.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-48 bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl">
                    <Shield size={40} className="text-emerald-500 mb-2" />
                    <p className="font-medium">All caught up!</p>
                    <p className="text-sm text-[var(--color-muted-foreground)]">
                        No claims requiring manual review
                    </p>
                </div>
            ) : (
                <div className="space-y-3">
                    {claims.map((claim) => (
                        <div
                            key={claim.id}
                            className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-5 hover:shadow-md transition-shadow animate-fade-in"
                        >
                            <div className="flex items-start justify-between gap-4">
                                <div className="flex items-start gap-4 flex-1 min-w-0">
                                    <FraudScoreGauge score={claim.fraud_score} size={64} />
                                    <div className="flex-1 min-w-0">
                                        <Link
                                            href={`/claims/${claim.id}`}
                                            className="font-semibold text-[var(--color-primary)] hover:underline"
                                        >
                                            {claim.policy_number}
                                        </Link>
                                        <p className="text-sm text-[var(--color-muted-foreground)]">
                                            {claim.claim_type} · {formatCurrency(claim.claim_amount)} ·{" "}
                                            {formatDate(claim.created_at)}
                                        </p>
                                        <div className="mt-2">
                                            <ClaimStatusBadge status={claim.status} />
                                        </div>
                                    </div>
                                </div>
                                <div className="flex gap-2 shrink-0">
                                    <button
                                        onClick={() => handleAction(claim.id, "APPROVED")}
                                        className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium transition-colors"
                                    >
                                        Approve
                                    </button>
                                    <button
                                        onClick={() => handleAction(claim.id, "REJECTED")}
                                        className="px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-white text-xs font-medium transition-colors"
                                    >
                                        Reject
                                    </button>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
