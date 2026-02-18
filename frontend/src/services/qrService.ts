import api from "./api";
import type {
    QRAuthorizationCreate,
    QRAuthorizationResponse,
    QRValidationRequest,
    QRValidationResponse,
} from "@/types";

export const qrService = {
    async createAuthorization(data: QRAuthorizationCreate): Promise<QRAuthorizationResponse> {
        const res = await api.post<QRAuthorizationResponse>("/qr/authorize", data);
        return res.data;
    },

    async validate(data: QRValidationRequest): Promise<QRValidationResponse> {
        const res = await api.post<QRValidationResponse>("/qr/validate", data);
        return res.data;
    },
};
