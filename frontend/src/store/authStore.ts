"use client";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/types";
import { authService } from "@/services/authService";

interface LoginResult {
    access_token: string;
    refresh_token: string;
    token_type: string;
    user: User;
}

interface AuthState {
    user: User | null;
    accessToken: string | null;
    isLoading: boolean;
    login: (email: string, password: string) => Promise<void>;
    logout: () => void;
    loadUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
    persist(
        (set, get) => ({
            user: null,
            accessToken: null,
            isLoading: false,

            login: async (email, password) => {
                set({ isLoading: true });
                try {
                    const result: LoginResult = await authService.login({ email, password }) as LoginResult;
                    localStorage.setItem("access_token", result.access_token);
                    localStorage.setItem("refresh_token", result.refresh_token);
                    set({ accessToken: result.access_token, user: result.user });
                } finally {
                    set({ isLoading: false });
                }
            },

            logout: () => {
                localStorage.removeItem("access_token");
                localStorage.removeItem("refresh_token");
                set({ user: null, accessToken: null });
                window.location.href = "/login";
            },

            loadUser: async () => {
                try {
                    const user = await authService.me();
                    set({ user });
                } catch {
                    set({ user: null, accessToken: null });
                    localStorage.removeItem("access_token");
                    localStorage.removeItem("refresh_token");
                }
            },
        }),
        {
            name: "auth-store",
            partialize: (s) => ({ accessToken: s.accessToken, user: s.user }),
        }
    )
);

export const useIsAdmin = () => {
    const role = useAuthStore((s) => s.user?.role);
    return role === "INSURER_ADMIN";
};

export const useIsAdjuster = () => {
    const role = useAuthStore((s) => s.user?.role);
    return role === "CLAIM_ADJUSTER";
};

export const useIsAuditor = () => {
    const role = useAuthStore((s) => s.user?.role);
    return role === "AUDITOR";
};
