import api from "./api";
import type { Claim, ClaimCreate, ClaimListResponse, ClaimStatusUpdate } from "@/types";

export const claimService = {
    async create(data: ClaimCreate): Promise<Claim> {
        const res = await api.post<Claim>("/claims/", data);
        return res.data;
    },

    async list(params?: { skip?: number; limit?: number; status?: string }): Promise<ClaimListResponse> {
        const res = await api.get<ClaimListResponse>("/claims/", { params });
        return res.data;
    },

    async getById(id: string): Promise<Claim> {
        const res = await api.get<Claim>(`/claims/${id}`);
        return res.data;
    },

    async updateStatus(id: string, data: ClaimStatusUpdate): Promise<Claim> {
        const res = await api.put<Claim>(`/claims/${id}/status`, data);
        return res.data;
    },

    async triggerFraudAnalysis(id: string): Promise<Claim> {
        const res = await api.post<Claim>(`/claims/${id}/analyze`);
        return res.data;
    },
};
