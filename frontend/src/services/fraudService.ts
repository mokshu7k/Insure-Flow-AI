import api from "./api";
import type { FraudAssessment } from "@/types";

export const fraudService = {
    analyze: (claimId: string) =>
        api.post<FraudAssessment>(`/fraud/analyze/${claimId}`).then((r) => r.data),

    // doesn't exist yet; the caller catches and treats null as "no assessment"
    getAssessment: (claimId: string) =>
        api.get<FraudAssessment>(`/fraud/${claimId}`).then((r) => r.data),
};
