"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { AuthLayout, FormError, FormSuccess, FieldLabel } from "@/components/layout/PublicLayout";
import type { UserRole } from "@/types";

const ROLES: { value: UserRole; label: string; desc: string }[] = [
    { value: "CUSTOMER", label: "Policyholder / Customer", desc: "Submit and track your own insurance claims" },
    { value: "PROVIDER", label: "Healthcare / Service Provider", desc: "Upload documents and view claims for your facility" },
    { value: "INSURER_ADMIN", label: "Insurer Admin", desc: "Full admin — fraud analysis, approvals, dashboard" },
    { value: "AUDITOR", label: "Compliance Auditor", desc: "Read-only access to audit trails and compliance logs" },
];

export default function RegisterPage() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [role, setRole] = useState<UserRole>("CUSTOMER");
    const [acceptedTerms, setAcceptedTerms] = useState(false);
    const [acceptedPrivacy, setAcceptedPrivacy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const router = useRouter();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        console.log("[Register] Submit →", { email, role, pwLen: password.length });

        if (password.length < 8) { setError("Password must be at least 8 characters."); return; }
        if (!acceptedTerms) { setError("You must accept the Terms & Conditions to register."); return; }
        if (!acceptedPrivacy) { setError("You must accept the Privacy Policy to register."); return; }
        setError(null);
        setLoading(true);

        try {
            const res = await fetch("/api/auth/register", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, password, role, consent_accepted: true }),
            });
            const data = await res.json();
            console.log("[Register] Response", res.status, data);

            if (!res.ok) {
                setError(data?.detail || data?.message || `Error ${res.status}`);
                return;
            }
            setSuccess("Account created! Redirecting to sign in…");
            setTimeout(() => router.push("/login"), 1400);
        } catch (err) {
            const msg = err instanceof Error ? err.message : "Network error — is the backend running?";
            console.error("[Register] Error:", err);
            setError(msg);
        } finally {
            setLoading(false);
        }
    };

    return (
        <AuthLayout title="Create your account">
            <h1 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 24 }}>Create account</h1>

            <FormSuccess message={success} />
            <FormError message={error} />

            <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {/* Email */}
                <div>
                    <FieldLabel>Email</FieldLabel>
                    <input
                        className="input" type="email" required autoComplete="email"
                        value={email} onChange={(e) => setEmail(e.target.value)}
                        placeholder="you@example.com"
                    />
                </div>

                {/* Password */}
                <div>
                    <FieldLabel>Password</FieldLabel>
                    <input
                        className="input" type="password" required autoComplete="new-password"
                        value={password} onChange={(e) => setPassword(e.target.value)}
                        placeholder="Minimum 8 characters"
                    />
                </div>

                {/* Role */}
                <div>
                    <FieldLabel>Account type</FieldLabel>
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                        {ROLES.map((r) => (
                            <label key={r.value} style={{
                                display: "flex", gap: 10, alignItems: "flex-start",
                                cursor: "pointer", padding: "10px 12px", borderRadius: 4,
                                border: `1px solid ${role === r.value ? "var(--blue-border)" : "var(--border)"}`,
                                background: role === r.value ? "var(--blue-bg)" : "transparent",
                                transition: "all 0.15s",
                            }}>
                                <input
                                    type="radio" name="role" value={r.value}
                                    checked={role === r.value}
                                    onChange={() => setRole(r.value)}
                                    style={{ marginTop: 2 }}
                                />
                                <div>
                                    <div style={{ fontSize: "0.8125rem", fontWeight: 500 }}>{r.label}</div>
                                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{r.desc}</div>
                                </div>
                            </label>
                        ))}
                    </div>
                </div>

                {/* Consent checkboxes — DPDP Act Section 6 */}
                <div
                    style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 10,
                        padding: "12px 14px",
                        background: "var(--bg-surface)",
                        border: "1px solid var(--border)",
                        borderRadius: 4,
                    }}
                >
                    <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: 2 }}>
                        Required consents (DPDP Act, 2023)
                    </p>

                    <label
                        style={{
                            display: "flex",
                            alignItems: "flex-start",
                            gap: 8,
                            cursor: "pointer",
                            fontSize: "0.8125rem",
                            color: "var(--text-secondary)",
                        }}
                    >
                        <input
                            type="checkbox"
                            checked={acceptedTerms}
                            onChange={(e) => setAcceptedTerms(e.target.checked)}
                            style={{ marginTop: 2, accentColor: "var(--blue)", flexShrink: 0 }}
                        />
                        <span>
                            I have read and accept the{" "}
                            <a
                                href="/terms"
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{ color: "var(--blue)", textDecoration: "underline" }}
                            >
                                Terms &amp; Conditions
                            </a>
                            , including the purposes for which my personal data will be
                            processed.
                        </span>
                    </label>

                    <label
                        style={{
                            display: "flex",
                            alignItems: "flex-start",
                            gap: 8,
                            cursor: "pointer",
                            fontSize: "0.8125rem",
                            color: "var(--text-secondary)",
                        }}
                    >
                        <input
                            type="checkbox"
                            checked={acceptedPrivacy}
                            onChange={(e) => setAcceptedPrivacy(e.target.checked)}
                            style={{ marginTop: 2, accentColor: "var(--blue)", flexShrink: 0 }}
                        />
                        <span>
                            I have read and accept the{" "}
                            <a
                                href="/privacy"
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{ color: "var(--blue)", textDecoration: "underline" }}
                            >
                                Privacy Policy
                            </a>
                            , including collection of health and financial data for
                            claim processing.
                        </span>
                    </label>
                </div>

                <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={loading || !!success || !acceptedTerms || !acceptedPrivacy}
                    style={{ marginTop: 6, justifyContent: "center", gap: 8 }}>
                    {loading
                        ? <><Loader2 size={14} className="animate-spin" /> Creating account…</>
                        : "Create account"
                    }
                </button>
            </form>

            <div style={{ marginTop: 24, paddingTop: 16, borderTop: "1px solid var(--border)", textAlign: "center" }}>
                <span style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>Have an account? </span>
                <a href="/login" style={{ fontSize: "0.8125rem", color: "var(--blue)", textDecoration: "none" }}>Sign in</a>
            </div>
        </AuthLayout>
    );
}
