import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import * as careApi from "@/api/care";
import type { CareSessionResponse } from "@/api/careTypes";
import * as childrenApi from "@/api/children";
import type { ChildDetailResponse } from "@/api/childrenTypes";
import * as matchingApi from "@/api/matching";
import type { CandidateResponse } from "@/api/matchingTypes";
import * as notificationsApi from "@/api/notifications";
import * as trustApi from "@/api/trust";
import { useAuth } from "@/hooks/useAuth";

function BellIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      className="h-5 w-5"
    >
      <path
        d="M6 10a6 6 0 1 1 12 0c0 4 1.5 5.5 1.5 5.5H4.5S6 14 6 10Z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M10 19a2 2 0 0 0 4 0" strokeLinecap="round" />
    </svg>
  );
}

// score(0~1) -> L1/L2/L3 배지. 신뢰 레벨 자체는 관계 단위 데이터라 계정 단위로는
// 존재하지 않으므로, 가중합 신뢰 점수(실제 값)를 구간으로 나눠 대신 보여준다.
function trustLevelBadge(score: number): string {
  if (score >= 0.7) return "L3";
  if (score >= 0.4) return "L2";
  return "L1";
}

function slotToTime(slot: number): string {
  const hour = Math.floor(slot / 2)
    .toString()
    .padStart(2, "0");
  const minute = slot % 2 === 0 ? "00" : "30";
  return `${hour}:${minute}`;
}

function toYmd(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function sessionWhenLabel(careSession: CareSessionResponse): string {
  const today = toYmd(new Date());
  const tomorrow = toYmd(new Date(Date.now() + 86400000));
  const dayLabel =
    careSession.care_date === today
      ? "오늘"
      : careSession.care_date === tomorrow
        ? "내일"
        : careSession.care_date;
  return `${dayLabel} ${slotToTime(careSession.start_slot)}`;
}

function durationLabel(startSlot: number, endSlot: number): string {
  const totalMinutes = (endSlot - startSlot) * 30;
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) return `${minutes}분`;
  if (minutes === 0) return `${hours}시간`;
  return `${hours}시간 ${minutes}분`;
}

