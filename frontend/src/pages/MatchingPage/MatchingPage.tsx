import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import * as matchingApi from "@/api/matching";
import type { CandidateResponse } from "@/api/matchingTypes";
import * as workScheduleApi from "@/api/workSchedule";
import type { WorkScheduleResponse } from "@/api/workScheduleTypes";
import PageHeader from "@/components/common/PageHeader";
import SafetyBadge from "@/components/common/SafetyBadge";
import ShiftWeekGrid, { type DayState } from "@/components/common/ShiftWeekGrid";
import { useAuth } from "@/hooks/useAuth";

type TabKey = "general" | "shift" | "pod";

const TABS: { key: TabKey; label: string }[] = [
  { key: "general", label: "일반" },
  { key: "shift", label: "교대근무" },
  { key: "pod", label: "Pod" },
];

const TIME_SLOTS = ["평일 저녁", "평일 오전", "주말", "야간", "등하원"];
const AGE_RANGES = ["0-2세", "3-5세", "6-8세", "9세 이상"];
const TRUST_FILTERS = ["L2 이상", "L3 단독위탁 가능", "비흡연 가정", "반려동물 없음"];

function trustLevelBadge(score: number): string {
  if (score >= 0.7) return "L3";
  if (score >= 0.4) return "L2";
  return "L1";
}

function walkMinutes(distanceM: number): number {
  return Math.round(distanceM / 80);
}

// 날짜별 48슬롯 마스크를 요일 상태로 환산한다. 비트가 1이면 돌봄 가능한 슬롯이다.
function toDayStates(schedule: WorkScheduleResponse[]): DayState[] {
  const byWeekday = new Map<number, WorkScheduleResponse>();
  for (const entry of schedule) {
    const weekday = (new Date(`${entry.work_date}T00:00:00`).getDay() + 6) % 7; // 월=0
    if (!byWeekday.has(weekday)) byWeekday.set(weekday, entry);
  }
  return Array.from({ length: 7 }, (_, weekday) => {
    const entry = byWeekday.get(weekday);
    if (!entry) return "off";
    if (entry.shift_template === "OFF") return "off";
    return "work";
  });
}

