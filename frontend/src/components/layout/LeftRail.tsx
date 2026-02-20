"use client";
import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore, useIsAdmin, useIsAdjuster } from "@/store/authStore";
import {
    LayoutDashboard, FileText, AlertTriangle, Scale, Shield, User, LogOut, ChevronRight, MessageSquare, QrCode
} from "lucide-react";

const navItems = [
    { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, alwaysShow: true },
    { href: "/claims", label: "Claims", icon: FileText, alwaysShow: true },
    { href: "/cashless", label: "Cashless", icon: QrCode, alwaysShow: true },
    { href: "/chat", label: "Assistant", icon: MessageSquare, alwaysShow: true },
    { href: "/adjuster", label: "Adjuster", icon: Scale, adminOnly: true },
    { href: "/compliance", label: "Compliance", icon: Shield, complianceRole: true },
    { href: "/profile", label: "Profile", icon: User, alwaysShow: true },
];

export function LeftRail() {
    const pathname = usePathname();
    const { user, logout } = useAuthStore();
    const isAdmin = useIsAdmin();
    const isAdjuster = useIsAdjuster();
    const isAuditor = user?.role === "AUDITOR";

    const visible = navItems.filter((i) => i.alwaysShow || (i.adminOnly && isAdmin) || (i.complianceRole && (isAdmin || isAuditor)));

    return (
        <aside style={{
            gridRow: "1 / -1",
            width: "var(--rail-width)",
            background: "var(--bg-panel)",
            borderRight: "1px solid var(--border)",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
        }}>
            {/* Logo */}
            <div style={{ padding: "16px 18px", borderBottom: "1px solid var(--border)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <AlertTriangle size={16} color="var(--amber)" />
                    <span style={{ fontWeight: 700, fontSize: "0.875rem", letterSpacing: "0.02em" }}>InsureFlow</span>
                    <span style={{ fontSize: "0.625rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)", marginLeft: "auto" }}>v2</span>
                </div>
            </div>

            {/* Nav */}
            <nav style={{ flex: 1, padding: "8px 0", overflowY: "auto" }}>
                {visible.map(({ href, label, icon: Icon }) => {
                    const active = pathname === href || pathname.startsWith(href + "/");
                    return (
                        <Link key={href} href={href} style={{
                            display: "flex", alignItems: "center", gap: 10,
                            padding: "8px 18px",
                            fontSize: "0.8125rem", fontWeight: active ? 500 : 400,
                            color: active ? "var(--text-primary)" : "var(--text-secondary)",
                            background: active ? "var(--bg-surface)" : "transparent",
                            borderLeft: active ? "2px solid var(--blue)" : "2px solid transparent",
                            textDecoration: "none",
                            transition: "all 150ms",
                        }}>
                            <Icon size={15} />
                            {label}
                        </Link>
                    );
                })}
            </nav>

            {/* User Footer */}
            {user && (
                <div style={{ borderTop: "1px solid var(--border)", padding: "12px 18px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                        <div style={{
                            width: 28, height: 28, borderRadius: "50%",
                            background: "var(--blue-bg)", border: "1px solid var(--blue-border)",
                            display: "flex", alignItems: "center", justifyContent: "center",
                        }}>
                            <User size={13} color="var(--blue)" />
                        </div>
                        <div style={{ minWidth: 0 }}>
                            <div style={{ fontSize: "0.75rem", fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                {user.email}
                            </div>
                            <div style={{ fontSize: "0.625rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                                {user.role}
                            </div>
                        </div>
                    </div>
                    <button onClick={logout} className="btn btn-ghost" style={{ width: "100%", padding: "5px 10px", justifyContent: "center" }}>
                        <LogOut size={13} />
                        Sign out
                    </button>
                </div>
            )}
        </aside>
    );
}
