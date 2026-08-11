import { useEffect, useState, type FormEvent } from "react";

import { ApiError } from "@/api/client";
import * as parentingValuesApi from "@/api/parentingValues";
import type { BaumrindQuestionItem, ParentingValuesResponse } from "@/api/parentingValuesTypes";
import { useAuth } from "@/hooks/useAuth";

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
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "문항을 불러오지 못했습니다."),
      );
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
      setError(err instanceof ApiError ? err.message : "제출에 실패했습니다.");
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
      setError(err instanceof ApiError ? err.message : "제출에 실패했습니다.");
    } finally {
      setIsSubmittingNarrative(false);
    }
  }

  if (!accessToken) return null;

  const allAnswered = !!questions && questions.every((q) => answers[q.index] != null);

  return (
    <main>
      <h1>양육 가치관 진단</h1>

      {result && (
        <section>
          <h2>진단 결과</h2>
          <p>온기 점수: {result.warmth_score}</p>
          <p>통제 점수: {result.control_score}</p>
          <p>유형: {result.type_label}</p>
        </section>
      )}

      <section>
        <h2>바움린드 8문항</h2>
        {questions === null && !error && <p>불러오는 중...</p>}
        {questions && (
          <form onSubmit={handleSubmitQuestionnaire}>
            {questions.map((question) => (
              <fieldset key={question.index}>
                <legend>{question.text}</legend>
                {[1, 2, 3, 4, 5].map((value) => (
                  <label key={value}>
                    <input
                      type="radio"
                      name={`question-${question.index}`}
                      value={value}
                      checked={answers[question.index] === value}
                      onChange={() => setAnswers((prev) => ({ ...prev, [question.index]: value }))}
                    />
                    {value}
                  </label>
                ))}
              </fieldset>
            ))}
            {error && <p>{error}</p>}
            <button type="submit" disabled={!allAnswered || isSubmittingQuestionnaire}>
              {isSubmittingQuestionnaire ? "제출 중..." : "제출"}
            </button>
          </form>
        )}
      </section>

      <section>
        <h2>자유 서술 보정</h2>
        <form onSubmit={handleSubmitNarrative}>
          <div>
            <label htmlFor="narrative">양육 경험 서술</label>
            <textarea
              id="narrative"
              maxLength={2000}
              value={narrative}
              onChange={(event) => setNarrative(event.target.value)}
            />
          </div>
          <button type="submit" disabled={!narrative || isSubmittingNarrative}>
            {isSubmittingNarrative ? "제출 중..." : "제출"}
          </button>
        </form>
      </section>
    </main>
  );
}
