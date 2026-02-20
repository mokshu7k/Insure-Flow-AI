import api from "./api";
import type { DocumentResponse } from "@/types";

export const documentService = {
    /** List all documents attached to a claim */
    listForClaim: (claimId: string) =>
        api.get<DocumentResponse[]>(`/documents`, { params: { claim_id: claimId } }).then((r) => r.data),

    /** Upload a document and attach it to a claim */
    upload: (claimId: string, file: File, documentType: string) => {
        const form = new FormData();
        form.append("file", file);
        form.append("document_type", documentType);
        form.append("claim_id", claimId);
        return api.post<DocumentResponse>(`/documents`, form, {
            headers: { "Content-Type": "multipart/form-data" },
        }).then((r) => r.data);
    },

    /** Update extracted data for a document */
    updateExtractedData: (documentId: string, extractedData: Record<string, unknown>, requiresManualReview?: boolean) =>
        api.patch<DocumentResponse>(`/documents/${documentId}/extracted-data`, {
            extracted_data: extractedData,
            requires_manual_review: requiresManualReview,
        }).then((r) => r.data),
};
