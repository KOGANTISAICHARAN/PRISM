"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { api, clearSession, getToken, readStoredUser, storeSession } from "./api";
import type { SessionUser } from "./types";

interface AuthState {
  user: SessionUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<SessionUser>;
  register: (payload: { email: string; password: string; name: string; phone?: string; role?: string }) => Promise<SessionUser>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const stored = readStoredUser();
    if (stored && getToken()) {
      setUser(stored);
      api
        .me()
        .then((fresh) => setUser({ id: fresh.id, email: fresh.email, name: fresh.name, role: fresh.role }))
        .catch(() => {
          clearSession();
          setUser(null);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.login(email, password);
    storeSession(res.access_token, res.user);
    setUser(res.user);
    return res.user;
  }, []);

  const register = useCallback(
    async (payload: { email: string; password: string; name: string; phone?: string; role?: string }) => {
      const res = await api.register(payload);
      storeSession(res.access_token, res.user);
      setUser(res.user);
      return res.user;
    },
    [],
  );

  const logout = useCallback(() => {
    clearSession();
    setUser(null);
    router.push("/");
  }, [router]);

  const value = useMemo(() => ({ user, loading, login, register, logout }), [user, loading, login, register, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

export function useRequireAuth(role?: "citizen" | "inspector") {
  const { user, loading } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (loading) return;
    if (!user) router.replace(`/login?next=${encodeURIComponent(window.location.pathname)}`);
    else if (role && user.role !== role) router.replace(user.role === "inspector" ? "/inspector" : "/");
  }, [user, loading, role, router]);
  return { user, loading };
}
