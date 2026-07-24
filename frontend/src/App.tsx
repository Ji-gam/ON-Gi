import { createBrowserRouter } from "react-router-dom";

import HomePage from "./pages/HomePage";

// 도메인 화면(페이지)은 src/pages 아래에 추가하고 여기에 라우트를 등록한다.
export const router = createBrowserRouter([{ path: "/", element: <HomePage /> }]);
