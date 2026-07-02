import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, setToken, type User } from "./api";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string, rememberMe?: boolean) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    try {
      const u = await api.me();
      setUser(u);
    } catch {
      setUser(null);
      setToken(null);
    }
  };

  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, []);

  const login = async (username: string, password: string, rememberMe = true) => {
    const { access_token } = await api.login({ username, password, remember_me: rememberMe });
    setToken(access_token, rememberMe);
    await refresh();
  };

  const register = async (username: string, email: string, password: string) => {
    await api.register({ username, email, password });
    await login(username, password);
  };

  const logout = () => {
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function isMod(user: User | null) {
  return user?.role === "mod" || user?.role === "admin" || user?.is_auto_editor;
}

export function isAdmin(user: User | null) {
  return user?.role === "admin";
}

export function canSubmit(user: User | null) {
  return !!user?.can_submit;
}

export function isVoteOnly(user: User | null) {
  return !!user && user.access_level === "vote_only" && !user.can_submit;
}

export function isEmailVerified(user: User | null) {
  return !!user?.email_verified;
}
