// SessionContext — real session state from GET /api/auth/me (T041, R-7, FR-015).
//
// Replaces the spec 001 in-memory placeholder. On mount, bootstraps from
// /api/auth/me: 200 → {authenticated: true, userId}; 401 → {authenticated: false}.
// Exposes login(userId) and logout() actions + useSession() hook.

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api } from "../services/api";

export interface SessionContextValue {
  authenticated: boolean;
  userId: string | null;
  loading: boolean;
  login: (userId: string) => void;
  logout: () => Promise<void>;
  /** Clear in-memory session state WITHOUT calling /api/auth/logout (spec 006,
   * research R-6). Used after face-data deletion: the session is already
   * destroyed by the deletion transaction, so calling logout would hit a
   * deleted session. */
  clearSession: () => void;
}

const SessionContext = createContext<SessionContextValue | undefined>(undefined);

interface SessionProviderProps {
  children: React.ReactNode;
  /** Initial authenticated flag (default false). Used in tests to skip the bootstrap fetch. */
  initialAuthenticated?: boolean;
  /** Initial userId for tests. */
  initialUserId?: string | null;
  /** Skip the bootstrap fetch (tests). */
  skipBootstrap?: boolean;
}

export const SessionProvider: React.FC<SessionProviderProps> = ({
  children,
  initialAuthenticated = false,
  initialUserId = null,
  skipBootstrap = false,
}) => {
  const [authenticated, setAuthenticated] = useState<boolean>(initialAuthenticated);
  const [userId, setUserId] = useState<string | null>(initialUserId);
  const [loading, setLoading] = useState<boolean>(!skipBootstrap && !initialAuthenticated);

  // Bootstrap from GET /api/auth/me on mount (unless skipped / pre-authed for tests).
  useEffect(() => {
    if (skipBootstrap || initialAuthenticated) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const me = await api.getMe();
        if (!cancelled) {
          setAuthenticated(me.authenticated);
          setUserId(me.userId);
        }
      } catch {
        if (!cancelled) {
          setAuthenticated(false);
          setUserId(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [skipBootstrap, initialAuthenticated]);

  const login = useCallback((uid: string) => {
    setAuthenticated(true);
    setUserId(uid);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // Best-effort; always clear local state.
    }
    setAuthenticated(false);
    setUserId(null);
  }, []);

  // Spec 006 (T020, research R-6): clear session state without calling /logout.
  // The deletion transaction already destroyed the AuthSession; calling logout
  // would hit a deleted session. Only local state is cleared.
  const clearSession = useCallback(() => {
    setAuthenticated(false);
    setUserId(null);
  }, []);

  const value = useMemo<SessionContextValue>(
    () => ({ authenticated, userId, loading, login, logout, clearSession }),
    [authenticated, userId, loading, login, logout, clearSession],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
};

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (ctx === undefined) {
    throw new Error("useSession must be used within a SessionProvider");
  }
  return ctx;
}

export default SessionContext;
