import api from "./api";
import type { LoginRequest, RegisterRequest, TokenResponse, User } from "@/types";

export const authService = {
    login: (data: LoginRequest) =>
        api.post<TokenResponse>("/auth/login", data).then((r) => r.data),


    register: (data: RegisterRequest) =>
        api.post<User>("/auth/register", data).then((r) => r.data),

    refresh: (refresh_token: string) =>
        api.post<TokenResponse>("/auth/refresh", { refresh_token }).then((r) => r.data),

    me: () => api.get<User>("/auth/me").then((r) => r.data),
};
