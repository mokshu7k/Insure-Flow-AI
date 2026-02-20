"use client";
import { create } from "zustand";
import axios from "axios";
import type { Claim, ClaimListResponse } from "@/types";
import { claimService } from "@/services/claimService";

function isAbortError(e: unknown): boolean {
    if (axios.isCancel(e)) return true;
    if (e instanceof Error && (e.message === "Network Error" || (e as any).code === "ERR_CANCELED")) return true;
    return false;
}

interface ClaimState {
    claims: Claim[];
    selectedClaim: Claim | null;
    total: number;
    totalPages: number;
    page: number;
    pageSize: number;
    statusFilter: string | undefined;
    isLoading: boolean;
    error: string | null;

    fetchClaims: (page?: number, status?: string) => Promise<void>;
    selectClaim: (claim: Claim | null) => void;
    fetchClaim: (id: string) => Promise<void>;
    setPage: (page: number) => void;
    setFilter: (status: string | undefined) => void;
}

export const useClaimStore = create<ClaimState>((set, get) => ({
    claims: [],
    selectedClaim: null,
    total: 0,
    totalPages: 0,
    page: 1,
    pageSize: 25,
    statusFilter: undefined,
    isLoading: false,
    error: null,

    fetchClaims: async (page?, status?) => {
        const p = page ?? get().page;
        const s = status !== undefined ? status : get().statusFilter;
        set({ isLoading: true, error: null });
        try {
            const data: ClaimListResponse = await claimService.list(p, get().pageSize, s || undefined);
            set({
                claims: data.items,
                total: data.total,
                totalPages: data.total_pages,
                page: data.page,
                statusFilter: s,
            });
        } catch (e: unknown) {
            if (isAbortError(e)) return;          // navigation cancelled the request
            set({ error: e instanceof Error ? e.message : "Failed to load claims" });
        } finally {
            set({ isLoading: false });
        }
    },

    fetchClaim: async (id) => {
        set({ isLoading: true, error: null });
        try {
            const claim = await claimService.get(id);
            set({ selectedClaim: claim });
        } catch (e: unknown) {
            if (isAbortError(e)) return;
            set({ error: e instanceof Error ? e.message : "Claim not found", selectedClaim: null });
        } finally {
            set({ isLoading: false });
        }
    },

    selectClaim: (claim) => set({ selectedClaim: claim }),
    setPage: (page) => { set({ page }); get().fetchClaims(page); },
    setFilter: (status) => { set({ statusFilter: status, page: 1 }); get().fetchClaims(1, status); },
}));
