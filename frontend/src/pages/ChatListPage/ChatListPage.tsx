import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import * as careApi from "@/api/care";
import * as matchingApi from "@/api/matching";
import { useAuth } from "@/hooks/useAuth";

interface ChatPartner {
  userId: number;
  nickname: string;
}

export default function ChatListPage() {
  const { user, accessToken } = useAuth();
  const [partners, setPartners] = useState<ChatPartner[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken || !user) return;
    Promise.all([careApi.listRequests(accessToken), matchingApi.getCandidates(accessToken)])
      .then(([sessions, candidates]) => {
        // REQUESTED/REJECTED는 아직 수락 전이라 신뢰 L1이 안 생겨 채팅이 막힌다(REQ-F-COM-01).
        // 그 외 상태는 한 번이라도 수락(accept)됐던 세션이라 L1 관계가 만들어졌다.
        const partnerIds = new Set(
          sessions
            .filter((s) => s.status !== "REQUESTED" && s.status !== "REJECTED")
            .map((s) => (s.requester_id === user.id ? s.provider_id : s.requester_id)),
        );
        setPartners(
          Array.from(partnerIds).map((userId) => ({
            userId,
            nickname: candidates.find((c) => c.user_id === userId)?.nickname ?? `이웃 ${userId}`,
          })),
        );
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "대화 목록을 불러오지 못했습니다."),
      );
  }, [accessToken, user]);

  if (!accessToken) return null;

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-4">
        <h1 className="text-sm font-medium text-foreground">채팅</h1>

        {partners === null && !error && (
          <p className="text-xs text-muted-foreground">불러오는 중...</p>
        )}
        {error && (
          <p className="rounded-lg bg-destructive/10 px-3 py-2.5 text-xs text-destructive">
            {error}
          </p>
        )}
        {partners && partners.length === 0 && (
          <p className="text-xs text-muted-foreground">
            아직 대화할 수 있는 이웃이 없어요. 돌봄 요청이 수락되면 여기서 대화할 수 있어요.
          </p>
        )}
        {partners && partners.length > 0 && (
          <ul className="flex list-none flex-col gap-2">
            {partners.map((partner) => (
              <li key={partner.userId}>
                <Link
                  to={`/chat/${partner.userId}`}
                  className="flex items-center gap-2.5 rounded-2xl border border-border bg-secondary p-3"
                >
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
                    {partner.nickname.slice(0, 1)}
                  </div>
                  <span className="text-xs font-medium text-foreground">{partner.nickname}님</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  );
}
