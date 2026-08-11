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
    <main>
      <h1>ON-Gi 회원가입</h1>
      <form onSubmit={handleSignup}>
        <fieldset>
          <legend>휴대폰 본인확인</legend>
          <p>알림(SMS) 인증 연동 전까지는 입력만 받습니다.</p>
          <div>
            <label htmlFor="phone">휴대폰 번호</label>
            <input
              id="phone"
              type="tel"
              placeholder="010-1234-5678"
              required
              value={phoneNumber}
              onChange={(event) => setPhoneNumber(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor="code">인증번호</label>
            <input id="code" inputMode="numeric" pattern="\d{6}" disabled />
          </div>
        </fieldset>

        <fieldset>
          <legend>약관 동의</legend>
          {terms.map((term) => (
            <div key={term.terms_type}>
              <label>
                <input
                  type="checkbox"
                  checked={agreedTypes.has(term.terms_type)}
                  onChange={() => toggleAgreement(term)}
                />
                {term.is_required ? "[필수] " : "[선택] "}
                {term.title}
              </label>
            </div>
          ))}
        </fieldset>

        <fieldset>
          <legend>가입정보</legend>
          <div>
            <label htmlFor="email">이메일</label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor="password">비밀번호</label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor="name">이름</label>
            <input
              id="name"
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor="nickname">닉네임</label>
            <input
              id="nickname"
              required
              value={nickname}
              onChange={(event) => setNickname(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor="birthDate">생년월일</label>
            <input
              id="birthDate"
              type="date"
              required
              value={birthDate}
              onChange={(event) => setBirthDate(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor="gender">성별</label>
            <select
              id="gender"
              required
              value={gender}
              onChange={(event: ChangeEvent<HTMLSelectElement>) =>
                setGender(event.target.value as Gender)
              }
            >
              <option value="" disabled>
                선택
              </option>
              <option value="M">남성</option>
              <option value="F">여성</option>
            </select>
          </div>
        </fieldset>

        {error && <p>{error}</p>}
        <button type="submit" disabled={!canSubmit}>
          {isSubmitting ? "가입 중..." : "가입하기"}
        </button>
      </form>
      <p>
        이미 계정이 있으신가요? <Link to="/login">로그인</Link>
      </p>
    </main>
  );
}
