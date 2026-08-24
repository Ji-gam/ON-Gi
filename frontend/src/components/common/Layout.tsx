import { NavLink, Outlet } from "react-router-dom";

function HomeIcon({ active }: { active: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={active ? 2 : 1.5}
      className="h-5 w-5"
    >
      <path d="M3 11.5 12 4l9 7.5" strokeLinecap="round" strokeLinejoin="round" />
      <path
        d="M5 10v9a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1v-9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function PeopleIcon({ active }: { active: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={active ? 2 : 1.5}
      className="h-5 w-5"
    >
      <circle cx="9" cy="8" r="3" />
      <path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6" strokeLinecap="round" />
      <circle cx="17" cy="9" r="2.4" />
      <path d="M15.5 14c2.5.3 4.5 2.4 4.5 5" strokeLinecap="round" />
    </svg>
  );
}

function HeartIcon({ active }: { active: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={active ? 2 : 1.5}
      className="h-5 w-5"
    >
      <path
        d="M12 20s-7-4.4-9.5-8.8C.8 8 2 4.5 5.4 3.7c2-.5 3.9.4 5 2 1.1-1.6 3-2.5 5-2 3.4.8 4.6 4.3 2.9 7.5C19 15.6 12 20 12 20Z"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ChatIcon({ active }: { active: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={active ? 2 : 1.5}
      className="h-5 w-5"
    >
      <path d="M4 5h16v10H9l-4 3.5V15H4V5Z" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function PersonIcon({ active }: { active: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={active ? 2 : 1.5}
      className="h-5 w-5"
    >
      <circle cx="12" cy="8" r="3.5" />
      <path d="M4.5 20c0-4.1 3.4-7 7.5-7s7.5 2.9 7.5 7" strokeLinecap="round" />
    </svg>
  );
}

const NAV_ITEMS = [
  { to: "/home", label: "홈", Icon: HomeIcon },
  { to: "/matching", label: "매칭", Icon: PeopleIcon },
  { to: "/care/requests", label: "돌봄", Icon: HeartIcon },
  { to: "/chat", label: "채팅", Icon: ChatIcon },
  { to: "/my", label: "MY", Icon: PersonIcon },
];

// 로그인 필요 라우트 공통 뼈대. 실제 인증 게이트는 RequireAuth(하위 라우트)가 맡는다 —
// 로그인 안 한 채로 매칭/돌봄/채팅/MY 탭을 누르면 자동으로 로그인 화면으로 보내진다.
export default function Layout() {
  return (
    <div className="pb-16">
      <Outlet />
      <nav className="fixed inset-x-0 bottom-0 border-t border-border bg-secondary">
        <div className="mx-auto flex max-w-[480px] justify-around py-2">
          {NAV_ITEMS.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                isActive
                  ? "flex flex-col items-center gap-0.5 px-4 py-1 text-primary"
                  : "flex flex-col items-center gap-0.5 px-4 py-1 text-muted-foreground"
              }
            >
              {({ isActive }) => (
                <>
                  <Icon active={isActive} />
                  <span className="text-[11px] font-medium">{label}</span>
                </>
              )}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
