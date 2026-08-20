import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import * as careApi from "@/api/care";
import * as childrenApi from "@/api/children";
import type { ChildResponse } from "@/api/childrenTypes";
import * as guardianProfileApi from "@/api/guardianProfile";
import { useAuth } from "@/hooks/useAuth";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

// 30분 단위 슬롯(0~47)을 "HH:MM"으로 표시 — app/core/utils/schedule_slots.py와 동일 규칙.
function slotToTime(slot: number): string {
  const hour = Math.floor(slot / 2)
    .toString()
    .padStart(2, "0");
  const minute = slot % 2 === 0 ? "00" : "30";
  return `${hour}:${minute}`;
}

const SLOTS = Array.from({ length: 48 }, (_, i) => i);

export default function CareRequestPage() {
  const { accessToken } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const providerId = Number(searchParams.get("providerId"));
  const providerNickname = searchParams.get("nickname");

  const [children, setChildren] = useState<ChildResponse[] | null>(null);
  // 약속 장소는 요청자 본인 거주지 H3를 그대로 쓴다(REQ-NF-SEC-05, 별도 지도 선택 UI는 범위 밖).
  const [meetingH3, setMeetingH3] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [childId, setChildId] = useState<number | "">("");
  const [careDate, setCareDate] = useState(today());
  const [startSlot, setStartSlot] = useState(18); // 09:00
  const [endSlot, setEndSlot] = useState(22); // 11:00

  useEffect(() => {
    if (!accessToken) return;
    childrenApi
      .listChildren(accessToken)
      .then(setChildren)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "아동 목록을 불러오지 못했습니다."),
      );
    guardianProfileApi
      .getGuardianProfile(accessToken)
      .then((profile) => setMeetingH3(profile.residence_h3))
      .catch((err) =>
        setError(err instanceof Error ? err.message : "프로필을 불러오지 못했습니다."),
      );
  }, [accessToken]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!accessToken || !childId || !meetingH3) return;
    setError(null);
    setIsSubmitting(true);
    try {
      const created = await careApi.createRequest(
        {
          provider_id: providerId,
          child_id: childId,
          meeting_h3: meetingH3,
          care_date: careDate,
          start_slot: startSlot,
          end_slot: endSlot,
        },
        accessToken,
      );
      navigate(`/care/requests/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "요청을 보내지 못했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!accessToken) return null;
  if (!providerId) {
    return (
      <main className="flex min-h-screen justify-center bg-background px-6 py-10">
        <p className="text-xs text-destructive">상대를 먼저 매칭 후보에서 선택해주세요.</p>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-4">
        <h1 className="text-sm font-medium text-foreground">
          {providerNickname ?? "상대"}님께 돌봄 요청
        </h1>

        {children === null && !error && (
          <p className="text-xs text-muted-foreground">불러오는 중...</p>
        )}

        {children && (
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <div>
              <label htmlFor="childId" className="mb-1 block text-xs text-muted-foreground">
                맡길 아동
              </label>
              <select
                id="childId"
                required
                value={childId}
                onChange={(event) => setChildId(Number(event.target.value))}
                className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground"
              >
                <option value="" disabled>
                  선택하세요
                </option>
                {children.map((child) => (
                  <option key={child.id} value={child.id}>
                    {child.months_old}개월 아동
                  </option>
                ))}
              </select>
              {children.length === 0 && (
                <p className="mt-1 text-[11px] text-destructive">
                  등록된 아동이 없습니다. 먼저 아동을 등록해주세요.
                </p>
              )}
            </div>

            <div>
              <label htmlFor="careDate" className="mb-1 block text-xs text-muted-foreground">
                돌봄 날짜
              </label>
              <input
                id="careDate"
                type="date"
                required
                value={careDate}
                onChange={(event) => setCareDate(event.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground"
              />
            </div>

            <div className="flex gap-3">
              <div className="flex-1">
                <label htmlFor="startSlot" className="mb-1 block text-xs text-muted-foreground">
                  시작
                </label>
                <select
                  id="startSlot"
                  value={startSlot}
                  onChange={(event) => setStartSlot(Number(event.target.value))}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground"
                >
                  {SLOTS.map((slot) => (
                    <option key={slot} value={slot}>
                      {slotToTime(slot)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex-1">
                <label htmlFor="endSlot" className="mb-1 block text-xs text-muted-foreground">
                  종료
                </label>
                <select
                  id="endSlot"
                  value={endSlot}
                  onChange={(event) => setEndSlot(Number(event.target.value))}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground"
                >
                  {SLOTS.filter((slot) => slot > startSlot).map((slot) => (
                    <option key={slot} value={slot}>
                      {slotToTime(slot)}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {error && (
              <p className="rounded-lg bg-destructive/10 px-3 py-2.5 text-xs text-destructive">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={!childId || !meetingH3 || isSubmitting}
              className="rounded-lg bg-primary px-3 py-3 text-sm font-medium text-primary-foreground disabled:opacity-60"
            >
              {isSubmitting ? "보내는 중..." : "요청 보내기"}
            </button>
          </form>
        )}
      </div>
    </main>
  );
}
