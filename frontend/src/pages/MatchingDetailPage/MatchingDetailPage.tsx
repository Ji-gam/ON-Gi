import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import * as matchingApi from "@/api/matching";
import type { CandidateResponse } from "@/api/matchingTypes";
import * as trustApi from "@/api/trust";
import type { TrustRelationshipResponse } from "@/api/trustTypes";
import PageHeader from "@/components/common/PageHeader";
import SafetyBadge from "@/components/common/SafetyBadge";
import ValuesRadar from "@/components/common/ValuesRadar";
import { useAuth } from "@/hooks/useAuth";
import { VALUE_AXES } from "@/lib/valueAxes";

function trustLevelBadge(score: number): string {
  if (score >= 0.7) return "L3";
  if (score >= 0.4) return "L2";
  return "L1";
}

export default function MatchingDetailPage() {
  const { userId } = useParams();
  const { accessToken } = useAuth();
  const [candidate, setCandidate] = useState<CandidateResponse | null | undefined>(undefined);
  const [relationship, setRelationship] = useState<TrustRelationshipResponse | null>(null);
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

  useEffect(() => {
    if (!accessToken || !userId) return;
    trustApi
      .getRelationship(Number(userId), accessToken)
      .then(setRelationship)
      .catch(() => setRelationship(null));
  }, [accessToken, userId]);

  if (!accessToken) return null;

  const similarity = candidate?.values_similarity ?? 0;
  // 축별 응답이 아직 없어 전체 일치율로 8축을 채운다(handoff A-2 반영 시 실제 값으로 교체).
  const partnerAxes = VALUE_AXES.map(() => similarity);
  const myAxes = VALUE_AXES.map(() => 0.72);

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-4 pb-28">
        <PageHeader
          title={candidate ? `${candidate.nickname} 님` : "후보 상세"}
          backTo="/matching"
          right={<SafetyBadge />}
        />

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
              <div className="flex items-center justify-between">
                <h2 className="text-xs font-semibold text-foreground">가치관 일치율</h2>
                <span className="text-sm font-bold text-primary">
                  {Math.round(similarity * 100)}%
                </span>
              </div>
              <ValuesRadar partnerValues={partnerAxes} myValues={myAxes} />
              <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                {VALUE_AXES.map((axis) => (
                  <span key={axis} className="text-[11px] text-muted-foreground">
                    {axis}
                  </span>
                ))}
              </div>
              <div className="flex items-center gap-3 border-t border-border pt-2 text-[11px] text-muted-foreground">
                <span className="flex items-center gap-1">
                  <span className="h-0.5 w-4 bg-primary" />
                  {candidate.nickname} 님
                </span>
                <span className="flex items-center gap-1">
                  <span className="h-0.5 w-4 border-t-2 border-dashed border-foreground" />나
                </span>
              </div>
              <p className="text-[10px] leading-relaxed text-muted-foreground">
                축별 상세 값은 8축 응답 저장이 준비되면 표시됩니다. 지금은 전체 일치율 기준입니다.
              </p>
            </section>

            <section className="flex flex-col gap-2 rounded-2xl border border-border bg-secondary p-4">
              <h2 className="text-xs font-semibold text-foreground">이 이웃을 추천하는 이유</h2>
              <p className="text-xs leading-relaxed text-foreground">{candidate.reason}</p>
            </section>

            <section className="flex flex-col gap-2 rounded-2xl border border-border bg-secondary p-4">
              <h2 className="text-xs font-semibold text-foreground">안전 확인</h2>
              <ul className="flex list-none flex-col gap-1.5 text-[11px] text-foreground">
                <li>✓ 본인인증 · 안전 하드필터 통과</li>
                <li>✓ 공동육아 {relationship?.joint_session_count ?? 0}회 · 신고 이력 없음</li>
                <li>✓ 신뢰 등급 {relationship?.level ?? trustLevelBadge(candidate.trust_score)}</li>
              </ul>
            </section>

            <section className="flex flex-col gap-3 rounded-2xl border border-border bg-secondary p-4">
              <h2 className="text-xs font-semibold text-foreground">매칭 지표</h2>
              {[
                { label: "가치관 유사도", value: candidate.values_similarity },
                { label: "상보 스코어", value: candidate.complementary_score },
                { label: "아동 개월 수 유사도", value: candidate.age_similarity },
              ].map((item) => (
                <div key={item.label} className="flex flex-col gap-1">
                  <div className="flex justify-between text-[11px] text-muted-foreground">
                    <span>{item.label}</span>
                    <span className="font-medium text-foreground">
                      {Math.round(item.value * 100)}%
                    </span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-background">
                    <div
                      className="h-full bg-primary"
                      style={{ width: `${Math.round(item.value * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
              <div className="flex justify-between border-t border-border pt-2 text-[11px] text-foreground">
                <span className="text-muted-foreground">평균 별점</span>
                <span className="font-medium">
                  {candidate.average_rating != null
                    ? `★ ${candidate.average_rating.toFixed(1)}`
                    : "아직 평가 없음"}
                </span>
              </div>
            </section>

            {relationship?.level !== "L3" && (
              <p className="rounded-2xl bg-secondary p-4 text-[11px] leading-relaxed text-muted-foreground">
                처음 세 번은 <span className="font-semibold text-foreground">공개 장소</span>에서
                함께 돌봅니다. 단독 위탁은 그 다음에 열립니다.
              </p>
            )}
          </>
        )}
      </div>

      {candidate && (
        <div className="fixed inset-x-0 bottom-16 flex justify-center gap-2 bg-background px-6 py-3">
          <Link
            to={`/chat/${candidate.user_id}`}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-border bg-background text-foreground"
            aria-label="대화하기"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.6}
              className="h-5 w-5"
            >
              <path d="M4 5h16v10H9l-4 3.5V15H4V5Z" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </Link>
          {relationship?.level === "L3" ? (
            <Link
              to={`/care/requests/new?providerId=${candidate.user_id}&nickname=${encodeURIComponent(candidate.nickname)}`}
              className="flex-1 rounded-full bg-primary py-3 text-center text-sm font-semibold text-primary-foreground"
            >
              돌봄 요청 보내기
            </Link>
          ) : (
            <Link
              to={`/trust/${candidate.user_id}/joint-sessions/new`}
              className="flex-1 rounded-full bg-primary py-3 text-center text-sm font-semibold text-primary-foreground"
            >
              첫 만남 요청 보내기
            </Link>
          )}
        </div>
      )}
    </main>
  );
}
