import api from "./api";

const SESSION_KEY = "agent_session_id";

export interface AgentMessage {
    role: "user" | "agent";
    content: string;
    timestamp: Date;
}

export interface ChatSessionSummary {
    session_id: string;
    title: string;
    created_at: string | null;
    updated_at: string | null;
    last_message: string | null;
}

export interface ChatMessage {
    role: string;
    content: string;
}

export interface ChatSessionDetail {
    session_id: string;
    title: string;
    created_at: string | null;
    updated_at: string | null;
    messages: ChatMessage[];
}

export const agentService = {
    /** Get or create a persistent session id from localStorage */
    getSessionId(): string | null {
        if (typeof window === "undefined") return null;
        return localStorage.getItem(SESSION_KEY);
    },

    /** Create a new blank session */
    async createSession(): Promise<string> {
        const { data } = await api.post<{ session_id: string; message: string }>("/agent/sessions");
        return data.session_id;
    },

    /** List all sessions for the current user, newest first */
    async listSessions(): Promise<ChatSessionSummary[]> {
        const { data } = await api.get<ChatSessionSummary[]>("/agent/sessions");
        return data;
    },

    /** Get full conversation history for a session */
    async getSession(sessionId: string): Promise<ChatSessionDetail> {
        const { data } = await api.get<ChatSessionDetail>(`/agent/sessions/${sessionId}`);
        return data;
    },

    /** Rename a session */
    async renameSession(sessionId: string, title: string): Promise<ChatSessionSummary> {
        const { data } = await api.patch<ChatSessionSummary>(`/agent/sessions/${sessionId}`, { title });
        return data;
    },

    /** Delete a session */
    async deleteSession(sessionId: string): Promise<void> {
        await api.delete(`/agent/sessions/${sessionId}`);
    },

    /** Send a message to an existing session */
    async sendMessage(
        message: string,
        sessionId: string
    ): Promise<{ session_id: string; reply: string; intent?: string | null }> {
        const { data } = await api.post<{ session_id: string; reply: string; intent?: string | null }>(
            `/agent/sessions/${sessionId}/message`,
            { message }
        );
        return data;
    },

    /** @deprecated Use explicit sessionId — kept for backward compat */
    clearSession(): void {
        if (typeof window !== "undefined") {
            localStorage.removeItem(SESSION_KEY);
        }
    },
};
