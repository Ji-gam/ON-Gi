import { createBrowserRouter } from "react-router-dom";

import Layout from "./components/common/Layout";
import RequireAuth from "./components/common/RequireAuth";
import ChildrenPage from "./pages/ChildrenPage/ChildrenPage";
import EmailVerifyPage from "./pages/EmailVerifyPage/EmailVerifyPage";
import GuardianProfilePage from "./pages/GuardianProfilePage/GuardianProfilePage";
import HomePage from "./pages/HomePage/HomePage";
import LoginPage from "./pages/LoginPage/LoginPage";
import MatchingPage from "./pages/MatchingPage/MatchingPage";
import ParentingValuesPage from "./pages/ParentingValuesPage/ParentingValuesPage";
import SignupPage from "./pages/SignupPage/SignupPage";
import WorkSchedulePage from "./pages/WorkSchedulePage/WorkSchedulePage";

// 도메인 화면(페이지)은 src/pages 아래에 추가하고 여기에 라우트를 등록한다.
// 로그인 필요 라우트는 Layout 하위 RequireAuth로 감싼다.
export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/signup", element: <SignupPage /> },
  { path: "/auth/email/verify", element: <EmailVerifyPage /> },
  {
    element: <Layout />,
    children: [
      { path: "/", element: <HomePage /> },
      {
        element: <RequireAuth />,
        children: [
          { path: "/children", element: <ChildrenPage /> },
          { path: "/guardian-profile", element: <GuardianProfilePage /> },
          { path: "/parenting-values", element: <ParentingValuesPage /> },
          { path: "/work-schedule", element: <WorkSchedulePage /> },
          { path: "/matching", element: <MatchingPage /> },
        ],
      },
    ],
  },
]);
