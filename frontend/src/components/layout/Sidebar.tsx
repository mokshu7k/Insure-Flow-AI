"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { cn } from "@/lib/utils";
import {
    LayoutDashboard,
    FileText,
    QrCode,
    Users,
    Shield,
    BarChart3,
    AlertTriangle,
    ClipboardList,
    ChevronLeft,
    ChevronRight,
    LogOut,
    ScanLine,
} from "lucide-react";
import { useState } from "react";

interface NavItem {
    label: string;
    href: string;
    icon: React.ReactNode;
    roles?: string[];
}

const navItems: NavItem[] = [
    {
        label: "Dashboard",
        href: "/dashboard",
        icon: <LayoutDashboard size={20} />,
    },
    {
        label: "Analytics",
        href: "/dashboard/analytics",
        icon: <BarChart3 size={20} />,
        roles: ["INSURER_ADMIN", "AUDITOR"],
    },
    {
        label: "Fraud Overview",
        href: "/dashboard/fraud-overview",
        icon: <AlertTriangle size={20} />,
        roles: ["INSURER_ADMIN", "AUDITOR"],
    },
    { label: "Claims", href: "/claims", icon: <FileText size={20} /> },
    {
        label: "New Claim",
        href: "/claims/new",
        icon: <ClipboardList size={20} />,
        roles: ["CUSTOMER"],
    },
    {
        label: "Review Queue",
        href: "/claims/review",
        icon: <Shield size={20} />,
        roles: ["INSURER_ADMIN"],
    },
    {
        label: "Generate QR",
        href: "/cashless/generate",
        icon: <QrCode size={20} />,
        roles: ["PROVIDER"],
    },
    {
        label: "Scan QR",
        href: "/cashless/scan",
        icon: <ScanLine size={20} />,
        roles: ["INSURER_ADMIN"],
    },
    {
        label: "Users",
        href: "/admin/users",
        icon: <Users size={20} />,
        roles: ["INSURER_ADMIN"],
    },
    {
        label: "Audit Logs",
        href: "/admin/audit-logs",
        icon: <ClipboardList size={20} />,
        roles: ["INSURER_ADMIN", "AUDITOR"],
    },
];

export default function Sidebar() {
    const pathname = usePathname();
    const { user, logout } = useAuthStore();
    const [collapsed, setCollapsed] = useState(false);

    const filteredItems = navItems.filter(
        (item) => !item.roles || (user && item.roles.includes(user.role))
    );

    return (
        <aside
            className={cn(
                "flex flex-col h-screen sticky top-0 transition-all duration-300 ease-in-out",
                collapsed ? "w-[68px]" : "w-[260px]"
            )}
            style={{ background: "var(--sidebar-bg)", color: "var(--sidebar-text)" }}
        >
            {/* Logo */}
            <div className="flex items-center gap-3 px-4 h-16 border-b border-white/10">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-400 to-purple-500 flex items-center justify-center font-bold text-white text-sm shrink-0">
                    IF
                </div>
                {!collapsed && (
                    <span className="font-semibold text-lg tracking-tight whitespace-nowrap">
                        InsureFlow
                    </span>
                )}
            </div>

            {/* Nav */}
            <nav className="flex-1 overflow-y-auto py-4 px-2 space-y-1">
                {filteredItems.map((item) => {
                    const isActive =
                        pathname === item.href ||
                        (item.href !== "/dashboard" && pathname.startsWith(item.href));
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={cn(
                                "flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 group",
                                isActive
                                    ? "text-white font-medium"
                                    : "text-indigo-200/70 hover:text-white"
                            )}
                            style={isActive ? { background: "var(--sidebar-active)" } : {}}
                            onMouseEnter={(e) => {
                                if (!isActive)
                                    e.currentTarget.style.background = "var(--sidebar-hover)";
                            }}
                            onMouseLeave={(e) => {
                                if (!isActive) e.currentTarget.style.background = "transparent";
                            }}
                        >
                            <span className="shrink-0">{item.icon}</span>
                            {!collapsed && (
                                <span className="text-sm whitespace-nowrap">{item.label}</span>
                            )}
                        </Link>
                    );
                })}
            </nav>

            {/* Footer */}
            <div className="border-t border-white/10 p-2 space-y-1">
                <button
                    onClick={() => {
                        logout();
                        window.location.href = "/login";
                    }}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-lg w-full text-indigo-200/70 hover:text-white transition-colors"
                    onMouseEnter={(e) =>
                        (e.currentTarget.style.background = "var(--sidebar-hover)")
                    }
                    onMouseLeave={(e) =>
                        (e.currentTarget.style.background = "transparent")
                    }
                >
                    <LogOut size={20} />
                    {!collapsed && <span className="text-sm">Logout</span>}
                </button>
                <button
                    onClick={() => setCollapsed(!collapsed)}
                    className="flex items-center justify-center w-full py-2 rounded-lg text-indigo-200/50 hover:text-white transition-colors"
                >
                    {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
                </button>
            </div>
        </aside>
    );
}
