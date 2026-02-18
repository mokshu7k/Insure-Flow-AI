import api from "./api";
import type { AuditLogEntry, AccessLogEntry, ConsentRecord } from "@/types";

export const complianceService = {
    async getConsentText(): Promise<{ version: string; text: string }> {
        const res = await api.get("/compliance/consent/text");
        return res.data;
    },

    async giveConsent(): Promise<{ message: string; consent_id: string }> {
        const res = await api.post("/compliance/consent/give", { confirm: true });
        return res.data;
    },

    async getConsentStatus(): Promise<{ has_valid_consent: boolean; can_submit_claims: boolean }> {
        const res = await api.get("/compliance/consent/status");
        return res.data;
    },

    async getConsentHistory(): Promise<ConsentRecord[]> {
        const res = await api.get<ConsentRecord[]>("/compliance/consent/history");
        return res.data;
    },

    async getAuditTrail(params?: {
        entity_type?: string;
        entity_id?: string;
        limit?: number;
    }): Promise<AuditLogEntry[]> {
        const res = await api.get<AuditLogEntry[]>("/compliance/audit/trail", { params });
        return res.data;
    },

    async getDocumentAccessLog(documentId: string): Promise<AccessLogEntry[]> {
        const res = await api.get<AccessLogEntry[]>(`/compliance/access-log/document/${documentId}`);
        return res.data;
    },

    async requestDeletion(reason: string): Promise<Record<string, unknown>> {
        const res = await api.post("/compliance/deletion-request", { reason });
        return res.data;
    },
};
