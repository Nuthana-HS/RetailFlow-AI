/**
 * RetailFlow AI — Auth Zustand Store
 *
 * Stores the access token in-memory only (never localStorage).
 * The refresh token lives in the httpOnly `rf_token` cookie managed by the browser.
 *
 * On app mount, `useAuth` hook calls /auth/me → if 401 → /auth/refresh → retry.
 */
import { create } from "zustand";
import type { User } from "@/types/auth";
import { initApiClient } from "@/lib/api/client";

interface AuthState {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  // Actions
  login: (token: string, user: User) => void;
  logout: () => void;
  setToken: (token: string) => void;
  setUser: (user: User) => void;
  setLoading: (loading: boolean) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: null,
  isAuthenticated: false,
  isLoading: true,

  login: (token, user) => {
    set({ accessToken: token, user, isAuthenticated: true, isLoading: false });
  },

  logout: () => {
    set({ accessToken: null, user: null, isAuthenticated: false, isLoading: false });
  },

  setToken: (token) => {
    set({ accessToken: token, isAuthenticated: true });
  },

  setUser: (user) => {
    set({ user });
  },

  setLoading: (loading) => {
    set({ isLoading: loading });
  },
}));

/**
 * Wire the Axios client interceptors to the auth store.
 * Call this once from the root Providers component.
 */
export function bootstrapApiClient(): void {
  initApiClient({
    getToken: () => useAuthStore.getState().accessToken,
    setToken: (token) => useAuthStore.getState().setToken(token),
    onUnauthenticated: () => {
      useAuthStore.getState().logout();
      // Redirect is handled by the middleware + useAuth hook
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    },
  });
}
