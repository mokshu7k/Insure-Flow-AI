import api from "./api";
import type { AdjusterChatRequest, AdjusterChatResponse, AdjusterReportResponse } from "@/types";

export const adjusterService = {
    chat: (data: AdjusterChatRequest) =>
        api.post<AdjusterChatResponse>("/adjuster/chat", data).then((r) => r.data),

    getReport: (claimId: string) =>
        api.get<AdjusterReportResponse>(`/adjuster/report/${claimId}`).then((r) => r.data),

    generateReport: (claimId: string) =>
        api.post<AdjusterReportResponse>(`/adjuster/report/${claimId}`).then((r) => r.data),

    regenerateReport: (claimId: string) =>
        api.post<AdjusterReportResponse>(`/adjuster/report/${claimId}?force=true`).then((r) => r.data),
};
