"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { createApiClient, type ApiClient } from "@/lib/api";

interface AuthState {
  apiKey: string;
  approverName: string;
  allowExternalProvider: boolean;
  connected: boolean;
}

interface AuthContextValue extends AuthState {
  setApiKey: (key: string) => void;
  setApproverName: (name: string) => void;
  setAllowExternalProvider: (allow: boolean) => void;
  setConnected: (connected: boolean) => void;
  api: ApiClient;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const STORAGE_KEY = "axioms_auth";

function loadAuth(): AuthState {
  if (typeof window === "undefined") {
    return { apiKey: "", approverName: "", allowExternalProvider: false, connected: false };
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return { ...parsed, connected: false };
    }
  } catch {
    // Ignore
  }
  return { apiKey: "", approverName: "", allowExternalProvider: false, connected: false };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(loadAuth);

  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          apiKey: state.apiKey,
          approverName: state.approverName,
          allowExternalProvider: state.allowExternalProvider,
        })
      );
    } catch {
      // Ignore
    }
  }, [state.apiKey, state.approverName, state.allowExternalProvider]);

  // Test connection on key change
  const api = useMemo(
    () =>
      createApiClient({
        apiKey: state.apiKey,
        allowExternalProvider: state.allowExternalProvider,
      }),
    [state.apiKey, state.allowExternalProvider]
  );

  useEffect(() => {
    if (!state.apiKey) {
      setState((s) => ({ ...s, connected: false }));
      return;
    }
    api
      .health()
      .then(() => setState((s) => ({ ...s, connected: true })))
      .catch(() => setState((s) => ({ ...s, connected: false })));
  }, [state.apiKey, api]);

  const setApiKey = useCallback((key: string) => setState((s) => ({ ...s, apiKey: key })), []);
  const setApproverName = useCallback(
    (name: string) => setState((s) => ({ ...s, approverName: name })),
    []
  );
  const setAllowExternalProvider = useCallback(
    (allow: boolean) => setState((s) => ({ ...s, allowExternalProvider: allow })),
    []
  );
  const setConnected = useCallback(
    (connected: boolean) => setState((s) => ({ ...s, connected })),
    []
  );

  const value = useMemo(
    () => ({
      ...state,
      setApiKey,
      setApproverName,
      setAllowExternalProvider,
      setConnected,
      api,
    }),
    [state, setApiKey, setApproverName, setAllowExternalProvider, setConnected, api]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
