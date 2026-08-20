import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import * as matchingApi from "@/api/matching";
import type { CandidateResponse } from "@/api/matchingTypes";
import { useAuth } from "@/hooks/useAuth";

export default function MatchingPage() {
  const { accessToken } = useAuth();
  const navigate = useNavigate();
  const [candidates, setCandidates] = useState<CandidateResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken) return;
    matchingApi
      .getCandidates(accessToken)
      .then(setCandidates)
      .catch((err) => setError(err instanceof Error ? err.message : "후보를 불러오지 못했습니다."));
  }, [accessToken]);

  if (!accessToken) return null;

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-4">
        <h1 className="text-center text-sm font-medium text-foreground">매칭 후보</h1>

        {candidates === null && !error && (
          <p className="text-xs text-muted-foreground">불러오는 중...</p>
        )}
        {error && (
          <p className="rounded-lg bg-destructive/10 px-3 py-2.5 text-xs text-destructive">
            {error}
          </p>
        )}
        {candidates && candidates.length === 0 && (
          <p className="text-xs text-muted-foreground">조건에 맞는 후보가 없습니다.</p>
        )}
        {candidates && candidates.length > 0 && (
          <>
            <p className="text-[11px] text-muted-foreground">
              추천순 정렬 · 총 {candidates.length}명
            </p>
            <ul className="flex flex-col gap-2.5">
              {candidates.map((candidate) => (
                <li
                  key={candidate.user_id}
                  className="flex flex-col gap-2.5 rounded-2xl border border-border bg-secondary p-3"
                >
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
                      {candidate.nickname.slice(0, 1)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-medium text-foreground">
                        {candidate.nickname}님 · 도보 {Math.round(candidate.distance_m / 80)}분
                      </div>
                      <div className="text-[11px] text-muted-foreground">
                        가치관 유사도 {(candidate.values_similarity * 100).toFixed(0)}% · 상보
                        스코어 {(candidate.complementary_score * 100).toFixed(0)}%
                      </div>
                    </div>
                    <span className="shrink-0 rounded-lg bg-primary px-2 py-1 text-[11px] font-bold text-primary-foreground">
                      {candidate.total_score.toFixed(0)}점
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      navigate(
                        `/care/requests/new?providerId=${candidate.user_id}&nickname=${encodeURIComponent(candidate.nickname)}`,
                      )
                    }
                    className="self-end rounded-lg bg-primary px-2.5 py-1.5 text-[11px] font-medium text-primary-foreground"
                  >
                    요청 보내기
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </main>
  );
}
