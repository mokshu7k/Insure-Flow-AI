"use client";

import { create } from "zustand";
import type { Claim } from "@/types";

interface ClaimState {
    claims: Claim[];
    selectedClaim: Claim | null;
    loading: boolean;
    total: number;
    page: number;
    pageSize: number;

    setClaims: (claims: Claim[], total: number, page: number, pageSize: number) => void;
    selectClaim: (claim: Claim | null) => void;
    setLoading: (v: boolean) => void;
    updateClaim: (updated: Claim) => void;
}

export const useClaimStore = create<ClaimState>((set) => ({
    claims: [],
    selectedClaim: null,
    loading: false,
    total: 0,
    page: 1,
    pageSize: 20,

    setClaims: (claims, total, page, pageSize) =>
        set({ claims, total, page, pageSize }),

    selectClaim: (claim) => set({ selectedClaim: claim }),

    setLoading: (v) => set({ loading: v }),

    updateClaim: (updated) =>
        set((state) => ({
            claims: state.claims.map((c) => (c.id === updated.id ? updated : c)),
            selectedClaim:
                state.selectedClaim?.id === updated.id ? updated : state.selectedClaim,
        })),
}));
