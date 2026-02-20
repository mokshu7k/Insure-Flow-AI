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
    /** True once the persisted state has been rehydrated from localStorage. */
    _hasHydrated: boolean;
    login: (email: string, password: string) => Promise<void>;
    logout: () => void;
    loadUser: () => Promise<void>;
    _setHasHydrated: (v: boolean) => void;
}

export const useAuthStore = create<AuthState>()(
    persist(
        (set, get) => ({
            user: null,
            accessToken: null,
            isLoading: false,
            _hasHydrated: false,
            _setHasHydrated: (v) => set({ _hasHydrated: v }),

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
            // Only persist auth data — never persist the hydration flag itself.
            partialize: (s) => ({ accessToken: s.accessToken, user: s.user }),
            // Prevent synchronous localStorage read during SSR hydration.
            // Rehydration is triggered explicitly in StoreHydrator after mount.
            skipHydration: true,
            // Called after rehydration completes — flip the flag so AuthGuard
            // knows it is safe to evaluate auth state and potentially redirect.
            onRehydrateStorage: () => (state) => {
                state?._setHasHydrated(true);
            },
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
