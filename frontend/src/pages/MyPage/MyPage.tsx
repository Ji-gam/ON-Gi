import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import * as pointsApi from "@/api/points";
import type { BalanceResponse } from "@/api/pointTypes";
import * as trustApi from "@/api/trust";
import { useAuth } from "@/hooks/useAuth";

const MENU_ITEMS = [
  { to: "/guardian-profile", label: "보호자 프로필 수정" },
  { to: "/children", label: "아동 정보 관리" },
  { to: "/parenting-values", label: "양육 가치관 재진단" },
  { to: "/work-schedule", label: "근무표 수정" },
];

export default function MyPage() {
  const { user, accessToken, logout } = useAuth();
  const navigate = useNavigate();
  const [trustScore, setTrustScore] = useState<number | null>(null);
  const [balance, setBalance] = useState<BalanceResponse | null>(null);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  useEffect(() => {
    if (!accessToken || !user) return;
    trustApi
      .getScore(user.id, accessToken)
      .then((res) => setTrustScore(res.score))
      .catch(() => {});
    pointsApi
      .getBalance(accessToken)
      .then(setBalance)
      .catch(() => {});
  }, [accessToken, user]);

  async function handleLogout() {
    setIsLoggingOut(true);
    try {
      await logout();
    } finally {
      navigate("/home");
    }
  }

  if (!accessToken || !user) return null;

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-4">
        <h1 className="text-sm font-medium text-foreground">MY</h1>

        <section className="flex flex-col gap-2.5 rounded-2xl border border-border bg-secondary p-4">
          <div className="text-sm font-medium text-foreground">{user.nickname}님</div>
          <div className="flex justify-between text-xs text-foreground">
            <span className="text-muted-foreground">신뢰 점수</span>
            <span>{trustScore !== null ? `${Math.round(trustScore * 100)}점` : "-"}</span>
          </div>
          <div className="flex justify-between text-xs text-foreground">
            <span className="text-muted-foreground">포인트 잔액</span>
            <span>{balance ? `${balance.balance}P` : "-"}</span>
          </div>
        </section>

        <section className="flex flex-col gap-2">
          {MENU_ITEMS.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className="rounded-xl border border-border bg-secondary px-4 py-3 text-xs font-medium text-foreground"
            >
              {item.label}
            </Link>
          ))}
        </section>

        <button
          type="button"
          disabled={isLoggingOut}
          onClick={handleLogout}
          className="rounded-lg border border-border bg-background px-3 py-3 text-sm font-medium text-destructive disabled:opacity-60"
        >
          {isLoggingOut ? "로그아웃 중..." : "로그아웃"}
        </button>
      </div>
    </main>
  );
}
