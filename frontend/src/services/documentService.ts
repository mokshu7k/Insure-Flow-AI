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

    /**
     * Download a claim document (streams via backend, accessible to the
     * document owner, admins and adjusters).
     * Triggers a browser file-save automatically.
     */
    downloadClaimDoc: async (docId: string, filename?: string): Promise<void> => {
        const response = await api.get(`/claim-documents/${docId}/download`, {
            responseType: "blob",
            timeout: 60_000,
        });
        const contentDisposition: string = response.headers["content-disposition"] ?? "";
        const matched = contentDisposition.match(/filename="([^"]+)"/);
        const name = filename ?? matched?.[1] ?? `document-${docId}`;
        const url = URL.createObjectURL(response.data as Blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = name;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    },

    /**
     * Request a signed GCS download URL for a document (admin / adjuster only).
     * Returns the signed URL, or null if GCS signed URLs are unavailable
     * (caller should fall back to downloadClaimDoc in that case).
     */
    getDocumentDownloadUrl: (docId: string) =>
        api.get<{ doc_id: string; gcs_path: string | null; download_url: string | null; fallback_endpoint: string; original_filename: string | null }>(
            `/claim-documents/${docId}/download-url`
        ).then((r) => r.data),
};
