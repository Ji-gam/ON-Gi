import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import * as careApi from "@/api/care";
import type { CareSessionResponse, CareSessionStatus } from "@/api/careTypes";
import * as childrenApi from "@/api/children";
import type { ChildDetailResponse } from "@/api/childrenTypes";
import PageHeader from "@/components/common/PageHeader";
import { useAuth } from "@/hooks/useAuth";

const STATUS_LABELS: Record<CareSessionStatus, string> = {
  REQUESTED: "요청됨",
  CONFIRMED: "확정됨",
  REJECTED: "거절됨",
  CANCELLED: "취소됨",
  NO_SHOW: "노쇼",
};

function slotToTime(slot: number): string {
  const hour = Math.floor(slot / 2)
    .toString()
    .padStart(2, "0");
  const minute = slot % 2 === 0 ? "00" : "30";
  return `${hour}:${minute}`;
}

function sessionStartAt(careSession: CareSessionResponse): Date {
  const start = new Date(`${careSession.care_date}T00:00:00`);
  start.setMinutes(careSession.start_slot * 30);
  return start;
}

function useCountdown(target: Date | null): number | null {
  const [remainingMs, setRemainingMs] = useState<number | null>(
    target ? target.getTime() - Date.now() : null,
  );
  useEffect(() => {
    if (!target) {
      setRemainingMs(null);
      return;
    }
    const tick = () => setRemainingMs(target.getTime() - Date.now());
    tick();
    const timer = setInterval(tick, 30000);
    return () => clearInterval(timer);
  }, [target]);
  return remainingMs;
}

function CountdownRing({ remainingMs }: { remainingMs: number }) {
  const minutes = Math.max(0, Math.round(remainingMs / 60000));
  // 남은 시간을 1시간 기준으로 환산해 링을 채운다(1시간 이상이면 가득 참).
  const ratio = Math.min(1, Math.max(0, minutes / 60));
  const circumference = 2 * Math.PI * 52;
  return (
    <div className="relative mx-auto h-32 w-32">
      <svg viewBox="0 0 120 120" className="h-32 w-32 -rotate-90">
        <circle cx="60" cy="60" r="52" fill="none" stroke="hsl(var(--border))" strokeWidth="8" />
        <circle
          cx="60"
          cy="60"
          r="52"
          fill="none"
          stroke="hsl(var(--primary))"
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - ratio)}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-[11px] text-muted-foreground">시작까지</span>
        <span className="text-xl font-bold text-foreground">
          {minutes > 0 ? `${minutes}분` : "곧 시작"}
        </span>
      </div>
    </div>
  );
}

