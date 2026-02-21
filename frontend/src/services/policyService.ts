import api from "./api";
import type { DocumentRequirementsListResponse, Policy, PolicyListResponse } from "@/types";

export const policyService = {
    listMine: () =>
        api.get<PolicyListResponse>("/policies").then((r) => r.data),

    get: (id: string) =>
        api.get<Policy>(`/policies/${id}`).then((r) => r.data),

    getDocumentRequirements: (policyId: string) =>
        api.get<DocumentRequirementsListResponse>(`/policies/${policyId}/document-requirements`).then((r) => r.data),
};
