import api from "./api";
import type { FraudAssessment } from "@/types";

export const fraudService = {
    /** Run fraud analysis on a claim (auto-picks first document, uses LangGraph agent). */
    analyze: (claimId: string) =>
        api.post<FraudAssessment>(`/fraud/analyze/${claimId}`).then((r) => r.data),

    /** Run fraud agent on a specific document (6-node LangGraph pipeline). */
    agentAnalyze: (claimId: string, documentId: string) =>
        api.post<FraudAssessment>(`/fraud/agent-analyze/${claimId}/${documentId}`).then((r) => r.data),

    /** Fetch the latest fraud assessment for a claim. */
    getAssessment: (claimId: string) =>
        api.get<FraudAssessment>(`/fraud/${claimId}`).then((r) => r.data),
};