export default function MatchingPage() {
  const { accessToken } = useAuth();
  const [tab, setTab] = useState<TabKey>("general");
  const [candidates, setCandidates] = useState<CandidateResponse[] | null>(null);
  const [mySchedule, setMySchedule] = useState<WorkScheduleResponse[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [showFilter, setShowFilter] = useState(false);
  const [timeSlots, setTimeSlots] = useState<Set<string>>(new Set());
  const [ageRanges, setAgeRanges] = useState<Set<string>>(new Set());
  const [trustFilters, setTrustFilters] = useState<Set<string>>(new Set());
  const [maxWalkMinutes, setMaxWalkMinutes] = useState(20);

  useEffect(() => {
    if (!accessToken) return;
    matchingApi
      .getCandidates(accessToken)
      .then(setCandidates)
      .catch((err) => setError(err instanceof Error ? err.message : "후보를 불러오지 못했습니다."));

    const today = new Date().toISOString().slice(0, 10);
    workScheduleApi
      .getSchedule(today, undefined, accessToken)
      .then(setMySchedule)
      .catch(() => setMySchedule([]));
  }, [accessToken]);

  // 백엔드 필터 파라미터가 아직 없어 클라이언트에서 거른다(handoff B-5).
  const filtered = useMemo(() => {
    if (!candidates) return null;
    return candidates.filter((candidate) => {
      if (walkMinutes(candidate.distance_m) > maxWalkMinutes) return false;
      if (trustFilters.has("L2 이상") && candidate.trust_score < 0.4) return false;
      if (trustFilters.has("L3 단독위탁 가능") && candidate.trust_score < 0.7) return false;
      return true;
    });
  }, [candidates, maxWalkMinutes, trustFilters]);

  const activeFilterCount = timeSlots.size + ageRanges.size + trustFilters.size;

  function toggle(set: Set<string>, apply: (next: Set<string>) => void, value: string) {
    const next = new Set(set);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    apply(next);
  }

  if (!accessToken) return null;

  const myDays = toDayStates(mySchedule);

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-3 pb-4">
        <PageHeader title="매칭" right={<SafetyBadge />} />

        <div className="flex items-center justify-between">
          <div className="flex gap-2">
            {TABS.map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => setTab(item.key)}
                className={
                  tab === item.key
                    ? "rounded-full border-0 bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground"
                    : "rounded-full border border-border bg-secondary px-3 py-1.5 text-xs text-foreground"
                }
              >
                {item.label}
              </button>
            ))}
          </div>
          {tab === "general" && (
            <button
              type="button"
              onClick={() => setShowFilter(true)}
              className="rounded-full border border-border bg-secondary px-3 py-1.5 text-xs text-foreground"
            >
              필터{activeFilterCount > 0 ? ` ${activeFilterCount}` : ""}
            </button>
          )}
        </div>

        {error && (
          <p className="rounded-lg bg-destructive/10 px-3 py-2.5 text-xs text-destructive">
            {error}
          </p>
        )}

        {tab === "general" && (
          <>
            <p className="text-[11px] text-muted-foreground">
              가치관 궁합 순 · 안전 하드필터 통과 {filtered?.length ?? 0}명
            </p>
            {filtered === null && !error && (
              <p className="text-xs text-muted-foreground">불러오는 중...</p>
            )}
            {filtered && filtered.length === 0 && (
              <div className="rounded-2xl border border-border bg-secondary p-4">
                <p className="text-xs text-foreground">조건에 맞는 이웃이 없어요.</p>
                <p className="mt-1 text-[11px] text-muted-foreground">
                  거리 범위를 넓히거나 선택한 태그를 줄여보세요.
                </p>
              </div>
            )}
            <ul className="flex list-none flex-col gap-2.5">
              {filtered?.map((candidate) => (
                <li
                  key={candidate.user_id}
                  className="flex flex-col gap-2.5 rounded-2xl border border-border bg-secondary p-3"
                >
                  <Link to={`/matching/${candidate.user_id}`} className="flex flex-col gap-2">
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
                        {candidate.nickname.slice(0, 1)}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5">
                          <span className="text-xs font-semibold text-foreground">
                            {candidate.nickname} 님
                          </span>
                          <span className="rounded-full bg-background px-1.5 py-0.5 text-[10px] font-semibold text-primary">
                            {trustLevelBadge(candidate.trust_score)}
                          </span>
                        </div>
                        <div className="text-[11px] text-muted-foreground">
                          도보 {walkMinutes(candidate.distance_m)}분
                        </div>
                      </div>
                      <span className="shrink-0 text-xs font-bold text-primary">
                        {Math.round(candidate.total_score * 100)}%
                      </span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-background">
                      <div
                        className="h-full bg-primary"
                        style={{ width: `${Math.round(candidate.total_score * 100)}%` }}
                      />
                    </div>
                    <p className="rounded-xl bg-background p-2.5 text-[11px] leading-relaxed text-foreground">
                      {candidate.reason}
                    </p>
                  </Link>
                  <div className="flex gap-2">
                    <Link
                      to={`/matching/${candidate.user_id}`}
                      className="flex-1 rounded-full border border-border bg-background px-3 py-2 text-center text-[11px] font-medium text-foreground"
                    >
                      궁합 자세히
                    </Link>
                    <Link
                      to={`/trust/${candidate.user_id}/joint-sessions/new`}
                      className="flex-1 rounded-full bg-primary px-3 py-2 text-center text-[11px] font-semibold text-primary-foreground"
                    >
                      첫 만남 요청
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}

        {tab === "shift" && (
          <>
            <p className="rounded-2xl bg-secondary p-4 text-[11px] leading-relaxed text-foreground">
              내 근무표와 <span className="font-semibold">엇갈리는</span> 이웃을 먼저 보여드립니다.
              서로의 빈 시간이 맞물릴 때 품앗이가 오래 갑니다.
            </p>
            <ul className="flex list-none flex-col gap-2.5">
              {filtered?.map((candidate) => (
                <li
                  key={candidate.user_id}
                  className="flex flex-col gap-3 rounded-2xl border border-border bg-secondary p-3"
                >
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
                      {candidate.nickname.slice(0, 1)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-semibold text-foreground">
                        {candidate.nickname} 님
                      </div>
                      <div className="text-[11px] text-muted-foreground">
                        상보성 {Math.round(candidate.complementary_score * 100)}% · 도보{" "}
                        {walkMinutes(candidate.distance_m)}분
                      </div>
                    </div>
                  </div>
                  <ShiftWeekGrid
                    rows={[
                      { label: "나", days: myDays },
                      {
                        label: candidate.nickname.slice(0, 2),
                        // 상대 근무표 조회 API가 없어 내 근무의 반대로 근사 표시한다(handoff B-13).
                        days: myDays.map((state) =>
                          state === "work" ? "available" : state === "off" ? "off" : "work",
                        ),
                      },
                    ]}
                  />
                  <p className="rounded-xl bg-background p-2.5 text-[11px] leading-relaxed text-foreground">
                    {candidate.reason}
                  </p>
                  <div className="flex gap-2">
                    <Link
                      to={`/matching/${candidate.user_id}`}
                      className="flex-1 rounded-full border border-border bg-background px-3 py-2 text-center text-[11px] font-medium text-foreground"
                    >
                      근무표 겹쳐보기
                    </Link>
                    <Link
                      to={`/trust/${candidate.user_id}/joint-sessions/new`}
                      className="flex-1 rounded-full bg-primary px-3 py-2 text-center text-[11px] font-semibold text-primary-foreground"
                    >
                      첫 만남 요청
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
            <p className="rounded-xl border border-dashed border-border p-3 text-[11px] text-muted-foreground">
              상대 근무표는 조회 API가 준비되면 실제 값으로 표시됩니다. 지금은 상보 스코어를
              기준으로 한 근사 표시입니다.
            </p>
          </>
        )}

        {tab === "pod" && (
          <div className="rounded-2xl border border-dashed border-border bg-secondary p-5 text-center">
            <p className="text-xs font-semibold text-foreground">Pod은 준비 중입니다</p>
            <p className="mt-1.5 text-[11px] leading-relaxed text-muted-foreground">
              신뢰가 쌓인 4~6가구가 상시로 서로를 돌보는 그룹이에요. 백엔드 API가 준비되면 모집
              현황과 가입 신청이 열립니다.
            </p>
          </div>
        )}
      </div>

      {showFilter && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-foreground/40">
          <div className="flex max-h-[85vh] w-full max-w-[480px] flex-col gap-4 overflow-y-auto rounded-t-3xl bg-background p-6 pb-10">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-foreground">필터</h2>
              <button
                type="button"
                onClick={() => {
                  setTimeSlots(new Set());
                  setAgeRanges(new Set());
                  setTrustFilters(new Set());
                  setMaxWalkMinutes(20);
                }}
                className="border-0 bg-transparent text-xs font-medium text-primary"
              >
                초기화
              </button>
            </div>

            <p className="rounded-xl bg-secondary p-3 text-[11px] leading-relaxed text-muted-foreground">
              선택한 태그를 모두 만족하는 이웃만 보여줍니다. 후보가 너무 줄면 조건을 완화해 보세요.
            </p>

            {(
              [
                ["돌봄 시간대", TIME_SLOTS, timeSlots, setTimeSlots],
                ["아이 나이", AGE_RANGES, ageRanges, setAgeRanges],
                ["안전 · 신뢰", TRUST_FILTERS, trustFilters, setTrustFilters],
              ] as [string, string[], Set<string>, (next: Set<string>) => void][]
            ).map(([title, options, selected, apply]) => (
              <div key={title}>
                <div className="mb-2 text-xs font-semibold text-foreground">{title}</div>
                <div className="flex flex-wrap gap-2">
                  {options.map((option) => (
                    <button
                      key={option}
                      type="button"
                      onClick={() => toggle(selected, apply, option)}
                      className={
                        selected.has(option)
                          ? "rounded-full border-0 bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground"
                          : "rounded-full border border-border bg-secondary px-3 py-1.5 text-xs text-foreground"
                      }
                    >
                      {option}
                    </button>
                  ))}
                </div>
              </div>
            ))}

            <div>
              <div className="mb-2 text-xs font-semibold text-foreground">거리</div>
              <input
                type="range"
                min={5}
                max={20}
                step={1}
                value={maxWalkMinutes}
                onChange={(event) => setMaxWalkMinutes(Number(event.target.value))}
                className="w-full accent-primary"
              />
              <div className="flex justify-between text-[10px] text-muted-foreground">
                <span>도보 5분</span>
                <span className="font-semibold text-foreground">도보 {maxWalkMinutes}분 이내</span>
                <span>도보 20분</span>
              </div>
            </div>

            <p className="rounded-xl bg-secondary p-3 text-[11px] leading-relaxed text-muted-foreground">
              시간대·나이 조건은 백엔드 필터가 열리면 후보 결과에 반영됩니다. 지금은 거리와 신뢰
              등급만 실제로 적용돼요.
            </p>

            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setShowFilter(false)}
                className="flex-1 rounded-full border border-border bg-background py-3 text-sm font-medium text-foreground"
              >
                닫기
              </button>
              <button
                type="button"
                onClick={() => setShowFilter(false)}
                className="flex-[2] rounded-full border-0 bg-primary py-3 text-sm font-semibold text-primary-foreground"
              >
                {filtered?.length ?? 0}명 보기
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
