import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthState {
    token: string | null;
    role: "admin" | "regulator" | "public" | null;
    login: (token: string, role: "admin" | "regulator") => void;
    logout: () => void;
    isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>()(
    persist(
        (set, get) => ({
            token: null,
            role: null,
            login: (token, role) => set({ token, role }),
            logout: () => set({ token: null, role: null }),
            isAuthenticated: () => !!get().token,
        }),
        {
            name: "auth-storage",
        }
    )
);
