"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { claimService } from "@/services/claimService";
import { fraudService } from "@/services/fraudService";
import { documentService } from "@/services/documentService";
import { settlementService } from "@/services/settlementService";
import type { Claim, FraudAssessment, DocumentResponse, Settlement } from "@/types";
import { demoClaims, demoFraudAssessments, demoDocuments, demoSettlements } from "@/lib/demoData";
import { useAuthStore } from "@/store/authStore";
import ClaimStatusBadge from "@/components/claims/ClaimStatusBadge";
import FraudScoreGauge from "@/components/fraud/FraudScoreGauge";
import FraudSignalsList from "@/components/fraud/FraudSignalsList";
import { formatCurrency, formatDate, formatDateTime } from "@/lib/utils";
import {
    Loader2,
    FileText,
    Download,
    Shield,
    CheckCircle2,
    XCircle,
    AlertTriangle,
    Zap,
} from "lucide-react";

export default function ClaimDetailPage() {
    const params = useParams();
    const claimId = params.id as string;
    const { user } = useAuthStore();

    const [claim, setClaim] = useState<Claim | null>(null);
    const [fraud, setFraud] = useState<FraudAssessment | null>(null);
    const [docs, setDocs] = useState<DocumentResponse[]>([]);
    const [settlement, setSettlement] = useState<Settlement | null>(null);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState("");

    useEffect(() => {
        async function load() {
            try {
                const c = await claimService.getById(claimId);
                setClaim(c);

                const [f, d, s] = await Promise.all([
                    fraudService.getAssessment(claimId).catch(() => null),
                    documentService.listByClaimId(claimId).catch(() => []),
                    settlementService.getByClaimId(claimId).catch(() => null),
                ]);
                if (f) setFraud(f);
                setDocs(d);
                if (s) setSettlement(s);
            } catch {
                // DEMO MODE: use demo data
                const demoClaim = demoClaims.find(c => c.id === claimId) ?? demoClaims[0];
                setClaim(demoClaim);
                setFraud(demoFraudAssessments[demoClaim.id] ?? null);
                setDocs(demoDocuments[demoClaim.id] ?? []);
                setSettlement(demoSettlements[demoClaim.id] ?? null);
            } finally {
                setLoading(false);
            }
        }
        load();
    }, [claimId]);

    const handleStatusUpdate = async (status: string) => {
        setActionLoading(status);
        try {
            const updated = await claimService.updateStatus(claimId, {
                status: status as "APPROVED" | "REJECTED" | "MANUAL_REVIEW_REQUIRED",
            });
            setClaim(updated);
        } catch {
            // handle error
        } finally {
            setActionLoading("");
        }
    };

    const handleTriggerAnalysis = async () => {
        setActionLoading("analyze");
        try {
            const updated = await claimService.triggerFraudAnalysis(claimId);
            setClaim(updated);
            const f = await fraudService.getAssessment(claimId).catch(() => null);
            if (f) setFraud(f);
        } catch {
            // handle error
        } finally {
            setActionLoading("");
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 size={32} className="animate-spin text-indigo-500" />
            </div>
        );
    }

    if (!claim) {
        return (
            <div className="flex flex-col items-center justify-center h-64">
                <p className="text-lg font-semibold">Claim not found</p>
            </div>
        );
    }

    const isAdmin = user?.role === "INSURER_ADMIN";

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            {/* Header */}
            <div className="flex items-start justify-between">
                <div>
                    <h1 className="text-2xl font-bold">Claim Details</h1>
                    <p className="text-sm text-[var(--color-muted-foreground)]">
                        {claim.policy_number} · {claim.claim_type}
                    </p>
                </div>
                <ClaimStatusBadge status={claim.status} />
            </div>

            {/* Info Cards */}
            <div className="grid sm:grid-cols-3 gap-4">
                <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-4">
                    <p className="text-xs font-medium text-[var(--color-muted-foreground)] uppercase tracking-wider">
                        Claim Amount
                    </p>
                    <p className="text-xl font-bold mt-1">
                        {formatCurrency(claim.claim_amount)}
                    </p>
                </div>
                <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-4">
                    <p className="text-xs font-medium text-[var(--color-muted-foreground)] uppercase tracking-wider">
                        Submitted
                    </p>
                    <p className="text-sm font-semibold mt-1">
                        {formatDateTime(claim.created_at)}
                    </p>
                </div>
                <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-4">
                    <p className="text-xs font-medium text-[var(--color-muted-foreground)] uppercase tracking-wider">
                        Last Updated
                    </p>
                    <p className="text-sm font-semibold mt-1">
                        {formatDateTime(claim.updated_at)}
                    </p>
                </div>
            </div>

            {/* Fraud Assessment */}
            <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-6">
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold flex items-center gap-2">
                        <Shield size={20} className="text-indigo-500" />
                        Fraud Assessment
                    </h2>
                    {isAdmin && (
                        <button
                            onClick={handleTriggerAnalysis}
                            disabled={actionLoading === "analyze"}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-indigo-50 dark:bg-indigo-950/30 text-indigo-600 dark:text-indigo-300 rounded-lg hover:bg-indigo-100 dark:hover:bg-indigo-950/50 transition-colors disabled:opacity-50"
                        >
                            {actionLoading === "analyze" ? (
                                <Loader2 size={14} className="animate-spin" />
                            ) : (
                                <Zap size={14} />
                            )}
                            Run Analysis
                        </button>
                    )}
                </div>

                {fraud ? (
                    <div className="grid sm:grid-cols-[120px_1fr] gap-6">
                        <div className="flex justify-center">
                            <FraudScoreGauge score={fraud.fraud_score} />
                        </div>
                        <div className="space-y-4">
                            <div>
                                <h3 className="text-sm font-medium mb-2">Explanation</h3>
                                <p className="text-sm text-[var(--color-muted-foreground)] leading-relaxed">
                                    {fraud.explanation_text}
                                </p>
                            </div>
                            <FraudSignalsList
                                deterministic={fraud.deterministic_signals}
                                statistical={fraud.statistical_signals}
                            />
                        </div>
                    </div>
                ) : (
                    <p className="text-sm text-[var(--color-muted-foreground)]">
                        No fraud assessment available. {isAdmin && "Click 'Run Analysis' to trigger."}
                    </p>
                )}
            </div>

            {/* Documents */}
            <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-6">
                <h2 className="text-lg font-semibold flex items-center gap-2 mb-4">
                    <FileText size={20} className="text-indigo-500" />
                    Documents ({docs.length})
                </h2>
                {docs.length > 0 ? (
                    <div className="space-y-2">
                        {docs.map((doc) => (
                            <div
                                key={doc.id}
                                className="flex items-center justify-between p-3 rounded-lg bg-[var(--color-muted)]"
                            >
                                <div>
                                    <p className="text-sm font-medium">
                                        {doc.document_type.replace(/_/g, " ")}
                                    </p>
                                    <p className="text-xs text-[var(--color-muted-foreground)]">
                                        {formatDate(doc.created_at)} ·{" "}
                                        {doc.has_ocr_data
                                            ? `OCR ${(doc.ocr_confidence ?? 0) * 100}%`
                                            : "No OCR"}
                                    </p>
                                </div>
                                <button
                                    onClick={() => {
                                        documentService.download(doc.id).then((blob) => {
                                            const url = URL.createObjectURL(blob);
                                            window.open(url);
                                        });
                                    }}
                                    className="p-2 rounded-lg hover:bg-[var(--color-border)] transition-colors"
                                >
                                    <Download size={16} />
                                </button>
                            </div>
                        ))}
                    </div>
                ) : (
                    <p className="text-sm text-[var(--color-muted-foreground)]">
                        No documents uploaded yet.
                    </p>
                )}
            </div>

            {/* Settlement */}
            {settlement && (
                <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-6">
                    <h2 className="text-lg font-semibold mb-3">Settlement</h2>
                    <div className="grid sm:grid-cols-3 gap-4 text-sm">
                        <div>
                            <p className="text-[var(--color-muted-foreground)]">Reference</p>
                            <p className="font-medium">{settlement.settlement_reference_id}</p>
                        </div>
                        <div>
                            <p className="text-[var(--color-muted-foreground)]">Amount</p>
                            <p className="font-semibold">{formatCurrency(settlement.amount)}</p>
                        </div>
                        <div>
                            <p className="text-[var(--color-muted-foreground)]">Status</p>
                            <ClaimStatusBadge status={settlement.status} />
                        </div>
                    </div>
                </div>
            )}

            {/* Admin Actions */}
            {isAdmin && (
                <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-6">
                    <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                        <AlertTriangle size={20} className="text-amber-500" />
                        Admin Actions
                    </h2>
                    <div className="flex flex-wrap gap-3">
                        <button
                            onClick={() => handleStatusUpdate("APPROVED")}
                            disabled={!!actionLoading}
                            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium transition-colors disabled:opacity-50"
                        >
                            {actionLoading === "APPROVED" ? (
                                <Loader2 size={14} className="animate-spin" />
                            ) : (
                                <CheckCircle2 size={14} />
                            )}
                            Approve
                        </button>
                        <button
                            onClick={() => handleStatusUpdate("REJECTED")}
                            disabled={!!actionLoading}
                            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm font-medium transition-colors disabled:opacity-50"
                        >
                            {actionLoading === "REJECTED" ? (
                                <Loader2 size={14} className="animate-spin" />
                            ) : (
                                <XCircle size={14} />
                            )}
                            Reject
                        </button>
                        <button
                            onClick={() => handleStatusUpdate("MANUAL_REVIEW_REQUIRED")}
                            disabled={!!actionLoading}
                            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-sm font-medium transition-colors disabled:opacity-50"
                        >
                            {actionLoading === "MANUAL_REVIEW_REQUIRED" ? (
                                <Loader2 size={14} className="animate-spin" />
                            ) : (
                                <AlertTriangle size={14} />
                            )}
                            Require Review
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
