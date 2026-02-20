import Link from "next/link";
import { AlertTriangle } from "lucide-react";

/**
 * Shared top nav for all public-facing pages (homepage, login, register).
 * Always identical across pages — logo left, Sign in + Get started right.
 */
export function Navbar() {
    return (
        <nav style={{
            position: "sticky", top: 0, zIndex: 50,
            background: "rgba(13,14,17,0.92)", backdropFilter: "blur(12px)",
            borderBottom: "1px solid var(--border)",
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "0 32px", height: 52,
        }}>
            {/* Logo */}
            <Link href="/" style={{ display: "flex", alignItems: "center", gap: 8, textDecoration: "none" }}>
                <AlertTriangle size={16} color="var(--amber)" />
                <span style={{ fontWeight: 700, fontSize: "0.9375rem", color: "var(--text-primary)" }}>InsureFlow</span>
                <span style={{
                    fontFamily: "var(--font-mono)", fontSize: "0.5625rem",
                    color: "var(--text-muted)", background: "var(--bg-surface)",
                    border: "1px solid var(--border)", borderRadius: 3,
                    padding: "2px 5px", letterSpacing: "0.06em", textTransform: "uppercase",
                }}>
                    CLAIM INTEL
                </span>
            </Link>

            {/* Actions */}
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Link href="/login" style={{
                    padding: "5px 14px", fontSize: "0.8125rem",
                    color: "var(--text-secondary)", textDecoration: "none",
                    border: "1px solid var(--border)", borderRadius: 4,
                }}>
                    Sign in
                </Link>
                <Link href="/register" style={{
                    padding: "5px 16px", fontSize: "0.8125rem",
                    background: "var(--blue)", color: "#fff", textDecoration: "none",
                    borderRadius: 4, fontWeight: 500,
                }}>
                    Get started
                </Link>
            </div>
        </nav>
    );
}

/** Logo mark used inside auth cards */
export function LogoMark({ subtitle }: { subtitle?: string }) {
    return (
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 32 }}>
            <AlertTriangle size={18} color="var(--amber)" />
            <div>
                <div style={{ fontWeight: 700, fontSize: "0.9375rem", letterSpacing: "0.01em" }}>InsureFlow</div>
                <div style={{
                    fontSize: "0.625rem", color: "var(--text-muted)",
                    fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.08em",
                }}>
                    {subtitle ?? "Claim Intelligence Platform"}
                </div>
            </div>
        </div>
    );
}

/** Shared error banner */
export function FormError({ message }: { message: string | null }) {
    if (!message) return null;
    return (
        <div style={{
            background: "var(--crimson-bg)", border: "1px solid var(--crimson-border)",
            borderRadius: 4, padding: "10px 12px", marginBottom: 16,
            fontSize: "0.8125rem", color: "var(--crimson)",
        }}>
            {message}
        </div>
    );
}

/** Shared success banner */
export function FormSuccess({ message }: { message: string | null }) {
    if (!message) return null;
    return (
        <div style={{
            background: "var(--green-bg)", border: "1px solid var(--green-border)",
            borderRadius: 4, padding: "10px 12px", marginBottom: 16,
            fontSize: "0.8125rem", color: "var(--green)",
            display: "flex", alignItems: "center", gap: 8,
        }}>
            {message}
        </div>
    );
}

/** Shared form field label */
export function FieldLabel({ children }: { children: React.ReactNode }) {
    return (
        <label style={{
            display: "block", fontSize: "0.75rem",
            color: "var(--text-muted)", fontWeight: 500,
            marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.04em",
        }}>
            {children}
        </label>
    );
}

/**
 * Centered auth card layout used by login + register.
 * Renders the public Navbar above the centered card.
 */
export function AuthLayout({ children, title }: { children: React.ReactNode; title: string }) {
    return (
        <div style={{ minHeight: "100vh", background: "var(--bg-base)" }}>
            <Navbar />
            <div style={{
                display: "flex", flexDirection: "column",
                alignItems: "center", justifyContent: "center",
                minHeight: "calc(100vh - 52px)", padding: "32px 20px",
            }}>
                <div className="auth-card" style={{ maxWidth: 460, width: "100%" }}>
                    <LogoMark subtitle={title} />
                    {children}
                    <div style={{
                        marginTop: 24, paddingTop: 16,
                        borderTop: "1px solid var(--border)",
                        textAlign: "center",
                    }} id="auth-footer">
                        {/* injected by each page */}
                    </div>
                </div>
            </div>
        </div>
    );
}
