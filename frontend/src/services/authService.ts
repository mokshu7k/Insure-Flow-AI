import api from "./api";
import type { LoginRequest, RegisterRequest, TokenResponse, User } from "@/types";

export const authService = {
    async login(data: LoginRequest): Promise<TokenResponse> {
        const res = await api.post<TokenResponse>("/auth/login", data);
        return res.data;
    },

    async register(data: RegisterRequest): Promise<User> {
        const res = await api.post<User>("/auth/register", data);
        return res.data;
    },

    async refreshToken(refreshToken: string): Promise<TokenResponse> {
        const res = await api.post<TokenResponse>("/auth/refresh", {
            refresh_token: refreshToken,
        });
        return res.data;
    },

    async getMe(): Promise<User> {
        const res = await api.get<User>("/auth/me");
        return res.data;
    },
};
