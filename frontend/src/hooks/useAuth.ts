/**
 * RetailFlow AI — useAuth Hook
 *
 * Handles:
 * 1. Session hydration on mount (GET /auth/me → if 401 → POST /auth/refresh → retry)
 * 2. Login action (calls API + updates store)
 * 3. Logout action (calls API + clears store)
 */
"use client";

import { useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";

import * as authApi from "@/lib/api/auth";
import { useAuthStore } from "@/store/authStore";
import { getApiErrorMessage } from "@/lib/api/client";

export function useAuth() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading, login, logout, setLoading } =
    useAuthStore();

  /**
   * Attempt to restore the session on mount.
   * Sequence: GET /auth/me → 401 → POST /auth/refresh → retry → still 401 → redirect /login
   */
  const hydrateSession = useCallback(async () => {
    setLoading(true);
    try {
      const meRes = await authApi.getMe();
      login(useAuthStore.getState().accessToken ?? "", meRes.data);
    } catch {
      // /me returned 401 — try refresh (uses httpOnly cookie automatically)
      try {
        const refreshRes = await authApi.refreshToken();
        login(refreshRes.data.access_token, refreshRes.data.user);
      } catch {
        // Both failed — user is not authenticated
        logout();
      }
    } finally {
      setLoading(false);
    }
  }, [login, logout, setLoading]);

  /** Login action: POST /auth/login → store token + user */
  const doLogin = useCallback(
    async (email: string, password: string): Promise<void> => {
      const res = await authApi.login({ email, password });
      login(res.data.access_token, res.data.user);
      router.push("/dashboard");
    },
    [login, router],
  );

  /** Logout action: POST /auth/logout → clear store → redirect /login */
  const doLogout = useCallback(async (): Promise<void> => {
    try {
      await authApi.logout();
    } catch {
      // swallow — always clear local state
    }
    logout();
    router.push("/login");
  }, [logout, router]);

  return {
    user,
    isAuthenticated,
    isLoading,
    hydrateSession,
    login: doLogin,
    logout: doLogout,
  };
}

/** Hook variant for the root layout: hydrates session once on mount. */
export function useSessionHydration() {
  const { hydrateSession } = useAuth();

  useEffect(() => {
    void hydrateSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}

/** Return only the error message string for error display. */
export function useApiError(error: unknown): string | null {
  if (!error) return null;
  return getApiErrorMessage(error);
}
