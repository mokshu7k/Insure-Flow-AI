import api from "./api";
import type { Claim, ClaimCreate, ClaimListResponse, ClaimStatusUpdate } from "@/types";

export const claimService = {
    list: (page = 1, pageSize = 25, status?: string) =>
        api.get<ClaimListResponse>("/claims", { params: { page, page_size: pageSize, status } }).then((r) => r.data),

    get: (id: string) => api.get<Claim>(`/claims/${id}`).then((r) => r.data),

    create: (data: ClaimCreate) => api.post<Claim>("/claims", data).then((r) => r.data),

    update: (id: string, data: { claim_amount?: number; description?: string }) =>
        api.patch<Claim>(`/claims/${id}`, data).then((r) => r.data),

    updateStatus: (id: string, data: ClaimStatusUpdate) =>
        api.patch<Claim>(`/claims/${id}/status`, data).then((r) => r.data),
};
