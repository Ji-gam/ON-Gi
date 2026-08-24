import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import * as matchingApi from "@/api/matching";
import type { CandidateResponse } from "@/api/matchingTypes";
import { useAuth } from "@/hooks/useAuth";

function ScoreBar({ label, value }: { label: string; value: number }) {
  const percent = Math.round(value * 100);
  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between text-[11px] text-muted-foreground">
        <span>{label}</span>
        <span className="font-medium text-foreground">{percent}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-background">
        <div className="h-full bg-primary" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

export default function MatchingDetailPage() {
  const { userId } = useParams();
  const { accessToken } = useAuth();
  const navigate = useNavigate();
  const [candidate, setCandidate] = useState<CandidateResponse | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken) return;
    matchingApi
      .getCandidates(accessToken)
      .then((candidates) => {
        setCandidate(candidates.find((c) => String(c.user_id) === userId) ?? null);
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "후보 정보를 불러오지 못했습니다."),
      );
  }, [accessToken, userId]);

  if (!accessToken) return null;

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-5 pb-24">
        <Link to="/matching" className="text-xs text-muted-foreground">
          ← 매칭 후보 목록
        </Link>

        {error && (
          <p className="rounded-lg bg-destructive/10 px-3 py-2.5 text-xs text-destructive">
            {error}
          </p>
        )}

        {candidate === undefined && !error && (
          <p className="text-xs text-muted-foreground">불러오는 중...</p>
        )}

        {candidate === null && !error && (
          <p className="text-xs text-muted-foreground">
            더 이상 후보 목록에 없는 이웃이에요. 근무표가 바뀌었거나 조건이 달라졌을 수 있어요.
          </p>
        )}

        {candidate && (
          <>
            <section className="flex flex-col gap-3 rounded-2xl border border-border bg-secondary p-4">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary text-base font-bold text-primary-foreground">
                  {candidate.nickname.slice(0, 1)}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-foreground">{candidate.nickname}님</div>
                  <div className="text-[11px] text-muted-foreground">
                    도보 {Math.round(candidate.distance_m / 80)}분 · 아동 개월 수 유사도{" "}
                    {Math.round(candidate.age_similarity * 100)}%
                  </div>
                </div>
                <span className="shrink-0 rounded-lg bg-primary px-2.5 py-1.5 text-xs font-bold text-primary-foreground">
                  {Math.round(candidate.total_score * 100)}점
                </span>
              </div>
            </section>

            <section className="flex flex-col gap-2 rounded-2xl border border-border bg-secondary p-4">
              <h2 className="text-xs font-medium text-muted-foreground">추천 근거</h2>
              <p className="text-sm leading-relaxed text-foreground">“{candidate.reason}”</p>
            </section>

            <section className="flex flex-col gap-3 rounded-2xl border border-border bg-secondary p-4">
              <h2 className="text-xs font-medium text-muted-foreground">매칭 지표</h2>
              <ScoreBar label="가치관 유사도" value={candidate.values_similarity} />
              <ScoreBar label="상보 스코어" value={candidate.complementary_score} />
            </section>

            <section className="flex flex-col gap-2.5 rounded-2xl border border-border bg-secondary p-4">
              <h2 className="text-xs font-medium text-muted-foreground">신뢰 정보</h2>
              <div className="flex items-center justify-between text-xs text-foreground">
                <span>평균 별점</span>
                <span className="font-medium">
                  {candidate.average_rating != null
                    ? `★ ${candidate.average_rating.toFixed(1)}`
                    : "아직 평가 없음"}
                </span>
              </div>
              {candidate.top_tags.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {candidate.top_tags.map((tag) => (
                    <span
                      key={tag}
                      className="rounded-full bg-background px-2.5 py-1 text-[11px] text-foreground"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </div>

      {candidate && (
        <div className="fixed inset-x-0 bottom-0 flex justify-center bg-background px-6 py-4">
          <button
            type="button"
            onClick={() =>
              navigate(
                `/care/requests/new?providerId=${candidate.user_id}&nickname=${encodeURIComponent(candidate.nickname)}`,
              )
            }
            className="w-full max-w-[480px] rounded-lg border-0 bg-primary py-3 text-sm font-medium text-primary-foreground"
          >
            매칭 요청 보내기
          </button>
        </div>
      )}
    </main>
  );
}
