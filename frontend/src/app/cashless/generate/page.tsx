"use client";

import { useState } from "react";
import { useForm, Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { qrService } from "@/services/qrService";
import type { QRAuthorizationResponse } from "@/types";
import { QRCodeSVG } from "qrcode.react";
import { Loader2, QrCode, CheckCircle2, Clock, Shield } from "lucide-react";
import { formatCurrency, formatDateTime } from "@/lib/utils";

const schema = z.object({
    claim_id: z.string().min(1, "Claim ID is required"),
    provider_id: z.string().min(1, "Provider ID is required"),
    approved_limit: z.coerce.number().positive("Must be positive"),
    expiry_minutes: z.coerce.number().min(5).max(1440).default(30),
});

type FormData = {
    claim_id: string;
    provider_id: string;
    approved_limit: number;
    expiry_minutes: number;
};

export default function GenerateQRPage() {
    const [result, setResult] = useState<QRAuthorizationResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const {
        register,
        handleSubmit,
        formState: { errors },
    } = useForm<FormData>({
        resolver: zodResolver(schema) as unknown as Resolver<FormData>,
        defaultValues: { expiry_minutes: 30 },
    });

    const onSubmit = async (data: FormData) => {
        setError("");
        setLoading(true);
        try {
            const res = await qrService.createAuthorization(data);
            setResult(res);
        } catch (err: unknown) {
            const msg =
                (err as { response?: { data?: { detail?: string } } })?.response?.data
                    ?.detail || "Failed to generate QR";
            setError(msg);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="max-w-2xl mx-auto space-y-6">
            <div>
                <h1 className="text-2xl font-bold flex items-center gap-2">
                    <QrCode size={24} className="text-indigo-500" />
                    Generate Cashless QR
                </h1>
                <p className="text-sm text-[var(--color-muted-foreground)]">
                    Create a signed, time-limited QR code for the insurer to scan and process payment
                </p>
            </div>

            {!result ? (
                <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-6">
                    {error && (
                        <div className="mb-4 px-4 py-3 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm">
                            {error}
                        </div>
                    )}

                    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
                        <div>
                            <label className="block text-sm font-medium mb-1.5">
                                Claim ID
                            </label>
                            <input
                                {...register("claim_id")}
                                placeholder="Claim UUID"
                                className="w-full px-3 py-2.5 rounded-lg border border-[var(--color-input)] bg-transparent text-sm outline-none focus:ring-2 focus:ring-[var(--color-ring)] focus:border-transparent transition-shadow"
                            />
                            {errors.claim_id && (
                                <p className="text-xs text-red-500 mt-1">
                                    {errors.claim_id.message}
                                </p>
                            )}
                        </div>

                        <div>
                            <label className="block text-sm font-medium mb-1.5">
                                Provider ID
                            </label>
                            <input
                                {...register("provider_id")}
                                placeholder="Provider UUID"
                                className="w-full px-3 py-2.5 rounded-lg border border-[var(--color-input)] bg-transparent text-sm outline-none focus:ring-2 focus:ring-[var(--color-ring)] focus:border-transparent transition-shadow"
                            />
                            {errors.provider_id && (
                                <p className="text-xs text-red-500 mt-1">
                                    {errors.provider_id.message}
                                </p>
                            )}
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm font-medium mb-1.5">
                                    Approved Limit (₹)
                                </label>
                                <input
                                    {...register("approved_limit")}
                                    type="number"
                                    step="0.01"
                                    className="w-full px-3 py-2.5 rounded-lg border border-[var(--color-input)] bg-transparent text-sm outline-none focus:ring-2 focus:ring-[var(--color-ring)] focus:border-transparent transition-shadow"
                                />
                                {errors.approved_limit && (
                                    <p className="text-xs text-red-500 mt-1">
                                        {errors.approved_limit.message}
                                    </p>
                                )}
                            </div>
                            <div>
                                <label className="block text-sm font-medium mb-1.5">
                                    Expiry (min)
                                </label>
                                <input
                                    {...register("expiry_minutes")}
                                    type="number"
                                    className="w-full px-3 py-2.5 rounded-lg border border-[var(--color-input)] bg-transparent text-sm outline-none focus:ring-2 focus:ring-[var(--color-ring)] focus:border-transparent transition-shadow"
                                />
                                {errors.expiry_minutes && (
                                    <p className="text-xs text-red-500 mt-1">
                                        {errors.expiry_minutes.message}
                                    </p>
                                )}
                            </div>
                        </div>

                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full py-2.5 rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-medium text-sm transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                        >
                            {loading && <Loader2 size={16} className="animate-spin" />}
                            {loading ? "Generating…" : "Generate QR Code"}
                        </button>
                    </form>
                </div>
            ) : (
                <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-6 animate-fade-in">
                    <div className="text-center">
                        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-50 dark:bg-emerald-950/30 text-emerald-600 dark:text-emerald-300 text-sm font-medium mb-6">
                            <CheckCircle2 size={16} />
                            Authorization Created
                        </div>

                        {/* QR Code */}
                        <div className="inline-block p-6 bg-white rounded-2xl shadow-lg mb-6">
                            <QRCodeSVG value={result.qr_token} size={200} level="H" />
                        </div>

                        {/* Details */}
                        <div className="grid sm:grid-cols-2 gap-4 text-left max-w-md mx-auto">
                            <div className="p-3 rounded-lg bg-[var(--color-muted)]">
                                <p className="text-xs text-[var(--color-muted-foreground)] flex items-center gap-1">
                                    <Shield size={12} /> Approved Limit
                                </p>
                                <p className="font-semibold">
                                    {formatCurrency(result.approved_limit)}
                                </p>
                            </div>
                            <div className="p-3 rounded-lg bg-[var(--color-muted)]">
                                <p className="text-xs text-[var(--color-muted-foreground)] flex items-center gap-1">
                                    <Clock size={12} /> Expires At
                                </p>
                                <p className="font-semibold text-sm">
                                    {formatDateTime(result.expires_at)}
                                </p>
                            </div>
                        </div>

                        <button
                            onClick={() => setResult(null)}
                            className="mt-6 px-4 py-2 text-sm text-[var(--color-primary)] font-medium hover:underline"
                        >
                            Generate Another
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
