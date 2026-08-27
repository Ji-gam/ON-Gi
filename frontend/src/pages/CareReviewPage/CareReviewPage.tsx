import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";

import * as careApi from "@/api/care";
import * as matchingApi from "@/api/matching";
import * as trustApi from "@/api/trust";
import PageHeader from "@/components/common/PageHeader";
import { useAuth } from "@/hooks/useAuth";

const POSITIVE_TAGS = [
  "시간 약속을 잘 지켜요",
  "아이와 잘 놀아줘요",
  "소통이 편해요",
  "알레르기를 세심히 챙겨요",
];

const RATING_LABELS = [
  "",
  "많이 아쉬웠어요",
  "아쉬웠어요",
  "보통이었어요",
  "좋았어요",
  "믿고 맡길 수 있었어요",
];

export default function CareReviewPage() {
  const { sessionId } = useParams();
  const { accessToken, user } = useAuth();
  const navigate = useNavigate();

  const [partnerName, setPartnerName] = useState("이웃");
  const [rating, setRating] = useState(0);
  const [tags, setTags] = useState<Set<string>>(new Set());
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!accessToken || !sessionId || !user) return;
    Promise.all([
      careApi.getRequest(Number(sessionId), accessToken),
      matchingApi.getCandidates(accessToken),
    ])
      .then(([session, candidates]) => {
        const partnerId =
          session.requester_id === user.id ? session.provider_id : session.requester_id;
        const found = candidates.find((c) => c.user_id === partnerId);
        if (found) setPartnerName(found.nickname);
      })
      .catch(() => {});
  }, [accessToken, sessionId, user]);

  function toggleTag(tag: string) {
    setTags((prev) => {
      const next = new Set(prev);
      if (next.has(tag)) next.delete(tag);
      else next.add(tag);
      return next;
    });
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!accessToken || !sessionId) return;
    if (rating === 0) {
      setError("별점을 선택해주세요.");
      return;
    }
    setError(null);
    setIsSubmitting(true);
    try {
      // 한 줄 후기 전용 필드가 없어 태그 목록에 함께 실어 보낸다(handoff B-11과 같은 맥락).
      const payloadTags = comment.trim()
        ? [...Array.from(tags), `한줄:${comment.trim()}`]
        : Array.from(tags);
      await trustApi.submitEvaluation(Number(sessionId), rating, payloadTags, accessToken);
      navigate("/home");
    } catch (err) {
      setError(err instanceof Error ? err.message : "평가를 제출하지 못했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!accessToken) return null;

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-4">
        <PageHeader title="돌봄 마무리" backTo={`/care/requests/${sessionId}`} />

        <div className="text-center">
          <h2 className="text-lg font-bold leading-snug text-foreground">
            {partnerName} 님과의 돌봄,
            <br />
            어떠셨나요?
          </h2>
          <p className="mt-2 text-[11px] text-muted-foreground">
            평가는 상호 제출 후에만 서로에게 공개됩니다.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          <div className="flex flex-col items-center gap-2">
            <div className="flex gap-1.5">
              {[1, 2, 3, 4, 5].map((value) => (
                <button
                  key={value}
                  type="button"
                  aria-label={`별점 ${value}점`}
                  onClick={() => setRating(value)}
                  className="border-0 bg-transparent p-0"
                >
                  <svg
                    viewBox="0 0 24 24"
                    className="h-9 w-9"
                    fill={value <= rating ? "hsl(var(--primary))" : "none"}
                    stroke="hsl(var(--primary))"
                    strokeWidth={1.5}
                  >
                    <path
                      d="m12 3.5 2.6 5.4 5.9.8-4.3 4.1 1 5.9-5.2-2.8-5.2 2.8 1-5.9L3.5 9.7l5.9-.8L12 3.5Z"
                      strokeLinejoin="round"
                    />
                  </svg>
                </button>
              ))}
            </div>
            {rating > 0 && (
              <span className="text-xs font-medium text-foreground">{RATING_LABELS[rating]}</span>
            )}
          </div>

          <div>
            <div className="mb-2 text-xs font-semibold text-foreground">특히 좋았던 점</div>
            <div className="flex flex-wrap gap-2">
              {POSITIVE_TAGS.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => toggleTag(tag)}
                  className={
                    tags.has(tag)
                      ? "rounded-full border-0 bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground"
                      : "rounded-full border border-border bg-secondary px-3 py-1.5 text-xs text-foreground"
                  }
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label htmlFor="comment" className="sr-only">
              한 줄 후기
            </label>
            <textarea
              id="comment"
              rows={3}
              value={comment}
              onChange={(event) => setComment(event.target.value)}
              placeholder="한 줄 남겨주세요 (선택)"
              className="w-full rounded-xl border border-border bg-secondary px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground"
            />
          </div>

          <p className="rounded-xl bg-secondary p-3 text-[11px] leading-relaxed text-muted-foreground">
            평가를 제출하면 신뢰 프로필이 갱신되고, 공동육아 기록으로 인정됩니다.
          </p>

          {error && (
            <p className="rounded-lg bg-destructive/10 px-3 py-2.5 text-xs text-destructive">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-full border-0 bg-primary px-3 py-3 text-sm font-semibold text-primary-foreground disabled:opacity-60"
          >
            {isSubmitting ? "제출 중..." : "평가 제출"}
          </button>
        </form>
      </div>
    </main>
  );
}
