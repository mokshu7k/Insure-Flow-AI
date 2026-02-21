import api from "./api";
import type { AuditLogEntry, ConsentRecord } from "@/types";

export const complianceService = {
    auditTrail: (entityId?: string, limit = 100) =>
        api.get<AuditLogEntry[]>("/compliance/audit", { params: { entity_id: entityId, limit } }).then((r) => r.data),

    consentHistory: (userId: string) =>
        api.get<ConsentRecord[]>(`/compliance/consent/${userId}`).then((r) => r.data),
};
