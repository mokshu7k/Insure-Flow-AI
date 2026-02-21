import api from "./api";
import type { ClaimDocumentListResponse, ClaimDocumentResponse } from "@/types";

export const documentService = {
    /** Upload a document using the ClaimDocument model (template-aware OCR) */
    uploadClaimDoc: (claimId: string, file: File, documentTypeCode: string, requirementId?: string) => {
        const form = new FormData();
        form.append("file", file);
        form.append("document_type_code", documentTypeCode);
        form.append("claim_id", claimId);
        if (requirementId) form.append("document_requirement_id", requirementId);
        return api.post<ClaimDocumentResponse>(`/claim-documents`, form, {
            headers: { "Content-Type": "multipart/form-data" },
            timeout: 120_000,
        }).then((r) => r.data);
    },

    /** List ClaimDocuments for a claim (new model) */
    listClaimDocs: (claimId: string) =>
        api.get<ClaimDocumentListResponse>(`/claim-documents`, { params: { claim_id: claimId } }).then((r) => r.data.items),

    /** Update extracted data for a ClaimDocument (manual correction) */
    updateClaimDocData: (docId: string, extractedData: Record<string, unknown>) =>
        api.patch<ClaimDocumentResponse>(`/claim-documents/${docId}/extracted-data`, {
            extracted_data: extractedData,
        }).then((r) => r.data),
};
