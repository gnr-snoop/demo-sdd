import React, { createContext, useContext, useMemo, useState } from "react";

export interface SessionContextValue {
  isAuthenticated: boolean;
  setAuthenticated: (value: boolean) => void;
}

const SessionContext = createContext<SessionContextValue | undefined>(undefined);

interface SessionProviderProps {
  children: React.ReactNode;
  /** Initial authentication flag (default false). Used in tests. */
  initialAuthenticated?: boolean;
}

export const SessionProvider: React.FC<SessionProviderProps> = ({
  children,
  initialAuthenticated = false,
}) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(initialAuthenticated);

  const value = useMemo<SessionContextValue>(
    () => ({ isAuthenticated, setAuthenticated: setIsAuthenticated }),
    [isAuthenticated],
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
