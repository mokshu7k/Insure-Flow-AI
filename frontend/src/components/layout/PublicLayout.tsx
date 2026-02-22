import Link from "next/link";
import { Shield } from "lucide-react";

/**
 * Shared top nav for all public-facing pages (homepage, login, register).
 * Always identical across pages — logo left, Sign in + Get started right.
 */
export function Navbar() {
    return (
        <nav style={{
            position: "sticky", top: 0, zIndex: 50,
            background: "rgba(255,255,255,0.92)", backdropFilter: "blur(12px)",
            borderBottom: "1px solid var(--border)",
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "0 32px", height: 60,
            boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
        }}>
            {/* Logo */}
            <Link href="/" style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none" }}>
                <div style={{
                    width: 30, height: 30, borderRadius: 8,
                    background: "var(--brand)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                    <Shield size={15} color="white" />
                </div>
                <span style={{ fontWeight: 800, fontSize: "1rem", color: "var(--text-primary)" }}>InsureFlow</span>
            </Link>

            {/* Actions */}
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Link href="/login" style={{
                    padding: "7px 16px", fontSize: "0.8125rem",
                    color: "var(--text-secondary)", textDecoration: "none",
                    border: "1px solid var(--border)", borderRadius: 8,
                    fontWeight: 500,
                }}>
                    Sign in
                </Link>
                <Link href="/register" style={{
                    padding: "7px 18px", fontSize: "0.8125rem",
                    background: "var(--brand)", color: "#fff", textDecoration: "none",
                    borderRadius: 8, fontWeight: 600,
                    boxShadow: "0 1px 3px rgba(26,86,219,0.3)",
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
            <div style={{
                width: 34, height: 34, borderRadius: 8,
                background: "var(--brand)",
                display: "flex", alignItems: "center", justifyContent: "center",
            }}>
                <Shield size={17} color="white" />
            </div>
            <div>
                <div style={{ fontWeight: 800, fontSize: "1rem", letterSpacing: "0.01em" }}>InsureFlow</div>
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
