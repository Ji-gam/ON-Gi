import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

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

export default function CareRequestsPage() {
  const { accessToken, user } = useAuth();
  const [sessions, setSessions] = useState<CareSessionResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<number | null>(null);

  function load() {
    if (!accessToken) return;
    careApi
      .listRequests(accessToken)
      .then(setSessions)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "요청 목록을 불러오지 못했습니다."),
      );
  }

  useEffect(load, [accessToken]);

  async function handleAction(action: "accept" | "reject", sessionId: number) {
    if (!accessToken) return;
    setError(null);
    setPendingId(sessionId);
    try {
      if (action === "accept") await careApi.acceptRequest(sessionId, accessToken);
      else await careApi.rejectRequest(sessionId, accessToken);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "처리하지 못했습니다.");
    } finally {
      setPendingId(null);
    }
  }

  if (!accessToken || !user) return null;

  const received = sessions?.filter((s) => s.provider_id === user.id) ?? [];
  const sent = sessions?.filter((s) => s.requester_id === user.id) ?? [];

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-6">
        <h1 className="text-sm font-medium text-foreground">돌봄 요청함</h1>

        {sessions === null && !error && (
          <p className="text-xs text-muted-foreground">불러오는 중...</p>
        )}
        {error && (
          <p className="rounded-lg bg-destructive/10 px-3 py-2.5 text-xs text-destructive">
            {error}
          </p>
        )}

        {sessions && (
          <>
            <section className="flex flex-col gap-2.5">
              <h2 className="text-xs font-medium text-muted-foreground">받은 요청</h2>
              {received.length === 0 && (
                <p className="text-xs text-muted-foreground">받은 요청이 없습니다.</p>
              )}
              <ul className="flex flex-col gap-2">
                {received.map((s) => (
                  <li
                    key={s.id}
                    className="flex flex-col gap-2 rounded-xl border border-border bg-secondary p-3"
                  >
                    <Link
                      to={`/care/requests/${s.id}`}
                      className="flex items-center justify-between"
                    >
                      <span className="text-xs text-foreground">
                        {s.care_date} · {STATUS_LABELS[s.status]}
                      </span>
                    </Link>
                    {s.status === "REQUESTED" && (
                      <div className="flex gap-2">
                        <button
                          type="button"
                          disabled={pendingId === s.id}
                          onClick={() => handleAction("accept", s.id)}
                          className="flex-1 rounded-lg bg-primary px-2.5 py-1.5 text-[11px] font-medium text-primary-foreground disabled:opacity-60"
                        >
                          수락
                        </button>
                        <button
                          type="button"
                          disabled={pendingId === s.id}
                          onClick={() => handleAction("reject", s.id)}
                          className="flex-1 rounded-lg border border-border bg-background px-2.5 py-1.5 text-[11px] font-medium text-foreground disabled:opacity-60"
                        >
                          거절
                        </button>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </section>

            <section className="flex flex-col gap-2.5">
              <h2 className="text-xs font-medium text-muted-foreground">보낸 요청</h2>
              {sent.length === 0 && (
                <p className="text-xs text-muted-foreground">보낸 요청이 없습니다.</p>
              )}
              <ul className="flex flex-col gap-2">
                {sent.map((s) => (
                  <li key={s.id} className="rounded-xl border border-border bg-secondary p-3">
                    <Link
                      to={`/care/requests/${s.id}`}
                      className="flex items-center justify-between"
                    >
                      <span className="text-xs text-foreground">
                        {s.care_date} · {STATUS_LABELS[s.status]}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          </>
        )}
      </div>
    </main>
  );
}
