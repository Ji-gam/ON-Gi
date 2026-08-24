import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import * as notificationsApi from "@/api/notifications";
import type { NotificationResponse } from "@/api/notificationTypes";
import { useAuth } from "@/hooks/useAuth";

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "방금 전";
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;
  return `${Math.floor(hours / 24)}일 전`;
}

export default function NotificationsPage() {
  const { accessToken } = useAuth();
  const [notifications, setNotifications] = useState<NotificationResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    if (!accessToken) return;
    notificationsApi
      .listNotifications(accessToken)
      .then(setNotifications)
      .catch((err) => setError(err instanceof Error ? err.message : "알림을 불러오지 못했습니다."));
  }

  useEffect(load, [accessToken]);

  async function handleClick(notification: NotificationResponse) {
    if (!accessToken || notification.read_at) return;
    try {
      await notificationsApi.markNotificationRead(notification.id, accessToken);
      load();
    } catch {
      // 읽음 처리 실패는 조용히 무시 — 목록 조회에는 영향 없음.
    }
  }

  if (!accessToken) return null;

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-4">
        <div className="flex items-center gap-2">
          <Link to="/home" className="text-xs text-muted-foreground">
            ← 홈
          </Link>
        </div>
        <h1 className="text-sm font-medium text-foreground">알림</h1>

        {notifications === null && !error && (
          <p className="text-xs text-muted-foreground">불러오는 중...</p>
        )}
        {error && (
          <p className="rounded-lg bg-destructive/10 px-3 py-2.5 text-xs text-destructive">
            {error}
          </p>
        )}
        {notifications && notifications.length === 0 && (
          <p className="text-xs text-muted-foreground">받은 알림이 없어요.</p>
        )}
        {notifications && notifications.length > 0 && (
          <ul className="flex flex-col gap-2">
            {notifications.map((notification) => (
              <li key={notification.id}>
                <button
                  type="button"
                  onClick={() => handleClick(notification)}
                  className={
                    notification.read_at
                      ? "flex w-full flex-col gap-1 rounded-xl border border-border bg-background px-4 py-3 text-left"
                      : "flex w-full flex-col gap-1 rounded-xl border border-border bg-secondary px-4 py-3 text-left"
                  }
                >
                  <span className="text-xs text-foreground">{notification.message}</span>
                  <span className="text-[11px] text-muted-foreground">
                    {timeAgo(notification.created_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  );
}
