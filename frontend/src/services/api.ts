import axios from "axios";

// In dev, Next.js rewrites /api/* → http://localhost:8000/api/*
// So we always call same-origin /api — no CORS, no credential issues.
const BASE = "/api";

const api = axios.create({
    baseURL: BASE,
    headers: { "Content-Type": "application/json" },
    withCredentials: false,
});

// ── Attach token ─────────────────────────────────────────
api.interceptors.request.use((config) => {
    if (typeof window !== "undefined") {
        const token = localStorage.getItem("access_token");
        if (token) config.headers.Authorization = `Bearer ${token}`;
    }
    console.debug("[api] →", config.method?.toUpperCase(), config.url, config.data ?? "");
    return config;
});

// ── 401 refresh ───────────────────────────────────────────
let isRefreshing = false;
let failedQueue: Array<{ resolve: (v: unknown) => void; reject: (e: unknown) => void }> = [];

function processQueue(error: unknown, token: string | null = null) {
    failedQueue.forEach(({ resolve, reject }) => {
        if (error) reject(error);
        else resolve(token);
    });
    failedQueue = [];
}

api.interceptors.response.use(
    (res) => {
        console.debug("[api] ←", res.status, res.config.url, res.data);
        return res;
    },
    async (error) => {
        // Ignore cancelled/aborted requests (happens during navigation)
        if (axios.isCancel(error) || error.code === "ERR_CANCELED" || error.code === "ERR_NETWORK") {
            return Promise.reject(error);
        }

        const original = error.config;
        const status = error.response?.status;

        // Never try to refresh on auth endpoints — just let the error propagate
        const isAuthEndpoint =
            original?.url?.includes("/auth/login") ||
            original?.url?.includes("/auth/register") ||
            original?.url?.includes("/auth/refresh");

        // Attempt token refresh on 401 (once only, not on auth endpoints themselves)
        if (status === 401 && !original._retry && !isAuthEndpoint) {
            if (isRefreshing) {
                return new Promise((resolve, reject) => {
                    failedQueue.push({ resolve, reject });
                }).then((token) => {
                    original.headers.Authorization = `Bearer ${token}`;
                    return api(original);
                });
            }
            original._retry = true;
            isRefreshing = true;
            try {
                const refresh = localStorage.getItem("refresh_token");
                if (!refresh) throw new Error("No refresh token");
                const { data } = await axios.post(`${BASE}/auth/refresh`, { refresh_token: refresh });
                localStorage.setItem("access_token", data.access_token);
                localStorage.setItem("refresh_token", data.refresh_token);
                api.defaults.headers.common.Authorization = `Bearer ${data.access_token}`;
                processQueue(null, data.access_token);
                original.headers.Authorization = `Bearer ${data.access_token}`;
                // Retry original request silently — do NOT log the original 401
                return api(original);
            } catch (err) {
                processQueue(err, null);
                localStorage.removeItem("access_token");
                localStorage.removeItem("refresh_token");
                console.error("[api] ✗ session expired, redirecting to login");
                if (typeof window !== "undefined") window.location.href = "/login";
                return Promise.reject(err);
            } finally {
                isRefreshing = false;
            }
        }

        // Log only errors that are NOT handled by the refresh flow above
        console.error("[api] ✗", status, original?.url, error.response?.data ?? error.message);
        return Promise.reject(error);
    }
);

export default api;
