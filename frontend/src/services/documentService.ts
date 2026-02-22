import api from "./api";
import type { ClaimDocumentListResponse, ClaimDocumentResponse } from "@/types";

export type InlineOcrResult = {
    is_relevant: boolean;
    reason: string;
    detected_type: string;
    extracted_fields: Record<string, unknown>;
    completeness: number;
    missing_fields: string[];
};

export const documentService = {
    /**
     * Combined relevance check + full OCR extraction in one LLM call.
     * No DB writes — returns extracted fields immediately for inline editing.
     */
    inlineOcr: (
        file: File,
        documentTypeCode: string,
        claimType: string,
        requirementId?: string,
    ) => {
        const form = new FormData();
        form.append("file", file);
        form.append("document_type_code", documentTypeCode);
        form.append("claim_type", claimType);
        if (requirementId) form.append("requirement_id", requirementId);
        return api.post<InlineOcrResult>(
            `/claim-documents/inline-ocr`, form, {
                headers: { "Content-Type": "multipart/form-data" },
                timeout: 60_000,
            }
        ).then((r) => r.data);
    },

    /**
     * Upload a document using the ClaimDocument model.
     * If precomputedData is provided the backend saves it directly (no background OCR).
     */
    uploadClaimDoc: (
        claimId: string,
        file: File,
        documentTypeCode: string,
        requirementId?: string,
        precomputedData?: Record<string, unknown>,
    ) => {
        const form = new FormData();
        form.append("file", file);
        form.append("document_type_code", documentTypeCode);
        form.append("claim_id", claimId);
        if (requirementId) form.append("document_requirement_id", requirementId);
        if (precomputedData && Object.keys(precomputedData).length > 0) {
            form.append("precomputed_data", JSON.stringify(precomputedData));
        }
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
