"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { claimService } from "@/services/claimService";
import { Loader2, FileText } from "lucide-react";

const schema = z.object({
    policy_number: z.string().min(5, "Minimum 5 characters").max(100),
    claim_type: z.enum(["HEALTH", "MOTOR", "REIMBURSEMENT"], {
        required_error: "Select a claim type",
    }),
    claim_amount: z.coerce.number().positive("Amount must be positive"),
});

type FormData = z.infer<typeof schema>;

export default function NewClaimPage() {
    const router = useRouter();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const {
        register,
        handleSubmit,
        formState: { errors },
    } = useForm<FormData>({
        resolver: zodResolver(schema),
    });

    const onSubmit = async (data: FormData) => {
        setError("");
        setLoading(true);
        try {
            const claim = await claimService.create(data);
            router.push(`/claims/${claim.id}`);
        } catch (err: unknown) {
            const msg =
                (err as { response?: { data?: { detail?: string } } })?.response?.data
                    ?.detail || "Failed to create claim";
            setError(msg);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="max-w-2xl mx-auto space-y-6">
            <div>
                <h1 className="text-2xl font-bold">Submit New Claim</h1>
                <p className="text-sm text-[var(--color-muted-foreground)]">
                    Fill in the details to submit a new insurance claim
                </p>
            </div>

            <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-6">
                {error && (
                    <div className="mb-4 px-4 py-3 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm">
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
                    <div>
                        <label className="block text-sm font-medium mb-1.5">
                            Policy Number
                        </label>
                        <input
                            {...register("policy_number")}
                            placeholder="e.g. POL-2026-001234"
                            className="w-full px-3 py-2.5 rounded-lg border border-[var(--color-input)] bg-transparent text-sm outline-none focus:ring-2 focus:ring-[var(--color-ring)] focus:border-transparent transition-shadow"
                        />
                        {errors.policy_number && (
                            <p className="text-xs text-red-500 mt-1">
                                {errors.policy_number.message}
                            </p>
                        )}
                    </div>

                    <div>
                        <label className="block text-sm font-medium mb-1.5">
                            Claim Type
                        </label>
                        <select
                            {...register("claim_type")}
                            className="w-full px-3 py-2.5 rounded-lg border border-[var(--color-input)] bg-[var(--color-card)] text-sm outline-none focus:ring-2 focus:ring-[var(--color-ring)] focus:border-transparent transition-shadow"
                        >
                            <option value="">Select type…</option>
                            <option value="HEALTH">Health</option>
                            <option value="MOTOR">Motor</option>
                            <option value="REIMBURSEMENT">Reimbursement</option>
                        </select>
                        {errors.claim_type && (
                            <p className="text-xs text-red-500 mt-1">
                                {errors.claim_type.message}
                            </p>
                        )}
                    </div>

                    <div>
                        <label className="block text-sm font-medium mb-1.5">
                            Claim Amount (₹)
                        </label>
                        <input
                            {...register("claim_amount")}
                            type="number"
                            step="0.01"
                            placeholder="50000"
                            className="w-full px-3 py-2.5 rounded-lg border border-[var(--color-input)] bg-transparent text-sm outline-none focus:ring-2 focus:ring-[var(--color-ring)] focus:border-transparent transition-shadow"
                        />
                        {errors.claim_amount && (
                            <p className="text-xs text-red-500 mt-1">
                                {errors.claim_amount.message}
                            </p>
                        )}
                    </div>

                    {/* Consent notice */}
                    <div className="p-4 rounded-lg bg-indigo-50 dark:bg-indigo-950/20 border border-indigo-100 dark:border-indigo-900/30">
                        <div className="flex gap-3">
                            <FileText size={18} className="text-indigo-500 shrink-0 mt-0.5" />
                            <div>
                                <p className="text-sm font-medium text-indigo-700 dark:text-indigo-300">
                                    Consent Required
                                </p>
                                <p className="text-xs text-indigo-600/70 dark:text-indigo-400/70 mt-1">
                                    By submitting this claim, you consent to AI-assisted fraud
                                    analysis and data processing as per DPDP regulations.
                                </p>
                            </div>
                        </div>
                    </div>

                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full py-2.5 rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-medium text-sm transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                    >
                        {loading && <Loader2 size={16} className="animate-spin" />}
                        {loading ? "Submitting…" : "Submit Claim"}
                    </button>
                </form>
            </div>
        </div>
    );
}
