"use client";
import { useEffect, useState } from "react";
import { useAuthStore } from "@/store/authStore";
import cashlessService from "@/services/cashlessService";
import type {
    CashlessQRRequest,
    CashlessQRResponse,
    CashlessScanResponse,
    CashlessPendingItem,
    NetworkClaimItem,
} from "@/types";

/* ──────────────────────────────  PROVIDER VIEW  ────────────────────────────── */
function ProviderCashless() {
    const [claims, setClaims] = useState<NetworkClaimItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedClaim, setSelectedClaim] = useState<NetworkClaimItem | null>(null);
    const [form, setForm] = useState({ patient_name: "", estimate_amount: "", procedure_name: "", hospital_name: "", diagnosis: "" });
    const [qrResult, setQrResult] = useState<CashlessQRResponse | null>(null);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
        cashlessService.getNetworkClaims()
            .then((r) => setClaims(r.items))
            .catch(() => setError("Failed to load network claims"))
            .finally(() => setLoading(false));
    }, []);

    const handleGenerate = async () => {
        if (!selectedClaim) return;
        setSubmitting(true);
        setError("");
        try {
            const payload: CashlessQRRequest = {
                claim_id: selectedClaim.id,
                estimate_amount: parseFloat(form.estimate_amount),
                patient_name: form.patient_name,
                procedure_name: form.procedure_name,
                hospital_name: form.hospital_name,
                estimate_data: form.diagnosis ? { diagnosis: form.diagnosis } : undefined,
            };
            const res = await cashlessService.generateQR(payload);
            setQrResult(res);
        } catch (e: unknown) {
            const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to generate QR";
            setError(msg);
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) return <div style={{ padding: 32 }}>Loading network claims…</div>;

    return (
        <div style={{ display: "flex", gap: 24, height: "100%" }}>
            {/* Left — Claim list */}
            <div style={{ flex: "0 0 340px", overflowY: "auto", borderRight: "1px solid var(--border)", padding: "16px 16px 16px 0" }}>
                <h3 style={{ fontSize: "0.875rem", fontWeight: 600, marginBottom: 12, color: "var(--text-secondary)" }}>
                    Network Cashless Claims ({claims.length})
                </h3>
                {claims.length === 0 && <p style={{ color: "var(--text-muted)", fontSize: "0.8125rem" }}>No cashless claims assigned to you.</p>}
                {claims.map((c) => (
                    <div key={c.id} onClick={() => { setSelectedClaim(c); setQrResult(null); setError(""); }}
                        style={{
                            padding: "10px 12px", marginBottom: 6, borderRadius: 6, cursor: "pointer",
                            background: selectedClaim?.id === c.id ? "var(--bg-surface)" : "transparent",
                            border: selectedClaim?.id === c.id ? "1px solid var(--blue-border)" : "1px solid var(--border)",
                        }}>
                        <div style={{ fontWeight: 500, fontSize: "0.8125rem" }}>{c.policy_number}</div>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                            {c.status} · {c.has_qr ? "QR issued" : "No QR yet"}
                            {c.claim_amount ? ` · ₹${c.claim_amount.toLocaleString()}` : ""}
                        </div>
                    </div>
                ))}
            </div>

            {/* Right — Generate form / QR result */}
            <div style={{ flex: 1, padding: "16px 0", overflowY: "auto" }}>
                {!selectedClaim && <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>Select a claim to generate a QR code.</p>}
                {selectedClaim && !qrResult && (
                    <div style={{ maxWidth: 480 }}>
                        <h3 style={{ fontSize: "0.875rem", fontWeight: 600, marginBottom: 16 }}>
                            Generate QR — {selectedClaim.policy_number}
                        </h3>
                        {error && <div style={{ color: "var(--red)", marginBottom: 12, fontSize: "0.8125rem" }}>{error}</div>}
                        {[
                            { label: "Patient Name", key: "patient_name", type: "text" },
                            { label: "Estimate Amount (₹)", key: "estimate_amount", type: "number" },
                            { label: "Procedure Name", key: "procedure_name", type: "text" },
                            { label: "Hospital Name", key: "hospital_name", type: "text" },
                            { label: "Diagnosis / Notes", key: "diagnosis", type: "text" },
                        ].map(({ label, key, type }) => (
                            <div key={key} style={{ marginBottom: 12 }}>
                                <label style={{ fontSize: "0.75rem", color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>{label}</label>
                                <input type={type} value={(form as Record<string, string>)[key]}
                                    onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                                    style={{
                                        width: "100%", padding: "8px 10px", borderRadius: 6,
                                        border: "1px solid var(--border)", background: "var(--bg-surface)",
                                        color: "var(--text-primary)", fontSize: "0.8125rem",
                                    }} />
                            </div>
                        ))}
                        <button onClick={handleGenerate} disabled={submitting || !form.patient_name || !form.estimate_amount || !form.procedure_name || !form.hospital_name}
                            style={{
                                padding: "8px 20px", borderRadius: 6, background: "var(--blue)", color: "#fff",
                                border: "none", cursor: "pointer", fontSize: "0.8125rem", fontWeight: 500,
                                opacity: submitting ? 0.6 : 1,
                            }}>
                            {submitting ? "Generating…" : "Generate QR Code"}
                        </button>
                    </div>
                )}
                {qrResult && (
                    <div style={{ textAlign: "center", maxWidth: 400, margin: "0 auto" }}>
                        <h3 style={{ fontSize: "0.875rem", fontWeight: 600, marginBottom: 16, color: "var(--green)" }}>QR Code Generated</h3>
                        <img src={`data:image/png;base64,${qrResult.qr_image_base64}`} alt="Cashless QR"
                            style={{ width: 240, height: 240, borderRadius: 8, border: "1px solid var(--border)", margin: "0 auto 16px" }} />
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: 8 }}>Token (share with patient):</div>
                        <div style={{
                            padding: "8px 12px", background: "var(--bg-surface)", borderRadius: 6,
                            fontFamily: "var(--font-mono)", fontSize: "0.75rem", wordBreak: "break-all",
                            border: "1px solid var(--border)", cursor: "pointer", marginBottom: 12,
                        }}
                            onClick={() => { navigator.clipboard.writeText(qrResult.token); }}>
                            {qrResult.token}
                            <span style={{ display: "block", fontSize: "0.625rem", color: "var(--text-muted)", marginTop: 4 }}>Click to copy</span>
                        </div>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                            Expires: {new Date(qrResult.expires_at).toLocaleString()}
                        </div>
                        <button onClick={() => { setQrResult(null); setSelectedClaim(null); setForm({ patient_name: "", estimate_amount: "", procedure_name: "", hospital_name: "", diagnosis: "" }); }}
                            style={{ marginTop: 16, padding: "6px 16px", borderRadius: 6, background: "var(--bg-surface)", border: "1px solid var(--border)", cursor: "pointer", fontSize: "0.8125rem" }}>
                            Done
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}

/* ──────────────────────────────  CUSTOMER VIEW  ────────────────────────────── */
function CustomerCashless() {
    const [token, setToken] = useState("");
    const [scanResult, setScanResult] = useState<CashlessScanResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [accepting, setAccepting] = useState(false);
    const [message, setMessage] = useState("");
    const [error, setError] = useState("");

    const handleScan = async () => {
        setLoading(true);
        setError("");
        setScanResult(null);
        setMessage("");
        try {
            const res = await cashlessService.scanQR(token.trim());
            setScanResult(res);
        } catch (e: unknown) {
            setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Invalid or expired QR token");
        } finally {
            setLoading(false);
        }
    };

    const handleAccept = async () => {
        setAccepting(true);
        setError("");
        try {
            const res = await cashlessService.acceptEstimate({ token: token.trim() });
            setMessage(res.message);
            setScanResult(null);
        } catch (e: unknown) {
            setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to accept estimate");
        } finally {
            setAccepting(false);
        }
    };

    return (
        <div style={{ maxWidth: 520, margin: "0 auto", padding: "24px 0" }}>
            <h3 style={{ fontSize: "0.875rem", fontWeight: 600, marginBottom: 16 }}>Scan Cashless QR</h3>
            <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
                <input placeholder="Paste QR token here…" value={token} onChange={(e) => setToken(e.target.value)}
                    style={{
                        flex: 1, padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)",
                        background: "var(--bg-surface)", color: "var(--text-primary)", fontSize: "0.8125rem",
                    }} />
                <button onClick={handleScan} disabled={loading || !token.trim()}
                    style={{
                        padding: "8px 16px", borderRadius: 6, background: "var(--blue)", color: "#fff",
                        border: "none", cursor: "pointer", fontSize: "0.8125rem", fontWeight: 500,
                        opacity: loading ? 0.6 : 1,
                    }}>
                    {loading ? "Scanning…" : "Scan"}
                </button>
            </div>
            {error && <div style={{ color: "var(--red)", fontSize: "0.8125rem", marginBottom: 12 }}>{error}</div>}
            {message && <div style={{ color: "var(--green)", fontSize: "0.8125rem", marginBottom: 12, fontWeight: 500 }}>{message}</div>}
            {scanResult && (
                <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: 8, padding: 20 }}>
                    <h4 style={{ fontSize: "0.8125rem", fontWeight: 600, marginBottom: 12 }}>Estimate Details</h4>
                    {[
                        ["Policy Number", scanResult.policy_number],
                        ["Claim Type", scanResult.claim_type],
                        ["Patient Name", scanResult.patient_name],
                        ["Procedure", scanResult.procedure_name],
                        ["Hospital", scanResult.hospital_name],
                        ["Status", scanResult.status],
                        ["Expires", new Date(scanResult.expires_at).toLocaleString()],
                    ].map(([k, v]) => (
                        <div key={k} style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: "0.8125rem" }}>
                            <span style={{ color: "var(--text-secondary)" }}>{k}</span>
                            <span style={{ fontWeight: 500 }}>{v || "—"}</span>
                        </div>
                    ))}
                    <div style={{
                        display: "flex", justifyContent: "space-between", padding: "10px 0", marginTop: 8,
                        borderTop: "1px solid var(--border)", fontSize: "0.9375rem", fontWeight: 600,
                    }}>
                        <span>Estimate Amount</span>
                        <span style={{ color: "var(--blue)" }}>₹{scanResult.estimate_amount.toLocaleString()}</span>
                    </div>
                    {scanResult.estimate_data && Object.keys(scanResult.estimate_data).length > 0 && (
                        <div style={{ marginTop: 10, fontSize: "0.75rem", color: "var(--text-muted)" }}>
                            <strong>Additional Info:</strong>
                            <pre style={{ marginTop: 4, whiteSpace: "pre-wrap", fontFamily: "var(--font-mono)" }}>
                                {JSON.stringify(scanResult.estimate_data, null, 2)}
                            </pre>
                        </div>
                    )}
                    <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
                        <button onClick={handleAccept} disabled={accepting}
                            style={{
                                flex: 1, padding: "8px 0", borderRadius: 6, background: "var(--green)", color: "#fff",
                                border: "none", cursor: "pointer", fontSize: "0.8125rem", fontWeight: 500,
                                opacity: accepting ? 0.6 : 1,
                            }}>
                            {accepting ? "Accepting…" : "Accept Estimate"}
                        </button>
                        <button onClick={() => { setScanResult(null); setToken(""); }}
                            style={{
                                flex: 1, padding: "8px 0", borderRadius: 6, background: "transparent",
                                border: "1px solid var(--border)", cursor: "pointer", fontSize: "0.8125rem",
                                color: "var(--text-secondary)",
                            }}>
                            Decline
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}

/* ──────────────────────────────  INSURER VIEW  ─────────────────────────────── */
function InsurerCashless() {
    const [items, setItems] = useState<CashlessPendingItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [processing, setProcessing] = useState<string | null>(null);
    const [adjustments, setAdjustments] = useState<Record<string, { amount: string; notes: string }>>({});
    const [error, setError] = useState("");

    const loadItems = () => {
        setLoading(true);
        cashlessService.getPendingAuthorizations()
            .then((data) => { setItems(data); setError(""); })
            .catch(() => setError("Failed to load pending authorizations"))
            .finally(() => setLoading(false));
    };

    useEffect(() => { loadItems(); }, []);

    const handleDecision = async (item: CashlessPendingItem, decision: "PRE_AUTHORIZED" | "REJECTED") => {
        setProcessing(item.qr_token_id);
        setError("");
        try {
            const adj = adjustments[item.qr_token_id];
            await cashlessService.preAuthorize({
                qr_token_id: item.qr_token_id,
                decision,
                approved_amount: adj?.amount ? parseFloat(adj.amount) : undefined,
                notes: adj?.notes || undefined,
            });
            loadItems();
        } catch (e: unknown) {
            setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Action failed");
        } finally {
            setProcessing(null);
        }
    };

    if (loading) return <div style={{ padding: 32 }}>Loading pending authorizations…</div>;

    return (
        <div style={{ padding: "16px 0" }}>
            <h3 style={{ fontSize: "0.875rem", fontWeight: 600, marginBottom: 16 }}>
                Pending Cashless Authorizations ({items.length})
            </h3>
            {error && <div style={{ color: "var(--red)", fontSize: "0.8125rem", marginBottom: 12 }}>{error}</div>}
            {items.length === 0 && <p style={{ color: "var(--text-muted)", fontSize: "0.8125rem" }}>No pending cashless authorizations.</p>}
            {items.map((item) => {
                const adj = adjustments[item.qr_token_id] || { amount: "", notes: "" };
                return (
                    <div key={item.qr_token_id} style={{
                        background: "var(--bg-surface)", border: "1px solid var(--border)",
                        borderRadius: 8, padding: 16, marginBottom: 12,
                    }}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                            <div>
                                <div style={{ fontWeight: 600, fontSize: "0.8125rem" }}>{item.patient_name || "Unknown"}</div>
                                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                                    {item.policy_number} · {item.procedure_name} · {item.hospital_name}
                                </div>
                            </div>
                            <div style={{ fontWeight: 600, fontSize: "0.9375rem", color: "var(--blue)" }}>
                                ₹{item.estimate_amount.toLocaleString()}
                            </div>
                        </div>
                        <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
                            <input placeholder="Adjusted amount (optional)" value={adj.amount}
                                onChange={(e) => setAdjustments((a) => ({ ...a, [item.qr_token_id]: { ...adj, amount: e.target.value } }))}
                                type="number"
                                style={{
                                    flex: 1, padding: "6px 10px", borderRadius: 6, border: "1px solid var(--border)",
                                    background: "var(--bg-panel)", fontSize: "0.8125rem", color: "var(--text-primary)",
                                }} />
                            <input placeholder="Notes (optional)" value={adj.notes}
                                onChange={(e) => setAdjustments((a) => ({ ...a, [item.qr_token_id]: { ...adj, notes: e.target.value } }))}
                                style={{
                                    flex: 2, padding: "6px 10px", borderRadius: 6, border: "1px solid var(--border)",
                                    background: "var(--bg-panel)", fontSize: "0.8125rem", color: "var(--text-primary)",
                                }} />
                        </div>
                        <div style={{ display: "flex", gap: 8 }}>
                            <button onClick={() => handleDecision(item, "PRE_AUTHORIZED")}
                                disabled={processing === item.qr_token_id}
                                style={{
                                    padding: "6px 16px", borderRadius: 6, background: "var(--green)", color: "#fff",
                                    border: "none", cursor: "pointer", fontSize: "0.8125rem", fontWeight: 500,
                                    opacity: processing === item.qr_token_id ? 0.6 : 1,
                                }}>
                                Pre-Authorize
                            </button>
                            <button onClick={() => handleDecision(item, "REJECTED")}
                                disabled={processing === item.qr_token_id}
                                style={{
                                    padding: "6px 16px", borderRadius: 6, background: "var(--red)", color: "#fff",
                                    border: "none", cursor: "pointer", fontSize: "0.8125rem", fontWeight: 500,
                                    opacity: processing === item.qr_token_id ? 0.6 : 1,
                                }}>
                                Reject
                            </button>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

/* ──────────────────────────────  MAIN PAGE  ────────────────────────────────── */
export default function CashlessPage() {
    const { user } = useAuthStore();

    if (!user) return <div style={{ padding: 32, color: "var(--text-muted)" }}>Please log in to access cashless claims.</div>;

    return (
        <div style={{ padding: "24px 28px", height: "100%", overflowY: "auto" }}>
            <h2 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: 4 }}>Cashless Claims</h2>
            <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: 20 }}>
                {user.role === "PROVIDER" && "Generate QR codes for cashless authorization"}
                {user.role === "CUSTOMER" && "Scan and accept hospital estimate QR codes"}
                {user.role === "INSURER_ADMIN" && "Review and pre-authorize cashless claims"}
                {!["PROVIDER", "CUSTOMER", "INSURER_ADMIN"].includes(user.role) && "Cashless claim management"}
            </p>
            {user.role === "PROVIDER" && <ProviderCashless />}
            {user.role === "CUSTOMER" && <CustomerCashless />}
            {user.role === "INSURER_ADMIN" && <InsurerCashless />}
            {!["PROVIDER", "CUSTOMER", "INSURER_ADMIN"].includes(user.role) && (
                <div style={{ color: "var(--text-muted)", fontSize: "0.8125rem" }}>
                    Cashless claims are managed by Providers, Customers, and Insurer Admins.
                </div>
            )}
        </div>
    );
}
