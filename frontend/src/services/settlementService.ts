import api from "./api";
import type { Settlement, SettlementCreate, SettlementStatusUpdate } from "@/types";

export const settlementService = {
    async initiate(data: SettlementCreate): Promise<Settlement> {
        const res = await api.post<Settlement>("/settlements/", data);
        return res.data;
    },

    async updateStatus(id: string, data: SettlementStatusUpdate): Promise<Settlement> {
        const res = await api.put<Settlement>(`/settlements/${id}/status`, data);
        return res.data;
    },

    async getByClaimId(claimId: string): Promise<Settlement | null> {
        const res = await api.get<Settlement | null>(`/settlements/claim/${claimId}`);
        return res.data;
    },
};
