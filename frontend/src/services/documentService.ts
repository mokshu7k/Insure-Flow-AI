import api from "./api";
import type { DocumentResponse, OCRResult } from "@/types";

export const documentService = {
    async upload(claimId: string, file: File, documentType: string): Promise<DocumentResponse> {
        const form = new FormData();
        form.append("file", file);
        form.append("document_type", documentType);
        const res = await api.post<DocumentResponse>(`/documents/${claimId}/upload`, form, {
            headers: { "Content-Type": "multipart/form-data" },
        });
        return res.data;
    },

    async listByClaimId(claimId: string): Promise<DocumentResponse[]> {
        const res = await api.get<DocumentResponse[]>(`/documents/claim/${claimId}`);
        return res.data;
    },

    async download(documentId: string): Promise<Blob> {
        const res = await api.get(`/documents/${documentId}/download`, { responseType: "blob" });
        return res.data;
    },

    async getOCR(documentId: string): Promise<OCRResult> {
        const res = await api.get<OCRResult>(`/documents/${documentId}/ocr`);
        return res.data;
    },
};
