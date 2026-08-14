import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import * as authApi from "@/api/auth";

type Status = "verifying" | "success" | "error";

export default function EmailVerifyPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState<Status>("verifying");
  const [message, setMessage] = useState("이메일을 인증하는 중이에요...");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("인증 링크가 올바르지 않아요. 메일에 있는 링크를 다시 눌러주세요.");
      return;
    }
    authApi
      .verifyEmail(token)
      .then((result) => {
        setStatus("success");
        setMessage(result.detail);
      })
      .catch((err) => {
        setStatus("error");
        setMessage(err instanceof Error ? err.message : "이메일 인증에 실패했습니다.");
      });
  }, [token]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6">
      <div className="flex w-full max-w-[420px] flex-col items-center gap-4 text-center">
        <h1 className="text-base font-medium text-foreground">이메일 인증</h1>
        <p
          className={
            status === "error"
              ? "rounded-lg bg-destructive/10 px-4 py-3 text-sm text-destructive"
              : "rounded-lg bg-secondary px-4 py-3 text-sm text-foreground"
          }
        >
          {message}
        </p>
        {status === "success" && (
          <p className="text-xs text-muted-foreground">
            이제 가입 화면으로 돌아가 나머지 정보를 입력하고 가입을 완료해주세요.
          </p>
        )}
        <Link to="/signup" className="text-xs font-medium text-primary">
          회원가입 화면으로 돌아가기
        </Link>
      </div>
    </main>
  );
}
