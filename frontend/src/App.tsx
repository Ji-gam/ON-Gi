import { createBrowserRouter } from "react-router-dom";

import Layout from "./components/common/Layout";
import RequireAuth from "./components/common/RequireAuth";
import CareRequestPage from "./pages/CareRequestPage/CareRequestPage";
import CareRequestsPage from "./pages/CareRequestsPage/CareRequestsPage";
import CareSessionDetailPage from "./pages/CareSessionDetailPage/CareSessionDetailPage";
import ChildrenPage from "./pages/ChildrenPage/ChildrenPage";
import GuardianProfilePage from "./pages/GuardianProfilePage/GuardianProfilePage";
import HomePage from "./pages/HomePage/HomePage";
import LoginPage from "./pages/LoginPage/LoginPage";
import MatchingPage from "./pages/MatchingPage/MatchingPage";
import ParentingValuesPage from "./pages/ParentingValuesPage/ParentingValuesPage";
import ScreenIndexPage from "./pages/ScreenIndexPage/ScreenIndexPage";
import SignupPage from "./pages/SignupPage/SignupPage";
import StartPage from "./pages/StartPage/StartPage";
import WorkSchedulePage from "./pages/WorkSchedulePage/WorkSchedulePage";

// 도메인 화면(페이지)은 src/pages 아래에 추가하고 여기에 라우트를 등록한다.
// 로그인 필요 라우트는 Layout 하위 RequireAuth로 감싼다.
export const router = createBrowserRouter([
  // 앱 진입점 — 실제 사용자용 시작 화면.
  { path: "/", element: <StartPage /> },
  // 개발 중 화면 확인용 — 실제 서비스 흐름에는 노출되지 않는다.
  { path: "/screens", element: <ScreenIndexPage /> },
  { path: "/login", element: <LoginPage /> },
  { path: "/signup", element: <SignupPage /> },
  {
    element: <Layout />,
    children: [
      { path: "/home", element: <HomePage /> },
      {
        element: <RequireAuth />,
        children: [
          { path: "/children", element: <ChildrenPage /> },
          { path: "/guardian-profile", element: <GuardianProfilePage /> },
          { path: "/parenting-values", element: <ParentingValuesPage /> },
          { path: "/work-schedule", element: <WorkSchedulePage /> },
          { path: "/matching", element: <MatchingPage /> },
          { path: "/care/requests/new", element: <CareRequestPage /> },
          { path: "/care/requests", element: <CareRequestsPage /> },
          { path: "/care/requests/:sessionId", element: <CareSessionDetailPage /> },
        ],
      },
    ],
  },
]);
