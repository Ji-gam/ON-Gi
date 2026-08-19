import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";

function EyeIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      width="16"
      height="16"
      aria-hidden="true"
    >
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      width="16"
      height="16"
      aria-hidden="true"
    >
      <path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-11-8-11-8a18.5 18.5 0 0 1 5.06-5.94M9.9 4.24A10.94 10.94 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  );
}

// 카카오/네이버/구글 버튼은 화면설계서 SCR-01 기준 UI만 먼저 반영 — 백엔드에 소셜 로그인
// 엔드포인트(api/auth.ts)가 없어 클릭해도 동작하지 않는다. 연동 전까지 disabled로 둔다.
const SOCIAL_PROVIDERS = [
  { name: "카카오로 시작하기", badgeBg: "bg-[#FEE500]", badgeText: "K" },
  { name: "네이버로 시작하기", badgeBg: "bg-[#03C75A]", badgeText: "N" },
  { name: "구글로 시작하기", badgeBg: "bg-white", badgeText: "G" },
];

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname ?? "/home";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "로그인에 실패했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  }

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

        <form onSubmit={handleSubmit} className="mt-14 flex w-full flex-col gap-2.5">
          <div>
            <label htmlFor="email" className="sr-only">
              이메일
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="이메일"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full rounded-lg border-0 bg-secondary px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
            />
          </div>
          <div className="flex items-center rounded-lg bg-secondary px-3 py-2.5">
            <label htmlFor="password" className="sr-only">
              비밀번호
            </label>
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              placeholder="비밀번호"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full border-0 bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
            />
            <button
              type="button"
              onClick={() => setShowPassword((prev) => !prev)}
              aria-label={showPassword ? "비밀번호 숨기기" : "비밀번호 보기"}
              className="flex shrink-0 items-center justify-center border-0 bg-transparent p-0 text-muted-foreground [appearance:none]"
            >
              {showPassword ? <EyeOffIcon /> : <EyeIcon />}
            </button>
          </div>

          {error && (
            <p className="rounded-lg bg-destructive/10 px-3 py-2.5 text-xs text-destructive">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-1.5 rounded-lg border-0 bg-primary px-3 py-3 text-sm font-medium text-primary-foreground disabled:opacity-60"
          >
            {isSubmitting ? "로그인 중..." : "로그인"}
          </button>
        </form>

        <div className="mt-4 flex w-full items-center gap-2">
          <span className="h-px flex-1 bg-border" />
          <span className="text-[11px] text-muted-foreground">또는</span>
          <span className="h-px flex-1 bg-border" />
        </div>

        <div className="mt-3.5 flex w-full flex-col gap-2">
          {SOCIAL_PROVIDERS.map((provider) => (
            <button
              key={provider.name}
              type="button"
              disabled
              className="flex items-center justify-center gap-2 rounded-lg border-0 bg-secondary px-3 py-2.5 text-sm font-medium text-black opacity-60"
            >
              <span
                className={`flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-medium text-foreground ${provider.badgeBg}`}
              >
                {provider.badgeText}
              </span>
              {provider.name}
              <span className="ml-1 text-[10px] text-muted-foreground">(준비 중)</span>
            </button>
          ))}
        </div>

        <p className="mt-5 text-xs text-foreground">
          계정이 없으신가요?{" "}
          <Link to="/signup" className="font-medium">
            회원가입
          </Link>
        </p>
      </div>
    </main>
  );
}
