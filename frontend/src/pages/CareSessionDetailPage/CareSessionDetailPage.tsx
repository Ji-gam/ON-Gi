import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import * as careApi from "@/api/care";
import type { CareSessionResponse, CareSessionStatus } from "@/api/careTypes";
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

export default function CareSessionDetailPage() {
  const { accessToken, user } = useAuth();
  const navigate = useNavigate();
  const { sessionId } = useParams();
  const [careSession, setCareSession] = useState<CareSessionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function load() {
    if (!accessToken || !sessionId) return;
    careApi
      .getRequest(Number(sessionId), accessToken)
      .then(setCareSession)
      .catch((err) => setError(err instanceof Error ? err.message : "세션을 불러오지 못했습니다."));
  }

  useEffect(load, [accessToken, sessionId]);

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

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-4">
        <button
          type="button"
          onClick={() => navigate("/care/requests")}
          className="self-start text-[11px] text-muted-foreground"
        >
          ← 목록으로
        </button>

        <h1 className="text-sm font-medium text-foreground">돌봄 요청 상세</h1>

        <div className="flex flex-col gap-2 rounded-xl border border-border bg-secondary p-4 text-xs text-foreground">
          <div className="flex justify-between">
            <span className="text-muted-foreground">상태</span>
            <span className="font-medium">{STATUS_LABELS[careSession.status]}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">날짜</span>
            <span>{careSession.care_date}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">시간</span>
            <span>
              {slotToTime(careSession.start_slot)} ~ {slotToTime(careSession.end_slot)}
            </span>
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
        </div>

        {error && (
          <p className="rounded-lg bg-destructive/10 px-3 py-2.5 text-xs text-destructive">
            {error}
          </p>
        )}

        {canRespond && (
          <div className="flex gap-2">
            <button
              type="button"
              disabled={isSubmitting}
              onClick={() => handleAction("accept")}
              className="flex-1 rounded-lg bg-primary px-3 py-3 text-sm font-medium text-primary-foreground disabled:opacity-60"
            >
              수락
            </button>
            <button
              type="button"
              disabled={isSubmitting}
              onClick={() => handleAction("reject")}
              className="flex-1 rounded-lg border border-border bg-background px-3 py-3 text-sm font-medium text-foreground disabled:opacity-60"
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
            className="rounded-lg border border-border bg-background px-3 py-3 text-sm font-medium text-destructive disabled:opacity-60"
          >
            요청 취소
          </button>
        )}
      </div>
    </main>
  );
}
