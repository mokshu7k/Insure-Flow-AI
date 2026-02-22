import api from "./api";
import type {
    AuditRunListResponse,
    AuditRunDetail,
    AuditFindingListResponse,
    AuditTriggerResponse,
} from "@/types";

export const auditService = {
    triggerSweep: () =>
        api.post<AuditTriggerResponse>("/audit/trigger").then((r) => r.data),

    listRuns: (page = 1, pageSize = 20) =>
        api
            .get<AuditRunListResponse>("/audit/runs", { params: { page, page_size: pageSize } })
            .then((r) => r.data),

    getRun: (runId: string) =>
        api.get<AuditRunDetail>(`/audit/runs/${runId}`).then((r) => r.data),

    listFindings: (params?: {
        page?: number;
        page_size?: number;
        severity?: string;
        finding_type?: string;
        entity_type?: string;
    }) =>
        api
            .get<AuditFindingListResponse>("/audit/findings", { params })
            .then((r) => r.data),
};
