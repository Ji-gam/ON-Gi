import { Link } from "react-router-dom";

// 개발 중 화면 확인용 목록 — 실제 사용자에게 노출되는 진입점이 아니다(그건 StartPage/"/").
const SCREENS = [
  { to: "/login", scr: "SCR-01", label: "로그인" },
  { to: "/signup", scr: "SCR-02", label: "회원가입" },
  { to: "/guardian-profile", scr: "SCR-03", label: "보호자 프로필" },
  { to: "/children", scr: "SCR-04·05", label: "아동 프로필 · 민감정보" },
  { to: "/parenting-values", scr: "SCR-06", label: "양육 가치관 진단" },
  { to: "/work-schedule", scr: "SCR-07", label: "근무표 등록" },
  { to: "/home", scr: "SCR-09", label: "홈 대시보드" },
  { to: "/matching", scr: "SCR-10", label: "매칭 후보 목록" },
  { to: "/care/requests", scr: "SCR-16", label: "돌봄 요청함" },
];

export default function ScreenIndexPage() {
  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-14">
      <div className="flex w-full max-w-[480px] flex-col items-center">
        <div className="flex h-[92px] w-[92px] flex-col items-center justify-center gap-[9px] rounded-lg bg-primary p-3">
          <span className="text-xl font-medium leading-none text-primary-foreground">품</span>
          <span className="h-px w-full bg-primary-foreground/75" />
          <div className="flex items-center gap-2">
            <span className="text-lg font-medium leading-none text-primary-foreground">앗</span>
            <span className="h-[18px] w-px bg-primary-foreground/75" />
            <span className="text-lg font-medium leading-none text-primary-foreground">이</span>
          </div>
        </div>

        <h1 className="mt-3.5 text-xs text-muted-foreground">지금까지 만든 화면 모음</h1>

        <div className="mt-7 flex w-full flex-col gap-2">
          {SCREENS.map((screen) => (
            <Link
              key={screen.to}
              to={screen.to}
              className="flex items-center justify-between rounded-lg border border-border bg-secondary px-4 py-3"
            >
              <span className="text-sm font-medium text-foreground">{screen.label}</span>
              <span className="text-[11px] text-muted-foreground">{screen.scr}</span>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
