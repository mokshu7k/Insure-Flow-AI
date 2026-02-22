"use client";
import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore, useIsAdmin, useIsAdjuster } from "@/store/authStore";
import {
    LayoutDashboard, FileText, AlertTriangle, Scale, Shield, ShieldAlert, User, LogOut,
    MessageSquare, QrCode, PanelLeftClose, PanelLeftOpen
} from "lucide-react";

const navItems = [
    { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, alwaysShow: true },
    { href: "/claims", label: "Claims", icon: FileText, alwaysShow: true },
    { href: "/cashless", label: "Cashless", icon: QrCode, alwaysShow: true },
    { href: "/chat", label: "Assistant", icon: MessageSquare, alwaysShow: true },
    { href: "/adjuster", label: "Adjuster", icon: Scale, adminOnly: true },
    { href: "/audit", label: "Audit", icon: ShieldAlert, auditorRole: true },
    { href: "/compliance", label: "Compliance", icon: Shield, complianceRole: true },
    { href: "/profile", label: "Profile", icon: User, alwaysShow: true },
];

export function LeftRail() {
    const pathname = usePathname();
    const { user, logout } = useAuthStore();
    const isAdmin = useIsAdmin();
    const isAdjuster = useIsAdjuster();
    const isAuditor = user?.role === "AUDITOR";
    const [collapsed, setCollapsed] = useState(false);

    const visible = navItems.filter((i) => i.alwaysShow || (i.adminOnly && isAdmin) || (i.auditorRole && isAuditor) || (i.complianceRole && (isAdmin || isAuditor)));

    const railWidth = collapsed ? 56 : 220;

    return (
        <aside style={{
            gridRow: "1 / -1",
            width: railWidth,
            minWidth: railWidth,
            background: "var(--bg-panel)",
            borderRight: "1px solid var(--border)",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            transition: "width 200ms ease, min-width 200ms ease",
        }}>
            {/* Logo + collapse toggle */}
            <div style={{
                padding: collapsed ? "16px 8px" : "16px 18px",
                borderBottom: "1px solid var(--border)",
                display: "flex", alignItems: "center",
                justifyContent: collapsed ? "center" : "flex-start",
                gap: 8,
            }}>
                {!collapsed && (
                    <>
                        <AlertTriangle size={16} color="var(--amber)" />
                        <span style={{ fontWeight: 700, fontSize: "0.875rem", letterSpacing: "0.02em", flex: 1 }}>InsureFlow</span>
                    </>
                )}
                <button
                    onClick={() => setCollapsed((c) => !c)}
                    title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                    style={{
                        background: "none", border: "none", cursor: "pointer",
                        color: "var(--text-muted)", padding: 4, borderRadius: 4,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        transition: "color 150ms",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-primary)")}
                    onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
                >
                    {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
                </button>
            </div>

            {/* Nav */}
            <nav style={{ flex: 1, padding: "8px 0", overflowY: "auto" }}>
                {visible.map(({ href, label, icon: Icon }) => {
                    const active = pathname === href || pathname.startsWith(href + "/");
                    return (
                        <Link key={href} href={href} title={collapsed ? label : undefined} style={{
                            display: "flex", alignItems: "center", gap: 10,
                            padding: collapsed ? "10px 0" : "8px 18px",
                            justifyContent: collapsed ? "center" : "flex-start",
                            fontSize: "0.8125rem", fontWeight: active ? 500 : 400,
                            color: active ? "var(--text-primary)" : "var(--text-secondary)",
                            background: active ? "var(--bg-surface)" : "transparent",
                            borderLeft: active ? "2px solid var(--blue)" : "2px solid transparent",
                            textDecoration: "none",
                            transition: "all 150ms",
                        }}>
                            <Icon size={16} />
                            {!collapsed && label}
                        </Link>
                    );
                })}
            </nav>

            {/* User Footer */}
            {user && (
                <div style={{ borderTop: "1px solid var(--border)", padding: collapsed ? "12px 8px" : "12px 18px" }}>
                    {!collapsed && (
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                            <div style={{
                                width: 28, height: 28, borderRadius: "50%",
                                background: "var(--blue-bg)", border: "1px solid var(--blue-border)",
                                display: "flex", alignItems: "center", justifyContent: "center",
                                flexShrink: 0,
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
                    )}
                    <button onClick={logout} className="btn btn-ghost" title={collapsed ? "Sign out" : undefined} style={{
                        width: "100%", padding: collapsed ? "6px 0" : "5px 10px",
                        justifyContent: "center",
                    }}>
                        <LogOut size={14} />
                        {!collapsed && "Sign out"}
                    </button>
                </div>
            )}
        </aside>
    );
}
