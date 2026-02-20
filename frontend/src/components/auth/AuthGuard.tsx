"use client";
import { useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/authStore";

interface AuthGuardProps { children: React.ReactNode; requireAdmin?: boolean; }

const ADMIN_ROLES = ["INSURER_ADMIN", "AUDITOR", "CLAIM_ADJUSTER"];

export function AuthGuard({ children, requireAdmin }: AuthGuardProps) {
    const { user, accessToken, loadUser } = useAuthStore();
    const router = useRouter();

    // Check if user has admin role
    const hasAdminRole = useMemo(() => {
        return user ? ADMIN_ROLES.includes(user.role) : false;
    }, [user]);

    useEffect(() => {
        if (!accessToken) { router.replace("/login"); return; }
        if (!user) { loadUser(); }
    }, [accessToken, user, loadUser, router]);

    useEffect(() => {
        if (user && requireAdmin && !hasAdminRole) {
            router.replace("/claims");
        }
    }, [user, requireAdmin, hasAdminRole, router]);

    // Show loading while user is not loaded
    if (!user) return (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", background: "var(--bg-base)" }}>
            <div className="skeleton" style={{ width: 200, height: 20 }} />
        </div>
    );

    // Block rendering if requireAdmin but user doesn't have admin role (will redirect)
    if (requireAdmin && !hasAdminRole) {
        return (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", background: "var(--bg-base)" }}>
                <div className="skeleton" style={{ width: 200, height: 20 }} />
            </div>
        );
    }

    return <>{children}</>;
}
