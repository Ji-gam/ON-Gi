import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import * as chatApi from "@/api/chat";
import type { MessageResponse } from "@/api/chatTypes";
import { useAuth } from "@/hooks/useAuth";

export default function ChatThreadPage() {
  const { partnerId } = useParams();
  const { user, accessToken } = useAuth();
  const [messages, setMessages] = useState<MessageResponse[] | null>(null);
  const [content, setContent] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);

  function load() {
    if (!accessToken || !partnerId) return;
    chatApi
      .listMessages(Number(partnerId), accessToken)
      .then(setMessages)
      .catch((err) => setError(err instanceof Error ? err.message : "대화를 불러오지 못했습니다."));
  }

  useEffect(load, [accessToken, partnerId]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!accessToken || !partnerId || !content.trim()) return;
    setError(null);
    setIsSending(true);
    try {
      await chatApi.sendMessage(Number(partnerId), content.trim(), accessToken);
      setContent("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "전송하지 못했습니다.");
    } finally {
      setIsSending(false);
    }
  }

  if (!accessToken || !user) return null;

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-3">
        <Link to="/chat" className="text-xs text-muted-foreground">
          ← 채팅 목록
        </Link>

        {messages === null && !error && (
          <p className="text-xs text-muted-foreground">불러오는 중...</p>
        )}
        {error && (
          <p className="rounded-lg bg-destructive/10 px-3 py-2.5 text-xs text-destructive">
            {error}
          </p>
        )}
        {messages && messages.length === 0 && (
          <p className="text-xs text-muted-foreground">아직 대화가 없어요. 먼저 인사해보세요.</p>
        )}
        {messages && messages.length > 0 && (
          <ul className="flex list-none flex-col gap-1.5">
            {messages.map((message) => {
              const isMine = message.sender_id === user.id;
              return (
                <li key={message.id} className={isMine ? "flex justify-end" : "flex justify-start"}>
                  <div
                    className={
                      isMine
                        ? "max-w-[75%] rounded-2xl bg-primary px-3 py-2 text-xs text-primary-foreground"
                        : "max-w-[75%] rounded-2xl bg-secondary px-3 py-2 text-xs text-foreground"
                    }
                  >
                    {message.content}
                    {message.pii_masked && (
                      <div className="mt-1 text-[10px] opacity-70">
                        연락처로 보이는 내용은 안전을 위해 가려졌어요.
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}

        <form onSubmit={handleSubmit} className="mt-2 flex gap-2">
          <label htmlFor="chatContent" className="sr-only">
            메시지
          </label>
          <input
            id="chatContent"
            value={content}
            onChange={(event) => setContent(event.target.value)}
            placeholder="메시지를 입력하세요"
            className="flex-1 rounded-lg border-0 bg-secondary px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground"
          />
          <button
            type="submit"
            disabled={isSending || !content.trim()}
            className="rounded-lg border-0 bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground disabled:opacity-60"
          >
            전송
          </button>
        </form>
      </div>
    </main>
  );
}
