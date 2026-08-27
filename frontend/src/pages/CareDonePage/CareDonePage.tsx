import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import * as careApi from "@/api/care";
import type { CareSessionResponse } from "@/api/careTypes";
import * as pointsApi from "@/api/points";
import * as trustApi from "@/api/trust";
import { useAuth } from "@/hooks/useAuth";

export default function CareDonePage() {
  const { sessionId } = useParams();
  const { accessToken, user } = useAuth();

  const [careSession, setCareSession] = useState<CareSessionResponse | null>(null);
  const [balance, setBalance] = useState<number | null>(null);
  const [trustScore, setTrustScore] = useState<number | null>(null);
  const [completedCount, setCompletedCount] = useState<number | null>(null);
  const [soloCount, setSoloCount] = useState<number | null>(null);

  useEffect(() => {
    if (!accessToken || !sessionId || !user) return;
    careApi
      .getRequest(Number(sessionId), accessToken)
      .then(setCareSession)
      .catch(() => {});
    pointsApi
      .getBalance(accessToken)
      .then((res) => setBalance(res.balance))
      .catch(() => {});
    trustApi
      .getScore(user.id, accessToken)
      .then((res) => setTrustScore(res.score))
      .catch(() => {});
    // 누적 통계 API가 없어 내 세션 목록에서 직접 센다 — handoff B-3.
    careApi
      .listRequests(accessToken)
      .then((sessions) => {
        const done = sessions.filter((s) => s.checkout_at);
        setCompletedCount(done.length);
        setSoloCount(done.filter((s) => s.provider_id === user.id).length);
      })
      .catch(() => {});
  }, [accessToken, sessionId, user]);

  if (!accessToken) return null;

  const minutes = careSession?.actual_minutes ?? 0;
  const hours = Math.floor(minutes / 60);
  const restMinutes = minutes % 60;
  const durationLabel =
    hours > 0
      ? restMinutes > 0
        ? `${hours}시간 ${restMinutes}분`
        : `${hours}시간`
      : `${minutes}분`;
  const earnedSlots = Math.floor(minutes / 30);

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-5">
        <div className="flex flex-col items-center gap-3 pt-6">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-secondary">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="hsl(var(--primary))"
              strokeWidth={2}
              className="h-8 w-8"
            >
              <path d="m5 12.5 4.5 4.5L19 7.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <h1 className="text-lg font-bold text-foreground">{durationLabel} 돌봄이 끝났어요</h1>
          <p className="text-center text-[11px] leading-relaxed text-muted-foreground">
            돌봄일지가 제출되어 예치했던 노쇼 방지 포인트가 정산되었습니다.
          </p>
        </div>

        <div className="flex gap-2">
          <section className="flex-1 rounded-2xl bg-secondary p-4 text-center">
            <div className="text-[11px] text-muted-foreground">적립 포인트</div>
            <div className="mt-1 text-xl font-bold text-foreground">+{earnedSlots}P</div>
            <div className="mt-1 text-[10px] text-muted-foreground">{durationLabel} 기준</div>
          </section>
          <section className="flex-1 rounded-2xl border border-border bg-secondary p-4 text-center">
            <div className="text-[11px] text-muted-foreground">누적 돌봄</div>
            <div className="mt-1 text-xl font-bold text-foreground">
              {completedCount !== null ? `${completedCount}회` : "-"}
            </div>
            <div className="mt-1 text-[10px] text-muted-foreground">
              {soloCount !== null ? `내가 맡은 돌봄 ${soloCount}회` : ""}
            </div>
          </section>
        </div>

        <section className="flex flex-col gap-2.5 rounded-2xl border border-border bg-secondary p-4">
          <h2 className="text-xs font-semibold text-foreground">신뢰 프로필이 갱신되었습니다</h2>
          <div className="flex items-center justify-between text-xs text-foreground">
            <span className="text-muted-foreground">신뢰 점수</span>
            <span className="font-semibold">
              {trustScore !== null ? `${Math.round(trustScore * 100)}점` : "-"}
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-background">
            <div
              className="h-full bg-primary"
              style={{ width: `${Math.round((trustScore ?? 0) * 100)}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-xs text-foreground">
            <span className="text-muted-foreground">포인트 잔액</span>
            <span className="font-semibold">{balance !== null ? `${balance}P` : "-"}</span>
          </div>
        </section>

        <div className="flex flex-col gap-2">
          <Link
            to={`/care/requests/${sessionId}/review`}
            className="rounded-full border-0 bg-primary px-3 py-3 text-center text-sm font-semibold text-primary-foreground"
          >
            평가 남기기
          </Link>
          <Link
            to="/home"
            className="rounded-full border border-border bg-background px-3 py-3 text-center text-sm font-medium text-foreground"
          >
            홈으로
          </Link>
        </div>
      </div>
    </main>
  );
}
