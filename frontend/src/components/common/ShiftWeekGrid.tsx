// 목업의 요일 비교 그리드(나 / 상대).
// 근무표는 날짜별 48슬롯 비트마스크로 저장돼 있어, 요일별 상태는 프론트에서 환산한다.
export type DayState = "work" | "available" | "off";

const DAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"];

const STATE_CLASS: Record<DayState, string> = {
  work: "bg-primary",
  available: "bg-[hsl(45_93%_62%)]",
  off: "bg-border",
};

export default function ShiftWeekGrid({ rows }: { rows: { label: string; days: DayState[] }[] }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex gap-1 pl-8">
        {DAY_LABELS.map((day) => (
          <span key={day} className="flex-1 text-center text-[10px] text-muted-foreground">
            {day}
          </span>
        ))}
      </div>
      {rows.map((row) => (
        <div key={row.label} className="flex items-center gap-1">
          <span className="w-8 shrink-0 text-[10px] text-muted-foreground">{row.label}</span>
          {row.days.map((state, index) => (
            <span
              key={index}
              className={`h-6 flex-1 rounded-md ${STATE_CLASS[state]}`}
              title={`${DAY_LABELS[index]} · ${state}`}
            />
          ))}
        </div>
      ))}
      <div className="flex gap-3 pl-8 pt-1">
        {(
          [
            ["work", "근무"],
            ["available", "돌봄 가능"],
            ["off", "휴무"],
          ] as [DayState, string][]
        ).map(([state, label]) => (
          <span key={state} className="flex items-center gap-1 text-[10px] text-muted-foreground">
            <span className={`h-2 w-2 rounded-sm ${STATE_CLASS[state]}`} />
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}
