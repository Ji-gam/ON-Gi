import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

import * as authApi from "@/api/auth";
import type { AuthResponse, AuthUser } from "@/api/types";

interface AuthContextValue {
  user: AuthUser | null;
  // 메모리에만 보관 — localStorage/sessionStorage 저장 금지(CODING_RULES.md §3, XSS 방어).
  accessToken: string | null;
  login: (email: string, password: string) => Promise<void>;
  // 회원가입 응답도 로그인과 같은 AuthResponse 형태로 토큰을 함께 내려준다(auth_kit 설계) — 재로그인 불필요.
  applySession: (result: AuthResponse) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      accessToken,
      login: async (email, password) => {
        const result = await authApi.login({ email, password });
        setUser(result.user);
        setAccessToken(result.access_token);
      },
      applySession: (result) => {
        setUser(result.user);
        setAccessToken(result.access_token);
      },
    }),
    [user, accessToken],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth는 AuthProvider 내부에서만 사용할 수 있습니다.");
  return context;
}
