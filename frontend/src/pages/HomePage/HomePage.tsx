import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import * as careApi from "@/api/care";
import type { CareSessionResponse } from "@/api/careTypes";
import * as matchingApi from "@/api/matching";
import type { CandidateResponse } from "@/api/matchingTypes";
import * as notificationsApi from "@/api/notifications";
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

  useEffect(() => {
    if (!accessToken) return;
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
  }, [accessToken]);

  const today = toYmd(new Date());
  const upcomingSession =
    sessions
      ?.filter((s) => s.status === "CONFIRMED" && !s.checkout_at && s.care_date >= today)
      .sort((a, b) =>
        a.care_date === b.care_date
          ? a.start_slot - b.start_slot
          : a.care_date.localeCompare(b.care_date),
      )[0] ?? null;

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

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-4">
        <div className="flex items-center justify-between">
          <h1 className="text-base font-medium text-foreground">품앗이온</h1>
          {accessToken && (
            <Link to="/notifications" className="relative text-foreground">
              <BellIcon />
              {unreadCount > 0 && (
                <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[9px] font-bold text-destructive-foreground">
                  {unreadCount > 9 ? "9+" : unreadCount}
                </span>
              )}
            </Link>
          )}
        </div>

        {!accessToken && (
          <Link
            to="/login"
            className="rounded-2xl border border-border bg-secondary px-4 py-4 text-center text-sm font-medium text-foreground"
          >
            로그인하고 이웃을 만나보세요 →
          </Link>
        )}

        {accessToken && (
          <>
            {upcomingSession && (
              <section className="flex flex-col gap-2.5 rounded-2xl border border-border bg-secondary p-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-xs font-medium text-muted-foreground">진행 중인 돌봄</h2>
                  <span className="text-[11px] font-semibold text-primary">확정됨</span>
                </div>
                <div className="text-sm font-medium text-foreground">
                  {sessionWhenLabel(upcomingSession)} ·{" "}
                  {durationLabel(upcomingSession.start_slot, upcomingSession.end_slot)}
                </div>
                <p className="text-[11px] text-muted-foreground">
                  상대와 함께 돌봄이 예정되어 있어요.
                </p>
                <Link
                  to={`/care/requests/${upcomingSession.id}`}
                  className="mt-1 rounded-lg bg-primary px-3 py-2.5 text-center text-xs font-medium text-primary-foreground"
                >
                  상세 보기
                </Link>
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
                <ul className="flex flex-col gap-2">
                  {candidates.slice(0, 2).map((candidate) => (
                    <li key={candidate.user_id}>
                      <Link
                        to={`/matching/${candidate.user_id}`}
                        className="flex items-center gap-2.5 rounded-2xl border border-border bg-secondary p-3"
                      >
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
                          {candidate.nickname.slice(0, 1)}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="text-xs font-medium text-foreground">
                            {candidate.nickname}님 · 도보 {Math.round(candidate.distance_m / 80)}분
                          </div>
                          <div className="truncate text-[11px] text-muted-foreground">
                            {candidate.reason}
                          </div>
                        </div>
                        <span className="shrink-0 rounded-lg bg-primary px-2 py-1 text-[11px] font-bold text-primary-foreground">
                          {Math.round(candidate.total_score * 100)}점
                        </span>
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
