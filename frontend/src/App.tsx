import { createBrowserRouter } from "react-router-dom";

import Layout from "./components/common/Layout";
import ChildrenPage from "./pages/ChildrenPage/ChildrenPage";
import GuardianProfilePage from "./pages/GuardianProfilePage/GuardianProfilePage";
import HomePage from "./pages/HomePage/HomePage";
import LoginPage from "./pages/LoginPage/LoginPage";
import MatchingPage from "./pages/MatchingPage/MatchingPage";
import ParentingValuesPage from "./pages/ParentingValuesPage/ParentingValuesPage";
import SignupPage from "./pages/SignupPage/SignupPage";
import WorkSchedulePage from "./pages/WorkSchedulePage/WorkSchedulePage";

// 도메인 화면(페이지)은 src/pages 아래에 추가하고 여기에 라우트를 등록한다.
// 로그인 필요 라우트는 Layout 하위에 배치, RequireAuth 게이트는 T-ACC-1 프론트 연동 시 추가.
export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/signup", element: <SignupPage /> },
  {
    element: <Layout />,
    children: [
      { path: "/", element: <HomePage /> },
      { path: "/children", element: <ChildrenPage /> },
      { path: "/guardian-profile", element: <GuardianProfilePage /> },
      { path: "/parenting-values", element: <ParentingValuesPage /> },
      { path: "/work-schedule", element: <WorkSchedulePage /> },
      { path: "/matching", element: <MatchingPage /> },
    ],
  },
]);
