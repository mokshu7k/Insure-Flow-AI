import api from "./api";
import type { User } from "@/types";

export const userService = {
    async list(params?: {
        role?: string;
        is_active?: boolean;
        skip?: number;
        limit?: number;
    }): Promise<User[]> {
        const res = await api.get<User[]>("/users/", { params });
        return res.data;
    },

    async getById(id: string): Promise<User> {
        const res = await api.get<User>(`/users/${id}`);
        return res.data;
    },

    async deactivate(id: string): Promise<{ message: string }> {
        const res = await api.put(`/users/${id}/deactivate`);
        return res.data;
    },

    async activate(id: string): Promise<{ message: string }> {
        const res = await api.put(`/users/${id}/activate`);
        return res.data;
    },
};
