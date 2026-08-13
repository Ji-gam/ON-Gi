import { useEffect, useState, type FormEvent } from "react";

import { ApiError } from "@/api/client";
import * as parentingValuesApi from "@/api/parentingValues";
import type { BaumrindQuestionItem, ParentingValuesResponse } from "@/api/parentingValuesTypes";
import { useAuth } from "@/hooks/useAuth";

const SCALE_LABELS = ["전혀 아니다", "아니다", "보통이다", "그렇다", "매우 그렇다"];

export default function ParentingValuesPage() {
  const { accessToken } = useAuth();
  const [questions, setQuestions] = useState<BaumrindQuestionItem[] | null>(null);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [result, setResult] = useState<ParentingValuesResponse | null>(null);
  const [narrative, setNarrative] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmittingQuestionnaire, setIsSubmittingQuestionnaire] = useState(false);
  const [isSubmittingNarrative, setIsSubmittingNarrative] = useState(false);

  useEffect(() => {
    parentingValuesApi
      .getQuestions()
      .then(setQuestions)
      .catch((err) => setError(err instanceof Error ? err.message : "문항을 불러오지 못했습니다."));
  }, []);

  useEffect(() => {
    if (!accessToken) return;
    parentingValuesApi
      .getParentingValues(accessToken)
      .then((res) => {
        setResult(res);
        setNarrative(res.narrative ?? "");
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status !== 404) setError(err.message);
      });
  }, [accessToken]);

  async function handleSubmitQuestionnaire(event: FormEvent) {
    event.preventDefault();
    if (!accessToken || !questions) return;
    setError(null);
    setIsSubmittingQuestionnaire(true);
    try {
      const orderedAnswers = questions.map((q) => answers[q.index]);
      const res = await parentingValuesApi.submitQuestionnaire(
        { answers: orderedAnswers },
        accessToken,
      );
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "제출에 실패했습니다.");
    } finally {
      setIsSubmittingQuestionnaire(false);
    }
  }

  async function handleSubmitNarrative(event: FormEvent) {
    event.preventDefault();
    if (!accessToken) return;
    setError(null);
    setIsSubmittingNarrative(true);
    try {
      const res = await parentingValuesApi.submitNarrative({ narrative }, accessToken);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "제출에 실패했습니다.");
    } finally {
      setIsSubmittingNarrative(false);
    }
  }

  if (!accessToken) return null;

  const allAnswered = !!questions && questions.every((q) => answers[q.index] != null);
  const answeredCount = questions ? questions.filter((q) => answers[q.index] != null).length : 0;

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-6">
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-secondary px-2 py-1 text-[11px] font-medium text-primary">
            4/5
          </span>
          <h1 className="text-sm font-medium text-foreground">양육 가치관 진단</h1>
        </div>

        {result && (
          <section className="flex flex-col gap-1 rounded-xl border border-border bg-secondary p-4">
            <h2 className="text-xs font-medium text-muted-foreground">진단 결과</h2>
            <div className="flex justify-between text-xs text-foreground">
              <span>온기 점수</span>
              <span className="font-medium">{result.warmth_score}</span>
            </div>
            <div className="flex justify-between text-xs text-foreground">
              <span>통제 점수</span>
              <span className="font-medium">{result.control_score}</span>
            </div>
            <div className="flex justify-between text-xs text-foreground">
              <span>유형</span>
              <span className="font-medium">{result.type_label}</span>
            </div>
          </section>
        )}

        <section className="flex flex-col gap-3">
          {questions === null && !error && (
            <p className="text-xs text-muted-foreground">불러오는 중...</p>
          )}
          {questions && (
            <>
              <div>
                <div className="mb-1 text-[11px] text-muted-foreground">
                  {answeredCount}/{questions.length} 문항
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-secondary">
                  <div
                    className="h-full bg-primary"
                    style={{ width: `${(answeredCount / questions.length) * 100}%` }}
                  />
                </div>
              </div>

              <form onSubmit={handleSubmitQuestionnaire} className="flex flex-col gap-4">
                {questions.map((question) => (
                  <fieldset
                    key={question.index}
                    className="flex flex-col gap-2 rounded-xl border border-border bg-secondary p-4"
                  >
                    <legend className="mb-1 text-xs leading-relaxed text-foreground">
                      {question.text}
                    </legend>
                    <div className="flex flex-col gap-1.5">
                      {[1, 2, 3, 4, 5].map((value) => (
                        <label
                          key={value}
                          className="flex items-center gap-2 text-xs text-foreground"
                        >
                          <input
                            type="radio"
                            name={`question-${question.index}`}
                            value={value}
                            checked={answers[question.index] === value}
                            onChange={() =>
                              setAnswers((prev) => ({ ...prev, [question.index]: value }))
                            }
                            className="h-3.5 w-3.5 accent-primary"
                          />
                          {SCALE_LABELS[value - 1]}
                        </label>
                      ))}
                    </div>
                  </fieldset>
                ))}
                {error && (
                  <p className="rounded-lg bg-destructive/10 px-3 py-2.5 text-xs text-destructive">
                    {error}
                  </p>
                )}
                <button
                  type="submit"
                  disabled={!allAnswered || isSubmittingQuestionnaire}
                  className="rounded-lg bg-primary px-3 py-3 text-sm font-medium text-primary-foreground disabled:opacity-60"
                >
                  {isSubmittingQuestionnaire ? "제출 중..." : "제출"}
                </button>
              </form>
            </>
          )}
        </section>

        <section className="flex flex-col gap-2.5 rounded-xl border border-border bg-secondary p-4">
          <h2 className="text-xs font-medium text-muted-foreground">자유 서술 보정 (선택)</h2>
          <form onSubmit={handleSubmitNarrative} className="flex flex-col gap-2.5">
            <label htmlFor="narrative" className="sr-only">
              양육 경험 서술
            </label>
            <textarea
              id="narrative"
              maxLength={2000}
              rows={3}
              placeholder="양육 경험을 자유롭게 적어주세요"
              value={narrative}
              onChange={(event) => setNarrative(event.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground"
            />
            <button
              type="submit"
              disabled={!narrative || isSubmittingNarrative}
              className="self-end rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium text-foreground disabled:opacity-60"
            >
              {isSubmittingNarrative ? "제출 중..." : "제출"}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}
