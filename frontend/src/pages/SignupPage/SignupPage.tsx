import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import * as authApi from "@/api/auth";
import type { Gender, TermItem } from "@/api/types";
import { useAuth } from "@/hooks/useAuth";

export default function SignupPage() {
  const { applySession } = useAuth();
  const navigate = useNavigate();

  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // 휴대폰 번호 — 알림(SMS) 발송 연동 전까지는 입력만 받는다(실제 인증 API 호출 없음).
  // 인증번호는 발송 자체가 없어 입력할 값이 없으므로 필드를 비활성화해둔다.
  const [phoneNumber, setPhoneNumber] = useState("");

  // 약관 동의
  const [terms, setTerms] = useState<TermItem[]>([]);
  const [agreedTypes, setAgreedTypes] = useState<Set<string>>(new Set());

  // 가입정보
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [nickname, setNickname] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [gender, setGender] = useState<Gender | "">("");

  useEffect(() => {
    authApi
      .getTerms()
      .then((res) => setTerms(res.terms))
      .catch((err) => setError(err instanceof Error ? err.message : "약관을 불러오지 못했습니다."));
  }, []);

  function toggleAgreement(term: TermItem) {
    setAgreedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(term.terms_type)) next.delete(term.terms_type);
      else next.add(term.terms_type);
      return next;
    });
  }

  const requiredAgreed = terms
    .filter((t) => t.is_required)
    .every((t) => agreedTypes.has(t.terms_type));

  async function handleSignup(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const result = await authApi.signup({
        email,
        password,
        name,
        nickname,
        birth_date: birthDate,
        gender: gender as Gender,
        phone_number: phoneNumber,
        agreements: terms.map((t) => ({
          terms_type: t.terms_type,
          version: t.version,
          agreed: agreedTypes.has(t.terms_type),
        })),
      });
      applySession(result);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "회원가입에 실패했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  }

  const canSubmit = requiredAgreed && !!gender && !isSubmitting;

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-6">
        <h1 className="text-center text-base font-medium text-foreground">회원가입 · 약관 동의</h1>

        <form onSubmit={handleSignup} className="flex flex-col gap-6">
          <section className="flex flex-col gap-2.5 rounded-xl border border-border bg-secondary p-4">
            <h2 className="text-xs font-medium text-muted-foreground">휴대폰 본인확인</h2>
            <p className="text-[11px] text-muted-foreground">
              알림(SMS) 인증 연동 전까지는 입력만 받습니다.
            </p>
            <div>
              <label htmlFor="phone" className="sr-only">
                휴대폰 번호
              </label>
              <input
                id="phone"
                type="tel"
                placeholder="010-1234-5678"
                required
                value={phoneNumber}
                onChange={(event) => setPhoneNumber(event.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground"
              />
            </div>
            <div>
              <label htmlFor="code" className="sr-only">
                인증번호
              </label>
              <input
                id="code"
                inputMode="numeric"
                pattern="\d{6}"
                disabled
                placeholder="인증번호 (연동 전)"
                className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-muted-foreground placeholder:text-muted-foreground disabled:opacity-60"
              />
            </div>
          </section>

          <section className="flex flex-col gap-2.5 rounded-xl border border-border bg-secondary p-4">
            <h2 className="text-xs font-medium text-muted-foreground">약관 동의</h2>
            {terms.map((term) => (
              <label
                key={term.terms_type}
                className="flex items-center gap-2 text-xs text-foreground"
              >
                <input
                  type="checkbox"
                  checked={agreedTypes.has(term.terms_type)}
                  onChange={() => toggleAgreement(term)}
                  className="h-4 w-4 accent-primary"
                />
                {term.is_required ? "[필수] " : "[선택] "}
                {term.title}
              </label>
            ))}
          </section>

          <section className="flex flex-col gap-2.5 rounded-xl border border-border bg-secondary p-4">
            <h2 className="text-xs font-medium text-muted-foreground">가입정보</h2>
            <div>
              <label htmlFor="email" className="sr-only">
                이메일
              </label>
              <input
                id="email"
                type="email"
                placeholder="이메일"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground"
              />
            </div>
            <div>
              <label htmlFor="password" className="sr-only">
                비밀번호
              </label>
              <input
                id="password"
                type="password"
                placeholder="비밀번호"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground"
              />
              <p className="mt-1 text-[11px] text-muted-foreground">
                대문자·소문자·숫자·기호를 포함해 입력하세요.
              </p>
            </div>
            <div>
              <label htmlFor="name" className="sr-only">
                이름
              </label>
              <input
                id="name"
                placeholder="이름"
                required
                value={name}
                onChange={(event) => setName(event.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground"
              />
            </div>
            <div>
              <label htmlFor="nickname" className="sr-only">
                닉네임
              </label>
              <input
                id="nickname"
                placeholder="닉네임"
                required
                value={nickname}
                onChange={(event) => setNickname(event.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground"
              />
            </div>
            <div>
              <label htmlFor="birthDate" className="mb-1 block text-xs text-muted-foreground">
                생년월일
              </label>
              <input
                id="birthDate"
                type="date"
                required
                value={birthDate}
                onChange={(event) => setBirthDate(event.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground"
              />
            </div>
            <div>
              <label htmlFor="gender" className="mb-1 block text-xs text-muted-foreground">
                성별
              </label>
              <select
                id="gender"
                required
                value={gender}
                onChange={(event: ChangeEvent<HTMLSelectElement>) =>
                  setGender(event.target.value as Gender)
                }
                className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground"
              >
                <option value="" disabled>
                  선택
                </option>
                <option value="M">남성</option>
                <option value="F">여성</option>
              </select>
            </div>
          </section>

          {error && (
            <p className="rounded-lg bg-destructive/10 px-3 py-2.5 text-xs text-destructive">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={!canSubmit}
            className="rounded-lg bg-primary px-3 py-3 text-sm font-medium text-primary-foreground disabled:opacity-60"
          >
            {isSubmitting ? "가입 중..." : "가입하기"}
          </button>
        </form>

        <p className="text-center text-xs text-foreground">
          이미 계정이 있으신가요?{" "}
          <Link to="/login" className="font-medium">
            로그인
          </Link>
        </p>
      </div>
    </main>
  );
}
