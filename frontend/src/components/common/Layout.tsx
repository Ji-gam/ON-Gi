import { NavLink, Outlet } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/home", label: "홈" },
  { to: "/children", label: "아동 관리" },
  { to: "/guardian-profile", label: "보호자 프로필" },
  { to: "/parenting-values", label: "양육 가치관 진단" },
  { to: "/work-schedule", label: "근무표" },
  { to: "/matching", label: "매칭 후보" },
  { to: "/care/requests", label: "돌봄 요청함" },
  { to: "/login", label: "로그인" },
  { to: "/signup", label: "회원가입" },
];

// 로그인 필요 라우트 공통 뼈대 — 실제 인증 게이트(RequireAuth)는 T-ACC-1 프론트 연동 시 추가.
export default function Layout() {
  return (
    <div>
      <nav>
        {NAV_ITEMS.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.to === "/"}>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  );
}
