import api from "./api";
import type {
    CashlessQRRequest,
    CashlessQRResponse,
    CashlessScanResponse,
    CashlessAcceptRequest,
    CashlessAcceptResponse,
    CashlessAuthorizationRequest,
    CashlessAuthorizationResponse,
    CashlessPendingItem,
    NetworkClaimsResponse,
} from "@/types";

const cashlessService = {
    /** Provider: list network cashless claims assigned to this hospital */
    getNetworkClaims: () =>
        api.get<NetworkClaimsResponse>("/cashless/network-claims").then((r) => r.data),

    /** Provider: generate a QR code for a cashless claim */
    generateQR: (data: CashlessQRRequest) =>
        api.post<CashlessQRResponse>("/cashless/generate-qr", data).then((r) => r.data),

    /** Customer: scan a QR token and return estimate details */
    scanQR: (token: string) =>
        api.get<CashlessScanResponse>(`/cashless/scan/${token}`).then((r) => r.data),

    /** Customer: accept the cashless estimate */
    acceptEstimate: (data: CashlessAcceptRequest) =>
        api.post<CashlessAcceptResponse>("/cashless/accept", data).then((r) => r.data),

    /** Insurer: list all pending cashless authorizations */
    getPendingAuthorizations: () =>
        api.get<CashlessPendingItem[]>("/cashless/pending-authorizations").then((r) => r.data),

    /** Insurer: pre-authorize or reject a cashless claim */
    preAuthorize: (data: CashlessAuthorizationRequest) =>
        api.post<CashlessAuthorizationResponse>("/cashless/pre-authorize", data).then((r) => r.data),
};

export default cashlessService;
