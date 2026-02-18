"use client";

import { useEffect } from "react";
import { useAuthStore } from "@/store/authStore";

export default function AuthGuard({ children }: { children: React.ReactNode }) {
    const { user, setUser } = useAuthStore();

    useEffect(() => {
        // In demo mode, auto-inject a CUSTOMER user only if nobody has logged in yet.
        // This allows users who logged in via the login page (with a role picker)
        // to keep their chosen role instead of being overridden to INSURER_ADMIN.
        if (!user) {
            setUser({
                id: "demo-user-001",
                email: "demo@insureflow.com",
                role: "CUSTOMER",
                is_active: true,
                created_at: "2026-01-01T00:00:00Z",
            });
        }
    }, [user, setUser]);

    return <>{children}</>;
}
