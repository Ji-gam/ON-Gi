import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import * as authApi from "@/api/auth";
import { ApiError } from "@/api/client";
import type { Gender, TermItem } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/hooks/useAuth";

type Step = "phone" | "terms" | "profile";

export default function SignupPage() {
  const { applySession } = useAuth();
  const navigate = useNavigate();

  const [step, setStep] = useState<Step>("phone");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // 1단계: 휴대폰 본인확인
  const [phoneNumber, setPhoneNumber] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [code, setCode] = useState("");

  // 2단계: 약관 동의
  const [terms, setTerms] = useState<TermItem[]>([]);
  const [agreedTypes, setAgreedTypes] = useState<Set<string>>(new Set());

  // 3단계: 가입정보
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [nickname, setNickname] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [gender, setGender] = useState<Gender | "">("");

  useEffect(() => {
    if (step !== "terms" || terms.length > 0) return;
    authApi
      .getTerms()
      .then((res) => setTerms(res.terms))
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "약관을 불러오지 못했습니다."),
      );
  }, [step, terms.length]);

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

  async function handleSendCode(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await authApi.requestPhoneVerification(phoneNumber);
      setCodeSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "인증 코드 발송에 실패했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleVerifyCode(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await authApi.verifyPhone({ phone_number: phoneNumber, code });
      setStep("terms");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "인증에 실패했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleTermsNext() {
    setError(null);
    setStep("profile");
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
      navigate("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "회원가입에 실패했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 px-4 py-10">
      <h1 className="text-2xl font-bold">ON-Gi 회원가입</h1>
      <p className="text-sm text-muted-foreground">
        {step === "phone" && "1/3 · 휴대폰 본인확인"}
        {step === "terms" && "2/3 · 약관 동의"}
        {step === "profile" && "3/3 · 가입정보 입력"}
      </p>

      {step === "phone" && (
        <form
          onSubmit={codeSent ? handleVerifyCode : handleSendCode}
          className="flex w-full max-w-sm flex-col gap-4"
        >
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="phone">휴대폰 번호</Label>
            <Input
              id="phone"
              type="tel"
              placeholder="010-1234-5678"
              required
              disabled={codeSent}
              value={phoneNumber}
              onChange={(event) => setPhoneNumber(event.target.value)}
            />
          </div>
          {codeSent && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="code">인증번호</Label>
              <Input
                id="code"
                inputMode="numeric"
                pattern="\d{6}"
                required
                value={code}
                onChange={(event) => setCode(event.target.value)}
              />
            </div>
          )}
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" disabled={isSubmitting}>
            {codeSent ? "인증 확인" : "인증번호 받기"}
          </Button>
        </form>
      )}

      {step === "terms" && (
        <div className="flex w-full max-w-sm flex-col gap-4">
          {terms.map((term) => (
            <label key={term.terms_type} className="flex items-start gap-2 text-sm">
              <Checkbox
                checked={agreedTypes.has(term.terms_type)}
                onCheckedChange={() => toggleAgreement(term)}
              />
              <span>
                {term.is_required ? "[필수] " : "[선택] "}
                {term.title}
              </span>
            </label>
          ))}
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="button" disabled={!requiredAgreed} onClick={handleTermsNext}>
            다음
          </Button>
        </div>
      )}

      {step === "profile" && (
        <form onSubmit={handleSignup} className="flex w-full max-w-sm flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="email">이메일</Label>
            <Input
              id="email"
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="password">비밀번호</Label>
            <Input
              id="password"
              type="password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="name">이름</Label>
            <Input
              id="name"
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="nickname">닉네임</Label>
            <Input
              id="nickname"
              required
              value={nickname}
              onChange={(event) => setNickname(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="birthDate">생년월일</Label>
            <Input
              id="birthDate"
              type="date"
              required
              value={birthDate}
              onChange={(event) => setBirthDate(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="gender">성별</Label>
            <Select value={gender} onValueChange={(value) => setGender(value as Gender)}>
              <SelectTrigger id="gender">
                <SelectValue placeholder="선택" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="M">남성</SelectItem>
                <SelectItem value="F">여성</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" disabled={isSubmitting || !gender}>
            {isSubmitting ? "가입 중..." : "가입 완료"}
          </Button>
        </form>
      )}
    </main>
  );
}
