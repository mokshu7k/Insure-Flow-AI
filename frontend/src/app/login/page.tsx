"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { AuthLayout, FormError, FieldLabel } from "@/components/layout/PublicLayout";

export default function LoginPage() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [showPass, setShowPass] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const { login, isLoading } = useAuthStore();
    const router = useRouter();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        console.log("[Login] Submitting for", email);
        setError(null);
        try {
            await login(email, password);
            console.log("[Login] ✅ Success — redirecting to /dashboard");
            router.push("/dashboard");
        } catch (err: unknown) {
            const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
            const msg = detail || (err instanceof Error ? err.message : "Invalid credentials");
            console.error("[Login] Failed:", msg);
            setError(msg);
        }
    };

    return (
        <AuthLayout title="Sign in to your portal">
            <h1 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 24 }}>Sign in</h1>

            <FormError message={error} />

            <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <div>
                    <FieldLabel>Email</FieldLabel>
                    <input
                        className="input"
                        type="email"
                        autoComplete="email"
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="you@insureflow.ai"
                    />
                </div>

                <div>
                    <FieldLabel>Password</FieldLabel>
                    <div style={{ position: "relative" }}>
                        <input
                            className="input"
                            type={showPass ? "text" : "password"}
                            autoComplete="current-password"
                            required
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="••••••••"
                            style={{ paddingRight: 40 }}
                        />
                        <button
                            type="button"
                            onClick={() => setShowPass(!showPass)}
                            style={{
                                position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)",
                                background: "none", border: "none", cursor: "pointer", color: "var(--text-muted)",
                                display: "flex", alignItems: "center",
                            }}
                        >
                            {showPass ? <EyeOff size={14} /> : <Eye size={14} />}
                        </button>
                    </div>
                </div>

                <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={isLoading}
                    style={{ marginTop: 6, justifyContent: "center", gap: 8 }}
                >
                    {isLoading
                        ? <><Loader2 size={14} className="animate-spin" /> Signing in…</>
                        : "Sign in"
                    }
                </button>
            </form>

            <div style={{ marginTop: 24, paddingTop: 16, borderTop: "1px solid var(--border)", textAlign: "center" }}>
                <span style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>No account? </span>
                <a href="/register" style={{ fontSize: "0.8125rem", color: "var(--blue)", textDecoration: "none" }}>
                    Create one
                </a>
            </div>
        </AuthLayout>
    );
}
