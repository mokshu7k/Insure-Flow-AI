"use client";
import { useEffect, useState } from "react";
import { CommandLayout } from "@/components/layout/CommandLayout";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { MonoValue, StatusPill } from "@/components/ui";
import { useAuthStore } from "@/store/authStore";
import { claimService } from "@/services/claimService";
import { User, Shield, FileText, Calendar, CheckCircle, XCircle, AlertTriangle } from "lucide-react";
import type { Claim } from "@/types";

const ROLE_CONFIG: Record<string, { label: string; color: string; bg: string; border: string; desc: string }> = {
    CUSTOMER: { label: "Policyholder", color: "var(--blue)", bg: "var(--blue-bg)", border: "var(--blue-border)", desc: "Submit and track your insurance claims." },
    PROVIDER: { label: "Healthcare Provider", color: "var(--green)", bg: "var(--green-bg)", border: "var(--green-border)", desc: "Upload documents and support claims for your facility." },
    INSURER_ADMIN: { label: "Insurer Admin", color: "var(--crimson)", bg: "var(--crimson-bg)", border: "var(--crimson-border)", desc: "Full administrative access — fraud analysis, approvals, and compliance." },
    AUDITOR: { label: "Compliance Auditor", color: "var(--amber)", bg: "var(--amber-bg)", border: "var(--amber-border)", desc: "Read-only access to audit trails and compliance reports." },
};

function formatDate(dt: string | null | undefined) {
    if (!dt) return "—";
    const d = new Date(dt);
    if (isNaN(d.getTime())) return "—";
    return d.toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" });
}

export default function ProfilePage() {
    const { user } = useAuthStore();
    const [claims, setClaims] = useState<Claim[]>([]);
    const [loading, setLoading] = useState(true);
    const roleCfg = user ? (ROLE_CONFIG[user.role] || ROLE_CONFIG.CUSTOMER) : null;

    useEffect(() => {
        claimService.list(1, 5)
            .then((r) => setClaims(r.items))
            .catch(() => setClaims([]))
            .finally(() => setLoading(false));
    }, []);

    if (!user) return null;

    return (
        <AuthGuard>
            <CommandLayout header={
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <User size={15} color="var(--text-muted)" />
                    <span style={{ fontSize: "0.875rem", fontWeight: 600 }}>My Profile</span>
                </div>
            }>
                <div style={{ maxWidth: 700, margin: "0 auto", padding: "24px 20px", display: "flex", flexDirection: "column", gap: 16 }}>

                    {/* User card */}
                    <div className="panel" style={{ padding: 24 }}>
                        <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
                            <div style={{
                                width: 48, height: 48, borderRadius: "50%",
                                background: roleCfg?.bg, border: `1px solid ${roleCfg?.border}`,
                                display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                            }}>
                                <User size={20} color={roleCfg?.color} />
                            </div>
                            <div style={{ flex: 1 }}>
                                <div style={{ fontWeight: 600, fontSize: "1rem", marginBottom: 4 }}>{user.email}</div>
                                <div style={{
                                    display: "inline-flex", alignItems: "center", gap: 6,
                                    fontFamily: "var(--font-mono)", fontSize: "0.625rem", fontWeight: 600,
                                    textTransform: "uppercase", letterSpacing: "0.08em",
                                    color: roleCfg?.color, background: roleCfg?.bg, border: `1px solid ${roleCfg?.border}`,
                                    borderRadius: 3, padding: "2px 8px",
                                }}>
                                    <Shield size={10} />
                                    {roleCfg?.label || user.role}
                                </div>
                                <p style={{ marginTop: 8, fontSize: "0.8125rem", color: "var(--text-secondary)" }}>{roleCfg?.desc}</p>
                            </div>
                            <div style={{ textAlign: "right" }}>
                                <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 4 }}>Account</div>
                                <div style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--green)", fontSize: "0.75rem" }}>
                                    <CheckCircle size={12} /> Active
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Role capabilities */}
                    <div className="panel" style={{ padding: 20 }}>
                        <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 14 }}>
                            Portal Access
                        </div>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px 24px" }}>
                            {[
                                ["Dashboard", true],
                                ["Claims — view & submit", true],
                                ["Fraud analysis", user.role === "INSURER_ADMIN"],
                                ["Claim approvals", user.role === "INSURER_ADMIN"],
                                ["Adjuster AI agent", user.role === "INSURER_ADMIN"],
                                ["Compliance & audit trail", user.role === "INSURER_ADMIN" || user.role === "AUDITOR"],
                            ].map(([label, has]) => (
                                <div key={label as string} style={{
                                    display: "flex", alignItems: "center", gap: 8, fontSize: "0.8125rem",
                                    color: has ? "var(--text-primary)" : "var(--text-muted)"
                                }}>
                                    {has ? <CheckCircle size={13} color="var(--green)" /> : <XCircle size={13} color="var(--border-strong)" />}
                                    {label}
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Recent claims */}
                    <div className="panel" style={{ padding: 20 }}>
                        <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 14, display: "flex", justifyContent: "space-between" }}>
                            Recent Claims
                            <a href="/claims" style={{ color: "var(--blue)", fontSize: "0.6875rem", textDecoration: "none" }}>View all →</a>
                        </div>
                        {loading && [...Array(3)].map((_, i) => (
                            <div key={i} className="skeleton" style={{ height: 12, marginBottom: 10, width: `${60 + i * 15}%` }} />
                        ))}
                        {!loading && claims.length === 0 && (
                            <div style={{ color: "var(--text-muted)", fontSize: "0.8125rem", textAlign: "center", padding: "16px 0" }}>
                                No claims yet — <a href="/claims" style={{ color: "var(--blue)", textDecoration: "none" }}>submit your first claim</a>
                            </div>
                        )}
                        {claims.map((c) => (
                            <div key={c.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
                                <FileText size={13} color="var(--text-muted)" />
                                <div style={{ flex: 1 }}>
                                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                        <MonoValue value={c.policy_number} size="0.8rem" />
                                        <StatusPill status={c.status} />
                                    </div>
                                    <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.625rem", color: "var(--text-muted)", marginTop: 2 }}>
                                        {c.claim_type} · {formatDate(c.created_at)}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Account info */}
                    <div className="panel" style={{ padding: 20 }}>
                        <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 14 }}>
                            Account Information
                        </div>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px 24px" }}>
                            {[
                                ["Email", user.email],
                                ["Role", user.role],
                                ["User ID", user.id.slice(0, 13) + "…"],
                            ].map(([label, value]) => (
                                <div key={label as string}>
                                    <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", marginBottom: 3, textTransform: "uppercase", letterSpacing: "0.04em" }}>{label}</div>
                                    <MonoValue value={value as string} size="0.8125rem" />
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </CommandLayout>
        </AuthGuard>
    );
}