export default function HomePage() {
  const { user, accessToken } = useAuth();
  const [candidates, setCandidates] = useState<CandidateResponse[] | null>(null);
  const [sessions, setSessions] = useState<CareSessionResponse[] | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [myTrustScore, setMyTrustScore] = useState<number | null>(null);
  const [upcomingChild, setUpcomingChild] = useState<ChildDetailResponse | null>(null);

  useEffect(() => {
    if (!accessToken || !user) return;
    matchingApi
      .getCandidates(accessToken)
      .then(setCandidates)
      .catch(() => setCandidates([]));
    careApi
      .listRequests(accessToken)
      .then(setSessions)
      .catch(() => setSessions([]));
    notificationsApi
      .listNotifications(accessToken)
      .then((list) => setUnreadCount(list.filter((n) => !n.read_at).length))
      .catch(() => {});
    trustApi
      .getScore(user.id, accessToken)
      .then((res) => setMyTrustScore(res.score))
      .catch(() => {});
  }, [accessToken, user]);

  const today = toYmd(new Date());
  const upcomingSession =
    sessions
      ?.filter((s) => s.status === "CONFIRMED" && !s.checkout_at && s.care_date >= today)
      .sort((a, b) =>
        a.care_date === b.care_date
          ? a.start_slot - b.start_slot
          : a.care_date.localeCompare(b.care_date),
      )[0] ?? null;

  useEffect(() => {
    if (!accessToken || !upcomingSession) {
      setUpcomingChild(null);
      return;
    }
    // 아동 상세는 본인 소유 아동만 조회 가능 — 내가 요청자일 때만 성공하고,
    // 내가 제공자면 404가 나서 아동 정보 없이 표시된다.
    childrenApi
      .getChild(upcomingSession.child_id, accessToken)
      .then(setUpcomingChild)
      .catch(() => setUpcomingChild(null));
  }, [accessToken, upcomingSession]);

  const receivedRequests =
    user && sessions
      ? sessions
          .filter((s) => s.provider_id === user.id && s.status === "REQUESTED")
          .sort((a, b) =>
            a.care_date === b.care_date
              ? a.start_slot - b.start_slot
              : a.care_date.localeCompare(b.care_date),
          )
      : [];

  const partnerNickname = (() => {
    if (!upcomingSession || !user || !candidates) return "이웃님";
    const partnerId =
      upcomingSession.requester_id === user.id
        ? upcomingSession.provider_id
        : upcomingSession.requester_id;
    return candidates.find((c) => c.user_id === partnerId)?.nickname ?? "이웃님";
  })();

  // 비로그인 상태에서도 대시보드 모양은 그대로 보여준다 — 실제 데이터가 없으니
  // 이 화면이 무엇을 보여주는 화면인지 예시로 채우고, 모든 액션은 로그인으로 유도한다.
  const isGuest = !accessToken;
  const detailLinkTarget = (path: string) => (isGuest ? "/login" : path);

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <h1 className="text-base font-medium text-foreground">품앗이온</h1>
            <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] font-semibold text-primary">
              신뢰 {isGuest ? "L2" : myTrustScore !== null ? trustLevelBadge(myTrustScore) : "-"}
            </span>
            <span className="rounded-full bg-destructive/10 px-2 py-0.5 text-[10px] font-semibold text-destructive">
              안전
            </span>
          </div>
          <Link to={detailLinkTarget("/notifications")} className="relative text-foreground">
            <BellIcon />
            {!isGuest && unreadCount > 0 && (
              <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[9px] font-bold text-destructive-foreground">
                {unreadCount > 9 ? "9+" : unreadCount}
              </span>
            )}
          </Link>
        </div>

        {isGuest ? (
          <>
            <section className="flex flex-col gap-2.5 rounded-2xl border border-border bg-secondary p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <h2 className="text-xs font-medium text-muted-foreground">진행 중인 돌봄</h2>
                  <span className="rounded-full bg-background px-1.5 py-0.5 text-[10px] text-muted-foreground">
                    예시
                  </span>
                </div>
                <span className="text-[11px] font-semibold text-primary">확정됨</span>
              </div>
              <div className="text-sm font-medium text-foreground">오늘 저녁 6시 · 2시간</div>
              <p className="text-[11px] text-muted-foreground">
                이웃님과 함께 · 노쇼 방지금 예치 완료
              </p>
              <div className="mt-1 flex gap-2">
                <Link
                  to="/login"
                  className="flex-1 rounded-full bg-primary px-3 py-2.5 text-center text-xs font-medium text-primary-foreground"
                >
                  체크인
                </Link>
                <Link
                  to="/login"
                  className="flex-1 rounded-full border border-border bg-background px-3 py-2.5 text-center text-xs font-medium text-foreground"
                >
                  일정 보기
                </Link>
              </div>
            </section>

            <section className="flex flex-col gap-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <h2 className="text-xs font-semibold text-foreground">오늘의 추천 이웃</h2>
                  <span className="rounded-full bg-secondary px-1.5 py-0.5 text-[10px] text-muted-foreground">
                    예시
                  </span>
                </div>
                <Link to="/login" className="text-[11px] font-semibold text-primary">
                  전체 보기
                </Link>
              </div>
              <ul className="flex list-none flex-col gap-2">
                {[
                  {
                    nickname: "서연",
                    trust: "L3",
                    reason: "아이 재우는 방식이 비슷하고, 도보 7분 거리예요.",
                    tags: ["4세 여아", "주말 가능"],
                  },
                  {
                    nickname: "민호",
                    trust: "L2",
                    reason: "제가 야간 근무인 시간대에 민호 님은 비번이에요.",
                    tags: ["5세 남아", "평일 야간"],
                  },
                ].map((example) => (
                  <li key={example.nickname}>
                    <Link
                      to="/login"
                      className="flex flex-col gap-2 rounded-2xl border border-border bg-secondary p-3"
                    >
                      <div className="flex items-center gap-2.5">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
                          {example.nickname.slice(0, 1)}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5 text-xs font-medium text-foreground">
                            <span>{example.nickname}님</span>
                            <span className="rounded-full bg-background px-1.5 py-0.5 text-[10px] font-semibold text-primary">
                              {example.trust}
                            </span>
                            <span className="rounded-full bg-background px-1.5 py-0.5 text-[10px] text-muted-foreground">
                              본인인증
                            </span>
                          </div>
                          <div className="truncate text-[11px] text-muted-foreground">
                            {example.reason}
                          </div>
                        </div>
                      </div>
                      <div className="flex gap-1.5 pl-11">
                        {example.tags.map((tag) => (
                          <span
                            key={tag}
                            className="rounded-full bg-background px-2 py-0.5 text-[10px] text-muted-foreground"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>

            <Link
              to="/login"
              className="flex items-center justify-between rounded-2xl border border-border bg-secondary p-4"
            >
              <div>
                <div className="flex items-center gap-1.5 text-sm font-medium text-foreground">
                  <span>받은 요청 2건</span>
                  <span className="rounded-full bg-background px-1.5 py-0.5 text-[10px] font-normal text-muted-foreground">
                    예시
                  </span>
                </div>
                <div className="text-[11px] text-muted-foreground">
                  가장 이른 요청은 내일 오전 9시입니다
                </div>
              </div>
              <span className="text-muted-foreground">›</span>
            </Link>

            <Link
              to="/login"
              className="rounded-2xl border border-border bg-secondary px-4 py-4 text-center text-sm font-medium text-foreground"
            >
              로그인하고 시작하기 →
            </Link>
          </>
        ) : (
          <>
            {upcomingSession && (
              <section className="flex flex-col gap-2.5 rounded-2xl border border-border bg-secondary p-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-xs font-medium text-muted-foreground">진행 중인 돌봄</h2>
                  <span className="text-[11px] font-semibold text-primary">확정됨</span>
                </div>
                <div className="text-sm font-medium text-foreground">
                  {sessionWhenLabel(upcomingSession)} ·{" "}
                  {upcomingChild ? `${upcomingChild.months_old}개월 · ` : ""}
                  {durationLabel(upcomingSession.start_slot, upcomingSession.end_slot)}
                </div>
                <p className="text-[11px] text-muted-foreground">
                  {partnerNickname}님과 함께 · 노쇼 방지금 예치 완료
                </p>
                <div className="mt-1 flex gap-2">
                  <Link
                    to={`/care/requests/${upcomingSession.id}`}
                    className="flex-1 rounded-full bg-primary px-3 py-2.5 text-center text-xs font-medium text-primary-foreground"
                  >
                    체크인
                  </Link>
                  <Link
                    to={`/care/requests/${upcomingSession.id}`}
                    className="flex-1 rounded-full border border-border bg-background px-3 py-2.5 text-center text-xs font-medium text-foreground"
                  >
                    일정 보기
                  </Link>
                </div>
              </section>
            )}

            <section className="flex flex-col gap-2.5">
              <div className="flex items-center justify-between">
                <h2 className="text-xs font-semibold text-foreground">오늘의 추천 이웃</h2>
                <Link to="/matching" className="text-[11px] font-semibold text-primary">
                  전체 보기
                </Link>
              </div>
              {candidates === null && (
                <p className="text-[11px] text-muted-foreground">불러오는 중...</p>
              )}
              {candidates && candidates.length === 0 && (
                <p className="text-[11px] text-muted-foreground">아직 추천할 이웃이 없어요.</p>
              )}
              {candidates && candidates.length > 0 && (
                <ul className="flex list-none flex-col gap-2">
                  {candidates.slice(0, 2).map((candidate) => (
                    <li key={candidate.user_id}>
                      <Link
                        to={`/matching/${candidate.user_id}`}
                        className="flex flex-col gap-2 rounded-2xl border border-border bg-secondary p-3"
                      >
                        <div className="flex items-center gap-2.5">
                          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
                            {candidate.nickname.slice(0, 1)}
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-1.5 text-xs font-medium text-foreground">
                              <span>{candidate.nickname}님</span>
                              <span className="rounded-full bg-background px-1.5 py-0.5 text-[10px] font-semibold text-primary">
                                {trustLevelBadge(candidate.trust_score)}
                              </span>
                              <span className="rounded-full bg-background px-1.5 py-0.5 text-[10px] text-muted-foreground">
                                본인인증
                              </span>
                            </div>
                            <div className="truncate text-[11px] text-muted-foreground">
                              {candidate.reason}
                            </div>
                          </div>
                          <span className="shrink-0 rounded-lg bg-primary px-2 py-1 text-[11px] font-bold text-primary-foreground">
                            {Math.round(candidate.total_score * 100)}점
                          </span>
                        </div>
                        <div className="flex gap-1.5 pl-11">
                          <span className="rounded-full bg-background px-2 py-0.5 text-[10px] text-muted-foreground">
                            도보 {Math.round(candidate.distance_m / 80)}분
                          </span>
                          {candidate.age_similarity >= 0.6 && (
                            <span className="rounded-full bg-background px-2 py-0.5 text-[10px] text-muted-foreground">
                              또래 아이
                            </span>
                          )}
                          {candidate.complementary_score >= 0.5 && (
                            <span className="rounded-full bg-background px-2 py-0.5 text-[10px] text-muted-foreground">
                              시간대 잘 맞음
                            </span>
                          )}
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {receivedRequests.length > 0 && (
              <Link
                to="/care/requests"
                className="flex items-center justify-between rounded-2xl border border-border bg-secondary p-4"
              >
                <div>
                  <div className="text-sm font-medium text-foreground">
                    받은 요청 {receivedRequests.length}건
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    가장 이른 요청은 {sessionWhenLabel(receivedRequests[0])}입니다
                  </div>
                </div>
                <span className="text-muted-foreground">›</span>
              </Link>
            )}
          </>
        )}
      </div>
    </main>
  );
}