export default function CareSessionDetailPage() {
  const { accessToken, user } = useAuth();
  const navigate = useNavigate();
  const { sessionId } = useParams();
  const [careSession, setCareSession] = useState<CareSessionResponse | null>(null);
  const [child, setChild] = useState<ChildDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [checkinNotice, setCheckinNotice] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!accessToken || !sessionId) return;
    careApi
      .getRequest(Number(sessionId), accessToken)
      .then(setCareSession)
      .catch((err) => setError(err instanceof Error ? err.message : "세션을 불러오지 못했습니다."));
  }, [accessToken, sessionId]);

  useEffect(load, [load]);

  useEffect(() => {
    if (!accessToken || !careSession) return;
    // 아동 상세는 본인 소유일 때만 조회된다 — 제공자 입장이면 실패해서 배지를 생략한다.
    childrenApi
      .getChild(careSession.child_id, accessToken)
      .then(setChild)
      .catch(() => setChild(null));
  }, [accessToken, careSession]);

  const startAt =
    careSession && careSession.status === "CONFIRMED" ? sessionStartAt(careSession) : null;
  const remainingMs = useCountdown(startAt);

  async function handleAction(action: "accept" | "reject" | "cancel") {
    if (!accessToken || !careSession) return;
    setError(null);
    setIsSubmitting(true);
    try {
      if (action === "accept") await careApi.acceptRequest(careSession.id, accessToken);
      else if (action === "reject") await careApi.rejectRequest(careSession.id, accessToken);
      else await careApi.cancelRequest(careSession.id, {}, accessToken);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "처리하지 못했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCheckin() {
    if (!accessToken || !careSession) return;
    setError(null);
    setCheckinNotice(null);
    setIsSubmitting(true);

    const submit = async (lat: number, lng: number, reason?: string) => {
      try {
        const updated = await careApi.checkin(careSession.id, { lat, lng, reason }, accessToken);
        setCareSession(updated);
        if (updated.checkin_out_of_range) {
          setCheckinNotice("약속 장소 반경 밖에서 체크인되어 사유가 함께 기록됐어요.");
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "체크인하지 못했습니다.";
        // 반경 밖이면 서버가 사유를 요구한다 — 사유를 붙여 한 번 더 시도한다.
        if (!reason && message.includes("사유")) {
          await submit(lat, lng, "위치 확인이 어려워 사유와 함께 체크인합니다.");
          return;
        }
        setError(message);
      } finally {
        setIsSubmitting(false);
      }
    };

    if (!navigator.geolocation) {
      setError("이 기기에서는 위치 확인을 사용할 수 없어요.");
      setIsSubmitting(false);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => submit(position.coords.latitude, position.coords.longitude),
      () => {
        setError("위치 권한이 필요합니다. 권한을 허용한 뒤 다시 시도해주세요.");
        setIsSubmitting(false);
      },
      { timeout: 8000 },
    );
  }

  if (!accessToken || !user) return null;
  if (!careSession) {
    return (
      <main className="flex min-h-screen justify-center bg-background px-6 py-10">
        {error ? (
          <p className="text-xs text-destructive">{error}</p>
        ) : (
          <p className="text-xs text-muted-foreground">불러오는 중...</p>
        )}
      </main>
    );
  }

  const isProvider = careSession.provider_id === user.id;
  const canRespond = isProvider && careSession.status === "REQUESTED";
  const canCancel =
    (careSession.status === "REQUESTED" || careSession.status === "CONFIRMED") &&
    !careSession.checkin_at;
  const canCheckin = isProvider && careSession.status === "CONFIRMED" && !careSession.checkin_at;
  const isInProgress = !!careSession.checkin_at && !careSession.checkout_at;
  const allergies = child?.allergies
    ?.split(/[,·]/)
    .map((item) => item.trim())
    .filter(Boolean);

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-4 pb-4">
        <PageHeader
          title={isInProgress || canCheckin ? "진행 중인 돌봄" : "돌봄 요청 상세"}
          backTo="/care/requests"
          right={
            <span className="rounded-full bg-destructive/10 px-2 py-0.5 text-[10px] font-semibold text-destructive">
              신고
            </span>
          }
        />

        <section className="flex flex-col gap-3 rounded-2xl border border-border bg-secondary p-4">
          <div className="flex justify-center">
            <span className="rounded-full bg-background px-2.5 py-1 text-[11px] font-semibold text-primary">
              {STATUS_LABELS[careSession.status]}
              {careSession.status === "CONFIRMED" ? " · 단독 위탁" : ""}
            </span>
          </div>

          <div className="text-center text-sm font-semibold text-foreground">
            {careSession.care_date} · {slotToTime(careSession.start_slot)} –{" "}
            {slotToTime(careSession.end_slot)}
          </div>

          {careSession.status === "CONFIRMED" && remainingMs !== null && remainingMs > 0 && (
            <CountdownRing remainingMs={remainingMs} />
          )}

          {careSession.checkin_at && (
            <div className="rounded-xl bg-background p-3 text-center text-[11px] text-muted-foreground">
              체크인 완료
              {careSession.checkin_distance_m !== null && (
                <> · 약속 장소에서 {Math.round(careSession.checkin_distance_m)}m</>
              )}
            </div>
          )}

          {canCheckin && (
            <>
              <p className="rounded-xl bg-background p-3 text-center text-[11px] text-muted-foreground">
                체크인하면 약속 장소 반경 안에 있는지만 확인합니다. 위치 좌표는 저장하지 않습니다.
              </p>
              <button
                type="button"
                disabled={isSubmitting}
                onClick={handleCheckin}
                className="rounded-full border-0 bg-primary py-3 text-sm font-semibold text-primary-foreground disabled:opacity-60"
              >
                {isSubmitting ? "확인 중..." : "체크인하고 돌봄 시작"}
              </button>
            </>
          )}

          {checkinNotice && (
            <p className="rounded-lg bg-destructive/10 px-3 py-2.5 text-[11px] text-destructive">
              {checkinNotice}
            </p>
          )}
        </section>

        {allergies && allergies.length > 0 && (
          <section className="flex flex-col gap-2 rounded-2xl border border-destructive/30 bg-destructive/5 p-4">
            <h2 className="text-xs font-semibold text-destructive">아이 알레르기</h2>
            <div className="flex flex-wrap gap-1.5">
              {allergies.map((item) => (
                <span
                  key={item}
                  className="rounded-full bg-background px-2.5 py-1 text-[11px] font-medium text-destructive"
                >
                  {item}
                </span>
              ))}
            </div>
            <p className="text-[11px] text-muted-foreground">
              온보딩에서 등록한 정보가 돌봄 당일 자동으로 표시됩니다.
            </p>
          </section>
        )}

        <section className="flex flex-col gap-2 rounded-2xl border border-border bg-secondary p-4 text-xs text-foreground">
          <div className="flex justify-between">
            <span className="text-muted-foreground">상태</span>
            <span className="font-medium">{STATUS_LABELS[careSession.status]}</span>
          </div>
          {careSession.actual_minutes !== null && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">실제 돌봄 시간</span>
              <span>{careSession.actual_minutes}분</span>
            </div>
          )}
          {careSession.cancel_reason && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">취소 사유</span>
              <span>{careSession.cancel_reason}</span>
            </div>
          )}
        </section>

        {error && (
          <p className="rounded-lg bg-destructive/10 px-3 py-2.5 text-xs text-destructive">
            {error}
          </p>
        )}

        {isInProgress && (
          <div className="flex gap-2">
            <Link
              to={`/chat/${isProvider ? careSession.requester_id : careSession.provider_id}`}
              className="flex-1 rounded-full border border-border bg-background px-3 py-3 text-center text-xs font-medium text-foreground"
            >
              상대와 대화
            </Link>
            <Link
              to={`/care/requests/${careSession.id}/journal`}
              className="flex-1 rounded-full border-0 bg-primary px-3 py-3 text-center text-xs font-semibold text-primary-foreground"
            >
              돌봄일지
            </Link>
          </div>
        )}

        {careSession.checkout_at && (
          <Link
            to={`/care/requests/${careSession.id}/review`}
            className="rounded-full border-0 bg-primary px-3 py-3 text-center text-sm font-semibold text-primary-foreground"
          >
            평가 남기기
          </Link>
        )}

        {canRespond && (
          <div className="flex gap-2">
            <button
              type="button"
              disabled={isSubmitting}
              onClick={() => handleAction("accept")}
              className="flex-1 rounded-full border-0 bg-primary px-3 py-3 text-sm font-semibold text-primary-foreground disabled:opacity-60"
            >
              수락
            </button>
            <button
              type="button"
              disabled={isSubmitting}
              onClick={() => handleAction("reject")}
              className="flex-1 rounded-full border border-border bg-background px-3 py-3 text-sm font-medium text-foreground disabled:opacity-60"
            >
              거절
            </button>
          </div>
        )}

        {canCancel && !canRespond && (
          <button
            type="button"
            disabled={isSubmitting}
            onClick={() => handleAction("cancel")}
            className="rounded-full border border-border bg-background px-3 py-3 text-sm font-medium text-destructive disabled:opacity-60"
          >
            요청 취소
          </button>
        )}

        <button
          type="button"
          onClick={() => navigate("/care/requests")}
          className="border-0 bg-transparent text-[11px] text-muted-foreground"
        >
          목록으로
        </button>
      </div>
    </main>
  );
}
