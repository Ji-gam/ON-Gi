import { useEffect, useState, type FormEvent } from "react";

import { ApiError } from "@/api/client";
import * as workScheduleApi from "@/api/workSchedule";
import type { ShiftTemplate, WorkScheduleResponse } from "@/api/workScheduleTypes";
import { useAuth } from "@/hooks/useAuth";

const SHIFT_TEMPLATES: ShiftTemplate[] = ["DAY", "EVENING", "NIGHT", "OFF"];

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function WorkSchedulePage() {
  const { accessToken } = useAuth();
  const [schedule, setSchedule] = useState<WorkScheduleResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [workDate, setWorkDate] = useState(today());
  const [template, setTemplate] = useState<ShiftTemplate | "">("");

  function loadSchedule() {
    if (!accessToken) return;
    workScheduleApi
      .getSchedule(today(), undefined, accessToken)
      .then(setSchedule)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "근무표를 불러오지 못했습니다."),
      );
  }

  useEffect(loadSchedule, [accessToken]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!accessToken) return;
    setError(null);
    setIsSubmitting(true);
    try {
      await workScheduleApi.registerShift(
        { work_date: workDate, template: template as ShiftTemplate },
        accessToken,
      );
      loadSchedule();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "등록에 실패했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!accessToken) return null;

  return (
    <main>
      <h1>근무표</h1>

      <section>
        <h2>등록된 근무 (오늘부터 30일)</h2>
        {schedule === null && !error && <p>불러오는 중...</p>}
        {schedule && schedule.length === 0 && <p>등록된 근무가 없습니다.</p>}
        {schedule && schedule.length > 0 && (
          <ul>
            {schedule.map((entry) => (
              <li key={entry.work_date}>
                {entry.work_date} · {entry.shift_template}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2>근무 등록</h2>
        <form onSubmit={handleSubmit}>
          <div>
            <label htmlFor="workDate">근무일</label>
            <input
              id="workDate"
              type="date"
              required
              value={workDate}
              onChange={(event) => setWorkDate(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor="template">근무 템플릿</label>
            <select
              id="template"
              required
              value={template}
              onChange={(event) => setTemplate(event.target.value as ShiftTemplate)}
            >
              <option value="" disabled>
                선택
              </option>
              {SHIFT_TEMPLATES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          {error && <p>{error}</p>}
          <button type="submit" disabled={!template || isSubmitting}>
            {isSubmitting ? "등록 중..." : "등록"}
          </button>
        </form>
      </section>
    </main>
  );
}
