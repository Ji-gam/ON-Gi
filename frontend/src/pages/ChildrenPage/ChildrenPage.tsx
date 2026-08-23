import { useEffect, useState, type FormEvent } from "react";

import * as authApi from "@/api/auth";
import * as childrenApi from "@/api/children";
import type { ChildGender, ChildResponse } from "@/api/childrenTypes";
import type { TermItem } from "@/api/types";
import { useAuth } from "@/hooks/useAuth";

const GUARDIAN_CONSENT_TYPE = "guardian_consent";

export default function ChildrenPage() {
  const { accessToken } = useAuth();
  const [children, setChildren] = useState<ChildResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [monthsOld, setMonthsOld] = useState("");
  const [gender, setGender] = useState<ChildGender | "">("");
  const [temperamentMemo, setTemperamentMemo] = useState("");
  const [allergies, setAllergies] = useState("");
  const [conditions, setConditions] = useState("");
  const [medications, setMedications] = useState("");

  // 법정대리인 동의(REQ-F-ACC-03) — 아동 등록 폼은 이 동의가 없으면 잠긴다.
  const [guardianTerm, setGuardianTerm] = useState<TermItem | null>(null);
  const [guardianConsentAgreed, setGuardianConsentAgreed] = useState(false);
  const [isSubmittingConsent, setIsSubmittingConsent] = useState(false);
  const [consentError, setConsentError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken) return;
    childrenApi
      .listChildren(accessToken)
      .then(setChildren)
      .catch((err) => setError(err instanceof Error ? err.message : "목록을 불러오지 못했습니다."));

    authApi
      .getTerms()
      .then((res) =>
        setGuardianTerm(res.terms.find((t) => t.terms_type === GUARDIAN_CONSENT_TYPE) ?? null),
      );

    authApi
      .getMyAgreements(accessToken)
      .then((res) => {
        const agreement = res.agreements.find((a) => a.terms_type === GUARDIAN_CONSENT_TYPE);
        if (agreement?.agreed && !agreement.needs_reagreement) setGuardianConsentAgreed(true);
      })
      .catch(() => {});
  }, [accessToken]);

  async function handleGuardianConsentChange(checked: boolean) {
    if (!checked) {
      setGuardianConsentAgreed(false);
      return;
    }
    if (!accessToken || !guardianTerm) return;
    setConsentError(null);
    setIsSubmittingConsent(true);
    try {
      await authApi.submitAgreements(
        [{ terms_type: guardianTerm.terms_type, version: guardianTerm.version, agreed: true }],
        accessToken,
      );
      setGuardianConsentAgreed(true);
    } catch (err) {
      setConsentError(err instanceof Error ? err.message : "동의 처리에 실패했습니다.");
    } finally {
      setIsSubmittingConsent(false);
    }
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    if (!accessToken) return;
    setError(null);
    setIsSubmitting(true);
    try {
      await childrenApi.createChild(
        {
          months_old: Number(monthsOld),
          gender: gender as ChildGender,
          temperament_memo: temperamentMemo || null,
          allergies: allergies || null,
          conditions: conditions || null,
          medications: medications || null,
        },
        accessToken,
      );
      const updated = await childrenApi.listChildren(accessToken);
      setChildren(updated);
      setMonthsOld("");
      setGender("");
      setTemperamentMemo("");
      setAllergies("");
      setConditions("");
      setMedications("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "아동 등록에 실패했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDelete(childId: number) {
    if (!accessToken) return;
    setError(null);
    try {
      await childrenApi.deleteChild(childId, accessToken);
      setChildren((prev) => prev?.filter((c) => c.id !== childId) ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "삭제에 실패했습니다.");
    }
  }

  if (!accessToken) return null;

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-6">
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-secondary px-2 py-1 text-[11px] font-medium text-primary">
            2/5
          </span>
          <h1 className="text-sm font-medium text-foreground">아동 프로필 · 민감정보</h1>
        </div>

        <section className="flex flex-col gap-2.5">
          <h2 className="text-xs font-medium text-muted-foreground">등록된 아동</h2>
          {children === null && !error && (
            <p className="text-xs text-muted-foreground">불러오는 중...</p>
          )}
          {children && children.length === 0 && (
            <p className="text-xs text-muted-foreground">등록된 아동이 없습니다.</p>
          )}
          {children && children.length > 0 && (
            <ul className="flex flex-col gap-2">
              {children.map((child) => (
                <li
                  key={child.id}
                  className="flex items-center justify-between rounded-xl border border-border bg-secondary px-4 py-3"
                >
                  <span className="text-xs text-foreground">
                    {child.months_old}개월 · {child.gender === "M" ? "남아" : "여아"}
                    {child.temperament_memo ? ` · ${child.temperament_memo}` : ""}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleDelete(child.id)}
                    className="text-xs text-muted-foreground"
                  >
                    삭제
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="flex flex-col gap-2.5 rounded-xl border border-border bg-secondary p-4">
          <div className="mb-1 flex gap-2 rounded-lg bg-background p-3">
            <span className="text-xs text-foreground">
              만 14세 미만 아동의 정보는 법정대리인 동의 하에 처리됩니다(개인정보 보호법 제22조의2).
              이 정보는 암호화되어 저장되며, 대응 가능한 이웃만 후보로 보여드립니다.
            </span>
          </div>

          <label className="flex items-start gap-2 rounded-lg bg-background p-3 text-xs text-foreground">
            <input
              type="checkbox"
              checked={guardianConsentAgreed}
              disabled={isSubmittingConsent || !guardianTerm}
              onChange={(event) => handleGuardianConsentChange(event.target.checked)}
              className="mt-0.5 h-3.5 w-3.5 accent-primary"
            />
            <span>
              본인은 아동의 법정대리인입니다 <span className="text-destructive">*</span>
            </span>
          </label>
          {consentError && (
            <p className="rounded-lg bg-destructive/10 px-3 py-2.5 text-xs text-destructive">
              {consentError}
            </p>
          )}

          <form onSubmit={handleCreate} className="flex flex-col gap-2.5">
            <fieldset
              disabled={!guardianConsentAgreed}
              className="flex flex-col gap-2.5 disabled:opacity-60"
            >
              <div>
                <label htmlFor="monthsOld" className="mb-1 block text-xs text-muted-foreground">
                  개월 수 <span className="text-destructive">*</span>
                </label>
                <input
                  id="monthsOld"
                  type="number"
                  min={0}
                  max={216}
                  required
                  value={monthsOld}
                  onChange={(event) => setMonthsOld(event.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground"
                />
              </div>
              <div>
                <label htmlFor="childGender" className="mb-1 block text-xs text-muted-foreground">
                  성별 <span className="text-destructive">*</span>
                </label>
                <select
                  id="childGender"
                  required
                  value={gender}
                  onChange={(event) => setGender(event.target.value as ChildGender)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground"
                >
                  <option value="" disabled>
                    선택
                  </option>
                  <option value="M">남아</option>
                  <option value="F">여아</option>
                </select>
              </div>
              <div>
                <label
                  htmlFor="temperamentMemo"
                  className="mb-1 block text-xs text-muted-foreground"
                >
                  기질 메모 (선택)
                </label>
                <input
                  id="temperamentMemo"
                  placeholder="예: 낯가림이 있어요"
                  value={temperamentMemo}
                  onChange={(event) => setTemperamentMemo(event.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground"
                />
              </div>
              <div>
                <label htmlFor="allergies" className="mb-1 block text-xs text-muted-foreground">
                  알레르기 (선택)
                </label>
                <input
                  id="allergies"
                  placeholder="예: 견과류, 계란"
                  value={allergies}
                  onChange={(event) => setAllergies(event.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground"
                />
              </div>
              <div>
                <label htmlFor="conditions" className="mb-1 block text-xs text-muted-foreground">
                  지병 (알레르기 외, 선택)
                </label>
                <input
                  id="conditions"
                  placeholder="예: 아토피"
                  value={conditions}
                  onChange={(event) => setConditions(event.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground"
                />
              </div>
              <div>
                <label htmlFor="medications" className="mb-1 block text-xs text-muted-foreground">
                  상시 투약 (선택)
                </label>
                <input
                  id="medications"
                  placeholder="약명·시간·주의사항"
                  value={medications}
                  onChange={(event) => setMedications(event.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground"
                />
              </div>
              {error && (
                <p className="rounded-lg bg-destructive/10 px-3 py-2.5 text-xs text-destructive">
                  {error}
                </p>
              )}
              <button
                type="submit"
                disabled={isSubmitting || !gender}
                className="rounded-lg bg-primary px-3 py-3 text-sm font-medium text-primary-foreground disabled:opacity-60"
              >
                {isSubmitting ? "등록 중..." : "아동 등록"}
              </button>
            </fieldset>
          </form>
        </section>
      </div>
    </main>
  );
}
