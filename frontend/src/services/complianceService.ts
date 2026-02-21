import api from "./api";
import type { AuditLogEntry, ConsentRecord } from "@/types";

export const complianceService = {
    auditTrail: (entityId?: string, limit = 100) =>
        api.get<AuditLogEntry[]>("/compliance/audit", { params: { entity_id: entityId, limit } }).then((r) => r.data),

    consentHistory: (userId: string) =>
        api.get<ConsentRecord[]>(`/compliance/consent/${userId}`).then((r) => r.data),

    /** Record the user's explicit consent (called before submitting a claim). */
    giveConsent: () =>
        api.post<{ message: string; version: string }>("/compliance/consent", {}).then((r) => r.data),

    /** Check whether the current user already has valid consent on record. */
    checkConsent: () =>
        api
            .get<{ has_valid_consent: boolean; consent_version: string; current_version: string }>("/compliance/consent")
            .then((r) => r.data),
};
