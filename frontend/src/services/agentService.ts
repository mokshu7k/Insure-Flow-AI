import api from "./api";

const SESSION_KEY = "agent_session_id";

export interface AgentMessage {
    role: "user" | "agent";
    content: string;
    timestamp: Date;
}

export const agentService = {
    /** Get or create a persistent session id from localStorage */
    getSessionId(): string | null {
        if (typeof window === "undefined") return null;
        return localStorage.getItem(SESSION_KEY);
    },

    /** Create a new session and persist its id */
    async createSession(): Promise<string> {
        const { data } = await api.post<{ session_id: string; message: string }>("/agent/sessions");
        localStorage.setItem(SESSION_KEY, data.session_id);
        return data.session_id;
    },

    /** Send a message to an existing session, creating one if needed */
    async sendMessage(
        message: string,
        sessionId?: string | null
    ): Promise<{ session_id: string; reply: string; intent?: string | null }> {
        let sid = sessionId ?? agentService.getSessionId();
        if (!sid) {
            sid = await agentService.createSession();
        }
        const { data } = await api.post<{ session_id: string; reply: string; intent?: string | null }>(
            `/agent/sessions/${sid}/message`,
            { message }
        );
        // Refresh stored session id in case it changed
        localStorage.setItem(SESSION_KEY, data.session_id);
        return data;
    },

    /** Reset the local session (forces new session on next message) */
    clearSession(): void {
        if (typeof window !== "undefined") {
            localStorage.removeItem(SESSION_KEY);
        }
    },
};
