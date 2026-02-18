import api from "./api";
import type { FraudAssessment } from "@/types";

export const fraudService = {
    async getAssessment(claimId: string): Promise<FraudAssessment> {
        const res = await api.get<FraudAssessment>(`/fraud/assessment/${claimId}`);
        return res.data;
    },
};
