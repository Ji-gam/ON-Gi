import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import * as matchingApi from "@/api/matching";
import type { CandidateResponse } from "@/api/matchingTypes";
import { useAuth } from "@/hooks/useAuth";

export default function HomePage() {
  const { user, accessToken } = useAuth();
  const [topCandidate, setTopCandidate] = useState<CandidateResponse | null>(null);

  useEffect(() => {
    if (!accessToken) return;
    matchingApi
      .getCandidates(accessToken)
      .then((candidates) => setTopCandidate(candidates[0] ?? null))
      .catch(() => setTopCandidate(null));
  }, [accessToken]);

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-3">
        <h1 className="text-base font-medium text-foreground">
          {user ? `${user.nickname}님, 안녕하세요` : "안녕하세요"}
        </h1>

        <section className="rounded-2xl border border-border bg-secondary p-3.5">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-xs font-semibold text-foreground">추천 이웃</h2>
            <Link to="/matching" className="text-[11px] font-semibold text-primary">
              더 보기
            </Link>
          </div>
          {topCandidate ? (
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
                {topCandidate.nickname.slice(0, 1)}
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-xs font-medium text-foreground">
                  {topCandidate.nickname}님 · 도보 {Math.round(topCandidate.distance_m / 80)}분
                </div>
              </div>
              <span className="shrink-0 rounded-lg bg-primary px-2 py-1 text-[11px] font-bold text-primary-foreground">
                {topCandidate.total_score.toFixed(0)}점
              </span>
            </div>
          ) : (
            <p className="text-[11px] text-muted-foreground">아직 추천할 이웃이 없어요.</p>
          )}
        </section>

        <section className="rounded-2xl border border-border bg-secondary p-3.5">
          <h2 className="mb-1 text-xs font-semibold text-foreground">예정된 돌봄</h2>
          <p className="text-[11px] text-muted-foreground">연동 준비 중입니다.</p>
        </section>

        <section className="rounded-2xl border border-border bg-secondary p-3.5">
          <h2 className="mb-1 text-xs font-semibold text-foreground">신뢰 단계</h2>
          <p className="text-[11px] text-muted-foreground">연동 준비 중입니다.</p>
        </section>

        <section className="flex items-center justify-between rounded-2xl border border-border bg-secondary p-3.5">
          <div>
            <div className="text-[11px] text-muted-foreground">포인트 잔액</div>
            <div className="text-sm font-semibold text-muted-foreground">연동 준비 중</div>
          </div>
        </section>
      </div>
    </main>
  );
}
