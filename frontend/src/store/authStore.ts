"use client";

import { create } from "zustand";
import type { User } from "@/types";

interface AuthState {
    user: User | null;
    accessToken: string | null;
    refreshToken: string | null;
    isAuthenticated: boolean;
    isLoading: boolean;

    setTokens: (access: string, refresh: string) => void;
    setUser: (user: User) => void;
    login: (user: User, access: string, refresh: string) => void;
    logout: () => void;
    setLoading: (v: boolean) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
    user: null,
    accessToken:
        typeof window !== "undefined" ? localStorage.getItem("access_token") : null,
    refreshToken:
        typeof window !== "undefined"
            ? localStorage.getItem("refresh_token")
            : null,
    isAuthenticated:
        typeof window !== "undefined"
            ? !!localStorage.getItem("access_token")
            : false,
    isLoading: false,

    setTokens: (access, refresh) => {
        localStorage.setItem("access_token", access);
        localStorage.setItem("refresh_token", refresh);
        set({ accessToken: access, refreshToken: refresh, isAuthenticated: true });
    },

    setUser: (user) => set({ user }),

    login: (user, access, refresh) => {
        localStorage.setItem("access_token", access);
        localStorage.setItem("refresh_token", refresh);
        set({
            user,
            accessToken: access,
            refreshToken: refresh,
            isAuthenticated: true,
        });
    },

    logout: () => {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        set({
            user: null,
            accessToken: null,
            refreshToken: null,
            isAuthenticated: false,
        });
    },

    setLoading: (v) => set({ isLoading: v }),
}));
