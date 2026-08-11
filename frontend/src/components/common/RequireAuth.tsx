import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";

// 로그인 필요 라우트 공통 게이트 — 미로그인 시 /login으로 보내고, 로그인 후 원래 경로로 복귀시킨다.
export default function RequireAuth() {
  const { accessToken } = useAuth();
  const location = useLocation();

  if (!accessToken) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <Outlet />;
}
