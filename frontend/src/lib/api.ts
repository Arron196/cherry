import axios, { AxiosError } from "axios";
import { useAuthStore } from "@/hooks/use-auth";
import { ProblemDetails } from "@/types/api";

const CONFIGURED_API_BASE_URL = process.env.NEXT_PUBLIC_API_URL?.trim();

function inferApiBaseUrl(): string {
    if (CONFIGURED_API_BASE_URL) {
        return CONFIGURED_API_BASE_URL;
    }

    if (typeof window === "undefined") {
        return "http://localhost:18941";
    }

    return "/api/backend";
}

const API_BASE_URL = inferApiBaseUrl();

const PROTECTED_API_PREFIXES = [
    "/admin/",
    "/v1/alerts",
    "/v1/devices",
    "/v1/simulation",
    "/metrics",
];

function requiresAuth(path: string | undefined): boolean {
    if (!path) return false;
    return PROTECTED_API_PREFIXES.some((prefix) => path.startsWith(prefix));
}

export const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        "Content-Type": "application/json",
    },
});

// Request Interceptor: Attach Token & Mock
api.interceptors.request.use((config) => {
    // We use getState() to access the store outside of a component
    const token = useAuthStore.getState().token;
    if (token && requiresAuth(config.url)) {
        config.headers.Authorization = `Bearer ${token}`;
    } else if (config.headers?.Authorization) {
        delete config.headers.Authorization;
    }
    return config;
});

// Response Interceptor: Error Normalization
api.interceptors.response.use(
    (response) => response,
    (error: AxiosError) => {
        if (error.response) {
            const data = error.response.data as ProblemDetails;

            // Normalize to a consistent error object
            const normalizedError = {
                status: error.response.status,
                type: data.type || "about:blank",
                title: data.title || "Unknown Error",
                detail: data.detail || "An unexpected error occurred",
                instance: data.instance || error.config?.url,
            };

            // Handle 401 - Unauthorized (Clear Token)
            if (error.response.status === 401) {
                useAuthStore.getState().logout();
                // Optional: Redirect to login or show toast
                // window.location.href = '/login'; 
            }

            return Promise.reject(normalizedError);
        }

        // Network Error or no response
        return Promise.reject({
            status: 0,
            title: "Network Error",
            detail: "Could not connect to the server. Please check your connection.",
        });
    }
);
