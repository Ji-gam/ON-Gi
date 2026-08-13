import { useEffect, useRef, useState, type FormEvent } from "react";

import * as workScheduleApi from "@/api/workSchedule";
import type { ShiftTemplate, WorkScheduleResponse } from "@/api/workScheduleTypes";
import { useAuth } from "@/hooks/useAuth";

const SHIFT_TEMPLATES: ShiftTemplate[] = ["DAY", "EVENING", "NIGHT", "OFF"];

const SHIFT_TEMPLATE_LABELS: Record<ShiftTemplate, string> = {
  DAY: "낮 근무 (D)",
  EVENING: "저녁 근무 (E)",
  NIGHT: "밤 근무 (N)",
  OFF: "휴무 (OFF)",
};

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

  const [scheduleFileName, setScheduleFileName] = useState<string | null>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function loadSchedule() {
    if (!accessToken) return;
    workScheduleApi
      .getSchedule(today(), undefined, accessToken)
      .then(setSchedule)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "근무표를 불러오지 못했습니다."),
      );
  }

  useEffect(loadSchedule, [accessToken]);

  function handlePhotoSelected(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    setScheduleFileName(file ? file.name : null);
  }

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
      setError(err instanceof Error ? err.message : "등록에 실패했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!accessToken) return null;

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-6">
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-secondary px-2 py-1 text-[11px] font-medium text-primary">
            5/5
          </span>
          <h1 className="text-sm font-medium text-foreground">근무표 등록</h1>
        </div>

        <section className="flex flex-col gap-2 rounded-xl border border-dashed border-border bg-secondary p-4">
          <h2 className="text-xs font-medium text-foreground">
            근무표 사진으로 등록{" "}
            <span className="text-[11px] font-normal text-muted-foreground">(선택)</span>
          </h2>
          <p className="text-[11px] text-muted-foreground">
            사진을 올려두면 자동 인식 기능이 준비되는 대로 반영해드려요. 지금은 아래에서 직접
            등록해주세요.
          </p>
          <div className="flex gap-2">
            <input
              ref={cameraInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              className="hidden"
              onChange={handlePhotoSelected}
            />
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={handlePhotoSelected}
            />
            <button
              type="button"
              onClick={() => cameraInputRef.current?.click()}
              className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium text-foreground"
            >
              사진 찍기
            </button>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium text-foreground"
            >
              사진 등록
            </button>
          </div>
          {scheduleFileName && (
            <p className="text-[11px] text-muted-foreground">선택된 파일: {scheduleFileName}</p>
          )}
        </section>

        <section className="flex flex-col gap-2.5">
          <h2 className="text-xs font-medium text-muted-foreground">등록된 근무 (오늘부터 30일)</h2>
          {schedule === null && !error && (
            <p className="text-xs text-muted-foreground">불러오는 중...</p>
          )}
          {schedule && schedule.length === 0 && (
            <p className="text-xs text-muted-foreground">등록된 근무가 없습니다.</p>
          )}
          {schedule && schedule.length > 0 && (
            <ul className="flex flex-col gap-2">
              {schedule.map((entry) => (
                <li
                  key={entry.work_date}
                  className="flex items-center justify-between rounded-xl border border-border bg-secondary px-4 py-3 text-xs text-foreground"
                >
                  <span>{entry.work_date}</span>
                  <span className="font-medium">{SHIFT_TEMPLATE_LABELS[entry.shift_template]}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="flex flex-col gap-2.5 rounded-xl border border-border bg-secondary p-4">
          <h2 className="text-xs font-medium text-muted-foreground">근무 등록</h2>
          <form onSubmit={handleSubmit} className="flex flex-col gap-2.5">
            <div>
              <label htmlFor="workDate" className="mb-1 block text-xs text-muted-foreground">
                근무일
              </label>
              <input
                id="workDate"
                type="date"
                required
                value={workDate}
                onChange={(event) => setWorkDate(event.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground"
              />
            </div>
            <div>
              <div className="mb-2 text-xs text-muted-foreground">근무 템플릿</div>
              <div className="flex flex-wrap gap-2">
                {SHIFT_TEMPLATES.map((value) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setTemplate(value)}
                    className={
                      template === value
                        ? "rounded-full bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground"
                        : "rounded-full border border-border bg-background px-3 py-1.5 text-xs text-foreground"
                    }
                  >
                    {SHIFT_TEMPLATE_LABELS[value]}
                  </button>
                ))}
              </div>
            </div>
            {error && (
              <p className="rounded-lg bg-destructive/10 px-3 py-2.5 text-xs text-destructive">
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={!template || isSubmitting}
              className="rounded-lg bg-primary px-3 py-3 text-sm font-medium text-primary-foreground disabled:opacity-60"
            >
              {isSubmitting ? "등록 중..." : "등록"}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}
