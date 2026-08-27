import { createBrowserRouter } from "react-router-dom";

import Layout from "./components/common/Layout";
import RequireAuth from "./components/common/RequireAuth";
import CareDonePage from "./pages/CareDonePage/CareDonePage";
import CareJournalPage from "./pages/CareJournalPage/CareJournalPage";
import CareRequestPage from "./pages/CareRequestPage/CareRequestPage";
import CareRequestsPage from "./pages/CareRequestsPage/CareRequestsPage";
import CareReviewPage from "./pages/CareReviewPage/CareReviewPage";
import CareSessionDetailPage from "./pages/CareSessionDetailPage/CareSessionDetailPage";
import ChatListPage from "./pages/ChatListPage/ChatListPage";
import ChatThreadPage from "./pages/ChatThreadPage/ChatThreadPage";
import ChildrenPage from "./pages/ChildrenPage/ChildrenPage";
import GuardianProfilePage from "./pages/GuardianProfilePage/GuardianProfilePage";
import HomePage from "./pages/HomePage/HomePage";
import JointSessionCreatePage from "./pages/JointSessionCreatePage/JointSessionCreatePage";
import LoginPage from "./pages/LoginPage/LoginPage";
import MatchingDetailPage from "./pages/MatchingDetailPage/MatchingDetailPage";
import MatchingPage from "./pages/MatchingPage/MatchingPage";
import MyPage from "./pages/MyPage/MyPage";
import NotificationsPage from "./pages/NotificationsPage/NotificationsPage";
import ParentingValuesPage from "./pages/ParentingValuesPage/ParentingValuesPage";
import ScreenIndexPage from "./pages/ScreenIndexPage/ScreenIndexPage";
import SignupPage from "./pages/SignupPage/SignupPage";
import StartPage from "./pages/StartPage/StartPage";
import TrustRelationPage from "./pages/TrustRelationPage/TrustRelationPage";
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
          { path: "/matching/:userId", element: <MatchingDetailPage /> },
          { path: "/notifications", element: <NotificationsPage /> },
          { path: "/care/requests/new", element: <CareRequestPage /> },
          { path: "/care/requests", element: <CareRequestsPage /> },
          { path: "/care/requests/:sessionId", element: <CareSessionDetailPage /> },
          { path: "/care/requests/:sessionId/journal", element: <CareJournalPage /> },
          { path: "/care/requests/:sessionId/review", element: <CareReviewPage /> },
          { path: "/care/requests/:sessionId/done", element: <CareDonePage /> },
          { path: "/trust/:partnerId", element: <TrustRelationPage /> },
          { path: "/trust/:partnerId/joint-sessions/new", element: <JointSessionCreatePage /> },
          { path: "/chat", element: <ChatListPage /> },
          { path: "/chat/:partnerId", element: <ChatThreadPage /> },
          { path: "/my", element: <MyPage /> },
        ],
      },
    ],
  },
]);
