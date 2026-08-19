import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import * as authApi from "@/api/auth";
import type { Gender, TermItem } from "@/api/types";
import { useAuth } from "@/hooks/useAuth";

type NicknameStatus = "idle" | "checking" | "available" | "taken";

export default function SignupPage() {
  const { applySession } = useAuth();
  const navigate = useNavigate();

  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

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

  // 닉네임 중복확인 — onBlur마다 서버에 물어보고, 겹치면 겹친다고 안내한다.
  const [nicknameStatus, setNicknameStatus] = useState<NicknameStatus>("idle");
  const [nicknameMessage, setNicknameMessage] = useState<string | null>(null);

  // 휴대폰 본인확인 — 인증번호를 받아 직접 검증까지 완료해야 phoneVerified가 true가 된다.
  // TODO(local-test): SMS 게이트웨이 붙기 전 임시로 인증 완료 상태 + 더미 번호로 시작.
  // 실제 인증 플로우 테스트 시 phoneNumber는 ""로, phoneVerified는 false로 되돌릴 것.
  const [phoneNumber, setPhoneNumber] = useState("010-0000-0000");
  const [phoneCode, setPhoneCode] = useState("");
  const [isSendingPhoneCode, setIsSendingPhoneCode] = useState(false);
  const [isVerifyingPhone, setIsVerifyingPhone] = useState(false);
  const [phoneCodeSent, setPhoneCodeSent] = useState(false);
  const [phoneVerified, setPhoneVerified] = useState(true);
  const [phoneMessage, setPhoneMessage] = useState<string | null>(null);

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

  function handleNicknameChange(value: string) {
    setNickname(value);
    setNicknameStatus("idle");
    setNicknameMessage(null);
  }

  async function handleNicknameBlur() {
    if (!nickname) return;
    setNicknameStatus("checking");
    try {
      const res = await authApi.checkNicknameAvailability(nickname);
      setNicknameStatus(res.available ? "available" : "taken");
      setNicknameMessage(res.message);
    } catch (err) {
      setNicknameStatus("idle");
      setNicknameMessage(err instanceof Error ? err.message : "닉네임 확인에 실패했습니다.");
    }
  }

  function handlePhoneNumberChange(value: string) {
    setPhoneNumber(value);
    // 번호를 바꾸면 이전 인증 상태는 더 이상 유효하지 않다.
    if (phoneCodeSent || phoneVerified) {
      setPhoneCodeSent(false);
      setPhoneVerified(false);
      setPhoneCode("");
      setPhoneMessage(null);
    }
  }

  async function handleSendPhoneCode() {
    setPhoneMessage(null);
    setIsSendingPhoneCode(true);
    try {
      const res = await authApi.requestPhoneVerification(phoneNumber);
      setPhoneMessage(res.message);
      setPhoneCodeSent(true);
    } catch (err) {
      setPhoneMessage(err instanceof Error ? err.message : "인증번호 발송에 실패했습니다.");
    } finally {
      setIsSendingPhoneCode(false);
    }
  }

  async function handleVerifyPhoneCode() {
    setPhoneMessage(null);
    setIsVerifyingPhone(true);
    try {
      await authApi.verifyPhone({ phone_number: phoneNumber, code: phoneCode });
      setPhoneVerified(true);
      setPhoneMessage("휴대폰 본인확인이 완료되었습니다.");
    } catch (err) {
      setPhoneMessage(err instanceof Error ? err.message : "인증번호가 올바르지 않습니다.");
    } finally {
      setIsVerifyingPhone(false);
    }
  }

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
      navigate("/home");
    } catch (err) {
      setError(err instanceof Error ? err.message : "회원가입에 실패했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  }

  const canSubmit =
    requiredAgreed && !!gender && phoneVerified && nicknameStatus !== "taken" && !isSubmitting;

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-6">
        <h1 className="text-center text-base font-medium text-foreground">회원가입 · 약관 동의</h1>

        <form onSubmit={handleSignup} className="flex flex-col gap-6">
          <section className="flex flex-col gap-2.5 rounded-xl border border-border bg-secondary p-4">
            <h2 className="text-xs font-medium text-foreground">휴대폰 본인확인</h2>
            <div className="flex gap-2">
              <input
                id="phone"
                type="tel"
                placeholder="010-1234-5678"
                required
                disabled={phoneVerified}
                value={phoneNumber}
                onChange={(event) => handlePhoneNumberChange(event.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground disabled:opacity-60"
              />
              <button
                type="button"
                onClick={handleSendPhoneCode}
                disabled={!phoneNumber || isSendingPhoneCode || phoneVerified}
                className="shrink-0 rounded-lg border border-border bg-background px-3 py-2.5 text-xs font-medium text-foreground disabled:opacity-60"
              >
                {isSendingPhoneCode ? "발송 중..." : phoneCodeSent ? "다시 받기" : "인증번호 받기"}
              </button>
            </div>
            {phoneCodeSent && !phoneVerified && (
              <div className="flex gap-2">
                <input
                  id="code"
                  inputMode="numeric"
                  pattern="\d{6}"
                  placeholder="인증번호 6자리"
                  value={phoneCode}
                  onChange={(event) => setPhoneCode(event.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground"
                />
                <button
                  type="button"
                  onClick={handleVerifyPhoneCode}
                  disabled={phoneCode.length !== 6 || isVerifyingPhone}
                  className="shrink-0 rounded-lg bg-primary px-3 py-2.5 text-xs font-medium text-primary-foreground disabled:opacity-60"
                >
                  {isVerifyingPhone ? "확인 중..." : "확인"}
                </button>
              </div>
            )}
            {phoneMessage && (
              <p
                className={
                  phoneVerified ? "text-[11px] text-primary" : "text-[11px] text-foreground"
                }
              >
                {phoneVerified ? "✓ " : ""}
                {phoneMessage}
              </p>
            )}
          </section>

          <section className="flex flex-col gap-2.5 rounded-xl border border-border bg-secondary p-4">
            <h2 className="text-xs font-medium text-foreground">약관 동의</h2>
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
            <h2 className="text-xs font-medium text-foreground">가입정보</h2>
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
              <p className="mt-1 text-[11px] text-foreground">
                대문자·소문자·숫자·기호를 포함해 8자 이상 입력하세요.
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
                onChange={(event) => handleNicknameChange(event.target.value)}
                onBlur={handleNicknameBlur}
                className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground"
              />
              {nicknameStatus === "checking" && (
                <p className="mt-1 text-[11px] text-foreground">닉네임 확인 중...</p>
              )}
              {nicknameStatus === "taken" && (
                <p className="mt-1 text-[11px] text-destructive">{nicknameMessage}</p>
              )}
              {nicknameStatus === "available" && (
                <p className="mt-1 text-[11px] text-primary">{nicknameMessage}</p>
              )}
            </div>
            <div>
              <label htmlFor="birthDate" className="mb-1 block text-xs text-foreground">
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
              <label htmlFor="gender" className="mb-1 block text-xs text-foreground">
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
          {!phoneVerified && (
            <p className="-mt-3 text-center text-[11px] text-foreground">
              휴대폰 본인확인을 완료해야 가입할 수 있어요.
            </p>
          )}
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
