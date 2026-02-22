"use client";
import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore, useIsAdmin, useIsAdjuster } from "@/store/authStore";
import {
    LayoutDashboard, FileText, AlertTriangle, Scale, Shield, ShieldAlert, User, LogOut,
    MessageSquare, QrCode, PanelLeftClose, PanelLeftOpen
} from "lucide-react";

const NAV_SECTIONS = [
    {
        title: "MENU",
        items: [
            { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, alwaysShow: true },
            { href: "/claims", label: "Claims", icon: FileText, alwaysShow: true },
            { href: "/cashless", label: "Cashless", icon: QrCode, alwaysShow: true },
            { href: "/chat", label: "Assistant", icon: MessageSquare, alwaysShow: true },
        ],
    },
    {
        title: "MANAGEMENT",
        items: [
            { href: "/adjuster", label: "Adjuster", icon: Scale, adminOnly: true },
            { href: "/audit", label: "Audit", icon: ShieldAlert, auditorRole: true },
            { href: "/compliance", label: "Compliance", icon: Shield, complianceRole: true },
        ],
    },
    {
        title: "ACCOUNT",
        items: [
            { href: "/profile", label: "Profile", icon: User, alwaysShow: true },
        ],
    },
];

export function LeftRail() {
    const pathname = usePathname();
    const { user, logout } = useAuthStore();
    const isAdmin = useIsAdmin();
    const isAdjuster = useIsAdjuster();
    const isAuditor = user?.role === "AUDITOR";
    const [collapsed, setCollapsed] = useState(false);

    const railWidth = collapsed ? 64 : 252;

    function isVisible(item: { alwaysShow?: boolean; adminOnly?: boolean; auditorRole?: boolean; complianceRole?: boolean }) {
        return item.alwaysShow || (item.adminOnly && (isAdmin || isAdjuster)) || (item.auditorRole && isAuditor) || (item.complianceRole && (isAdmin || isAuditor));
    }

    return (
        <aside style={{
            gridRow: "1 / -1",
            width: railWidth,
            minWidth: railWidth,
            background: "#ffffff",
            borderRight: "1px solid #e8ecf1",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            transition: "width 250ms cubic-bezier(0.4, 0, 0.2, 1), min-width 250ms cubic-bezier(0.4, 0, 0.2, 1)",
        }}>
            {/* Logo + collapse toggle */}
            <div style={{
                padding: collapsed ? "18px 8px" : "18px 20px",
                borderBottom: "1px solid #e8ecf1",
                display: "flex", alignItems: "center",
                justifyContent: collapsed ? "center" : "flex-start",
                gap: 10,
                minHeight: 60,
            }}>
                {!collapsed && (
                    <>
                        <div style={{
                            width: 34, height: 34, borderRadius: 10,
                            background: "linear-gradient(135deg, #1a56db, #3b82f6)",
                            display: "flex", alignItems: "center", justifyContent: "center",
                            flexShrink: 0,
                            boxShadow: "0 2px 8px rgba(26,86,219,0.25)",
                        }}>
                            <Shield size={17} color="white" />
                        </div>
                        <span style={{ fontWeight: 800, fontSize: "1.0625rem", letterSpacing: "-0.02em", flex: 1, color: "#0f172a" }}>
                            InsureFlow
                        </span>
                    </>
                )}
                <button
                    onClick={() => setCollapsed((c) => !c)}
                    title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                    style={{
                        background: "none", border: "none", cursor: "pointer",
                        color: "#94a3b8", padding: 4, borderRadius: 6,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        transition: "color 150ms",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = "#334155")}
                    onMouseLeave={(e) => (e.currentTarget.style.color = "#94a3b8")}
                >
                    {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
                </button>
            </div>

            {/* Nav — grouped sections */}
            <nav style={{ flex: 1, padding: "8px 10px", overflowY: "auto" }}>
                {NAV_SECTIONS.map((section) => {
                    const visibleItems = section.items.filter(isVisible);
                    if (visibleItems.length === 0) return null;
                    return (
                        <div key={section.title} style={{ marginBottom: 8 }}>
                            {!collapsed && (
                                <div style={{
                                    fontSize: "0.625rem", fontWeight: 700,
                                    color: "#94a3b8", textTransform: "uppercase",
                                    letterSpacing: "0.08em", padding: "10px 12px 5px",
                                }}>
                                    {section.title}
                                </div>
                            )}
                            {visibleItems.map(({ href, label, icon: Icon }) => {
                                const active = pathname === href || pathname.startsWith(href + "/");
                                return (
                                    <Link key={href} href={href} title={collapsed ? label : undefined} style={{
                                        display: "flex", alignItems: "center", gap: 11,
                                        padding: collapsed ? "10px 0" : "9px 12px",
                                        justifyContent: collapsed ? "center" : "flex-start",
                                        fontSize: "0.8125rem", fontWeight: active ? 600 : 400,
                                        color: active ? "#1a56db" : "#64748b",
                                        background: active ? "rgba(26,86,219,0.06)" : "transparent",
                                        borderRadius: 8,
                                        textDecoration: "none",
                                        transition: "all 150ms",
                                        marginBottom: 1,
                                        borderLeft: active ? "3px solid #1a56db" : "3px solid transparent",
                                    }}
                                    onMouseEnter={(e) => { if (!active) { e.currentTarget.style.background = "#f1f5f9"; e.currentTarget.style.color = "#334155"; } }}
                                    onMouseLeave={(e) => { if (!active) { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "#64748b"; } }}
                                    >
                                        <Icon size={17} style={{ flexShrink: 0 }} />
                                        {!collapsed && label}
                                    </Link>
                                );
                            })}
                        </div>
                    );
                })}
            </nav>

            {/* User Footer */}
            {user && (
                <div style={{ borderTop: "1px solid #e8ecf1", padding: collapsed ? "14px 8px" : "14px 16px" }}>
                    {!collapsed && (
                        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                            <div style={{
                                width: 34, height: 34, borderRadius: "50%",
                                background: "linear-gradient(135deg, #e0e7ff, #c7d2fe)",
                                border: "2px solid #e8ecf1",
                                display: "flex", alignItems: "center", justifyContent: "center",
                                flexShrink: 0,
                            }}>
                                <User size={14} color="#4f46e5" />
                            </div>
                            <div style={{ minWidth: 0, flex: 1 }}>
                                <div style={{
                                    fontSize: "0.8125rem", fontWeight: 600,
                                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                                    color: "#0f172a",
                                }}>
                                    {user.email?.split("@")[0]}
                                </div>
                                <div style={{
                                    fontSize: "0.625rem", color: "#94a3b8",
                                    fontFamily: "var(--font-mono)",
                                    textTransform: "uppercase", letterSpacing: "0.06em",
                                }}>
                                    {user.role?.replace(/_/g, " ")}
                                </div>
                            </div>
                        </div>
                    )}
                    <button onClick={logout} title={collapsed ? "Sign out" : undefined} style={{
                        display: "flex", alignItems: "center", gap: 6,
                        width: "100%", padding: collapsed ? "8px 0" : "8px 12px",
                        justifyContent: "center",
                        background: "#f8fafc",
                        border: "1px solid #e8ecf1",
                        borderRadius: 8,
                        color: "#64748b",
                        fontSize: "0.8125rem",
                        fontWeight: 500,
                        cursor: "pointer",
                        transition: "all 150ms",
                        fontFamily: "var(--font-sans)",
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "#f1f5f9"; e.currentTarget.style.color = "#dc2626"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "#f8fafc"; e.currentTarget.style.color = "#64748b"; }}
                    >
                        <LogOut size={14} />
                        {!collapsed && "Sign out"}
                    </button>
                </div>
            )}
        </aside>
    );
}
