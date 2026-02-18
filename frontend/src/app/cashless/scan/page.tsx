"use client";

import { useEffect, useRef, useState } from "react";
import { qrService } from "@/services/qrService";
import type { QRValidationResponse } from "@/types";
import { formatCurrency } from "@/lib/utils";
import {
    Camera,
    CheckCircle2,
    XCircle,
    Loader2,
    ScanLine,
    RefreshCw,
} from "lucide-react";

export default function ScanQRPage() {
    const videoRef = useRef<HTMLDivElement>(null);
    const scannerRef = useRef<unknown>(null);
    const [scanning, setScanning] = useState(false);
    const [result, setResult] = useState<QRValidationResponse | null>(null);
    const [validating, setValidating] = useState(false);
    const [error, setError] = useState("");

    const startScanner = async () => {
        setError("");
        setResult(null);

        try {
            const { Html5Qrcode } = await import("html5-qrcode");

            if (scannerRef.current) {
                try {
                    await (scannerRef.current as InstanceType<typeof Html5Qrcode>).stop();
                } catch {
                    // ignore
                }
            }

            const scanner = new Html5Qrcode("qr-reader");
            scannerRef.current = scanner;
            setScanning(true);

            await scanner.start(
                { facingMode: "environment" },
                { fps: 10, qrbox: { width: 250, height: 250 } },
                async (decodedText: string) => {
                    setScanning(false);
                    try {
                        await scanner.stop();
                    } catch {
                        // ignore
                    }
                    await validateToken(decodedText);
                },
                () => { }
            );
        } catch (err) {
            setError("Camera access denied or unavailable. Please grant camera permissions.");
            setScanning(false);
            console.error(err);
        }
    };

    const validateToken = async (token: string) => {
        setValidating(true);
        try {
            const res = await qrService.validate({ qr_token: token });
            setResult(res);
        } catch (err: unknown) {
            const msg =
                (err as { response?: { data?: { detail?: string } } })?.response?.data
                    ?.detail || "Validation failed";
            setResult({ valid: false, message: msg });
        } finally {
            setValidating(false);
        }
    };

    useEffect(() => {
        return () => {
            if (scannerRef.current) {
                try {
                    (scannerRef.current as { stop: () => Promise<void> }).stop();
                } catch {
                    // ignore
                }
            }
        };
    }, []);

    return (
        <div className="max-w-lg mx-auto space-y-6">
            <div>
                <h1 className="text-2xl font-bold flex items-center gap-2">
                    <ScanLine size={24} className="text-indigo-500" />
                    Scan & Approve Payment
                </h1>
                <p className="text-sm text-[var(--color-muted-foreground)]">
                    Scan the hospital&apos;s QR code to verify the authorization and process cashless payment
                </p>
            </div>

            <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-6">
                {/* Scanner area */}
                {!result && (
                    <>
                        <div
                            id="qr-reader"
                            ref={videoRef}
                            className="w-full rounded-xl overflow-hidden bg-black/5 dark:bg-black/20 min-h-[300px]"
                        />

                        {!scanning && (
                            <button
                                onClick={startScanner}
                                className="w-full mt-4 py-2.5 rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-medium text-sm transition-all flex items-center justify-center gap-2"
                            >
                                <Camera size={16} />
                                Start Camera
                            </button>
                        )}

                        {scanning && (
                            <div className="text-center mt-4">
                                <p className="text-sm text-[var(--color-muted-foreground)] flex items-center justify-center gap-2">
                                    <Loader2 size={16} className="animate-spin" />
                                    Scanning for QR code…
                                </p>
                            </div>
                        )}
                    </>
                )}

                {/* Validation in progress */}
                {validating && (
                    <div className="flex flex-col items-center justify-center py-12">
                        <Loader2 size={40} className="animate-spin text-indigo-500 mb-3" />
                        <p className="text-sm">Validating authorization…</p>
                    </div>
                )}

                {/* Result */}
                {result && !validating && (
                    <div className="text-center animate-fade-in py-6">
                        {result.valid ? (
                            <>
                                <div className="w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-950/30 flex items-center justify-center mx-auto mb-4">
                                    <CheckCircle2 size={32} className="text-emerald-500" />
                                </div>
                                <h2 className="text-xl font-bold text-emerald-600 dark:text-emerald-400">
                                    Authorization Valid
                                </h2>
                                <p className="text-sm text-[var(--color-muted-foreground)] mt-1">
                                    {result.message}
                                </p>

                                <div className="grid grid-cols-2 gap-4 text-left mt-6">
                                    <div className="p-3 rounded-lg bg-[var(--color-muted)]">
                                        <p className="text-xs text-[var(--color-muted-foreground)]">
                                            Approved Limit
                                        </p>
                                        <p className="font-bold">
                                            {formatCurrency(result.approved_limit ?? 0)}
                                        </p>
                                    </div>
                                    <div className="p-3 rounded-lg bg-[var(--color-muted)]">
                                        <p className="text-xs text-[var(--color-muted-foreground)]">
                                            Claim ID
                                        </p>
                                        <p className="font-mono text-xs font-semibold truncate">
                                            {result.claim_id}
                                        </p>
                                    </div>
                                </div>
                            </>
                        ) : (
                            <>
                                <div className="w-16 h-16 rounded-full bg-red-100 dark:bg-red-950/30 flex items-center justify-center mx-auto mb-4">
                                    <XCircle size={32} className="text-red-500" />
                                </div>
                                <h2 className="text-xl font-bold text-red-600 dark:text-red-400">
                                    Authorization Invalid
                                </h2>
                                <p className="text-sm text-[var(--color-muted-foreground)] mt-1">
                                    {result.message}
                                </p>
                            </>
                        )}

                        <button
                            onClick={() => {
                                setResult(null);
                                startScanner();
                            }}
                            className="mt-6 flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--color-muted)] hover:bg-[var(--color-border)] transition-colors text-sm font-medium mx-auto"
                        >
                            <RefreshCw size={14} />
                            Scan Another
                        </button>
                    </div>
                )}

                {error && (
                    <div className="mt-4 px-4 py-3 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm">
                        {error}
                    </div>
                )}
            </div>
        </div>
    );
}
