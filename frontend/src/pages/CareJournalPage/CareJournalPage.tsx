import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";

import * as careApi from "@/api/care";
import type { CareSessionResponse } from "@/api/careTypes";
import * as childrenApi from "@/api/children";
import type { ChildDetailResponse } from "@/api/childrenTypes";
import PageHeader from "@/components/common/PageHeader";
import { useAuth } from "@/hooks/useAuth";

const MOODS = ["평소와 비슷했어요", "아주 잘 지냈어요", "조금 힘들어했어요"];

// 백엔드 CareLog에는 태그 배열 필드가 없어, 선택한 태그를 note 앞에 함께 저장한다.
// 전용 필드는 docs/backend-handoff.txt B-11로 요청해둔 상태.
const RECORD_TAGS = ["간식 먹었어요", "낮잠 없음", "바깥 놀이", "투약", "다툼"];

export default function CareJournalPage() {
  const { sessionId } = useParams();
  const { accessToken } = useAuth();
  const navigate = useNavigate();

  const [careSession, setCareSession] = useState<CareSessionResponse | null>(null);
  const [child, setChild] = useState<ChildDetailResponse | null>(null);
  const [mood, setMood] = useState<string>("");
  const [tags, setTags] = useState<Set<string>>(new Set());
  const [note, setNote] = useState("");
  const [allergyNote, setAllergyNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!accessToken || !sessionId) return;
    careApi
      .getRequest(Number(sessionId), accessToken)
      .then(setCareSession)
      .catch((err) => setError(err instanceof Error ? err.message : "세션을 불러오지 못했습니다."));
    careApi
      .getJournal(Number(sessionId), accessToken)
      .then((journal) => {
        if (!journal) return;
        if (journal.mood) setMood(journal.mood);
        if (journal.note) setNote(journal.note);
        if (journal.allergy_note) setAllergyNote(journal.allergy_note);
      })
      .catch(() => {});
  }, [accessToken, sessionId]);

  useEffect(() => {
    if (!accessToken || !careSession) return;
    childrenApi
      .getChild(careSession.child_id, accessToken)
      .then(setChild)
      .catch(() => setChild(null));
  }, [accessToken, careSession]);

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
    setError(null);
    setIsSubmitting(true);
    try {
      const tagLine = tags.size > 0 ? `[${Array.from(tags).join(", ")}] ` : "";
      await careApi.upsertJournal(
        Number(sessionId),
        {
          mood: mood || null,
          note: `${tagLine}${note}`.trim() || null,
          allergy_note: allergyNote || null,
        },
        accessToken,
      );
      await careApi.checkout(Number(sessionId), accessToken);
      navigate(`/care/requests/${sessionId}/done`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "저장하지 못했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!accessToken) return null;

  const hasAllergy = !!child?.allergies;

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-4">
        <PageHeader
          title="돌봄일지"
          backTo={`/care/requests/${sessionId}`}
          right={
            <span className="rounded-full bg-destructive/10 px-2 py-0.5 text-[10px] font-semibold text-destructive">
              필수
            </span>
          }
        />

        <p className="rounded-2xl bg-secondary p-4 text-[11px] leading-relaxed text-muted-foreground">
          일지를 작성하지 않으면 노쇼 방지 포인트 정산이 보류됩니다. 3줄이면 충분합니다.
        </p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          <div>
            <div className="mb-2 text-xs font-semibold text-foreground">오늘 아이는 어땠나요?</div>
            <div className="flex gap-2">
              {MOODS.map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setMood(value)}
                  className={
                    mood === value
                      ? "flex-1 rounded-xl border-2 border-primary bg-secondary px-2 py-3 text-[11px] font-semibold leading-tight text-foreground"
                      : "flex-1 rounded-xl border border-border bg-secondary px-2 py-3 text-[11px] leading-tight text-foreground"
                  }
                >
                  {value}
                </button>
              ))}
            </div>
          </div>

          <div>
            <div className="mb-2 text-xs font-semibold text-foreground">기록</div>
            <div className="flex flex-wrap gap-2">
              {RECORD_TAGS.map((tag) => (
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
            <label htmlFor="note" className="sr-only">
              돌봄 기록
            </label>
            <textarea
              id="note"
              rows={4}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="어떻게 지냈는지 편하게 적어주세요."
              className="w-full rounded-xl border border-border bg-secondary px-3 py-2.5 text-sm leading-relaxed text-foreground placeholder:text-muted-foreground"
            />
          </div>

          {hasAllergy && (
            <div>
              <label
                htmlFor="allergyNote"
                className="mb-1 block text-xs font-semibold text-destructive"
              >
                알레르기 관련 확인 <span className="text-destructive">*</span>
              </label>
              <input
                id="allergyNote"
                required
                value={allergyNote}
                onChange={(event) => setAllergyNote(event.target.value)}
                placeholder={`${child?.allergies} — 어떻게 관리했는지 적어주세요`}
                className="w-full rounded-lg border border-border bg-secondary px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground"
              />
              <p className="mt-1 text-[11px] text-muted-foreground">
                알레르기가 등록된 아동은 이 항목을 적어야 저장됩니다.
              </p>
            </div>
          )}

          <div className="rounded-xl border border-dashed border-border bg-secondary p-3 text-[11px] leading-relaxed text-muted-foreground">
            사진 첨부는 업로드 기능이 준비되면 열립니다. 사진은 상대 보호자에게만 보이며 30일 후
            자동 삭제될 예정입니다.
          </div>

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
            {isSubmitting ? "저장 중..." : "일지 저장하고 체크아웃"}
          </button>
        </form>
      </div>
    </main>
  );
}
