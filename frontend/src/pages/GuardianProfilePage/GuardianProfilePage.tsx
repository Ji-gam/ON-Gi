import { useEffect, useState, type FormEvent } from "react";

import { ApiError } from "@/api/client";
import * as guardianProfileApi from "@/api/guardianProfile";
import {
  GUARDIAN_TAG_CODES,
  type HouseholdComposition,
  type JobCategory,
  type WorkType,
} from "@/api/guardianProfileTypes";
import { useAuth } from "@/hooks/useAuth";

const JOB_CATEGORIES: JobCategory[] = [
  "OFFICE_WORKER",
  "SERVICE",
  "SELF_EMPLOYED",
  "HEALTHCARE",
  "EDUCATION",
  "IT",
  "PUBLIC_SERVANT",
  "HOMEMAKER",
  "FREELANCER",
  "OTHER",
];

const JOB_CATEGORY_LABELS: Record<JobCategory, string> = {
  OFFICE_WORKER: "사무직",
  SERVICE: "서비스직",
  SELF_EMPLOYED: "자영업",
  HEALTHCARE: "의료·보건",
  EDUCATION: "교육",
  IT: "IT",
  PUBLIC_SERVANT: "공무원",
  HOMEMAKER: "전업주부",
  FREELANCER: "프리랜서",
  OTHER: "기타",
};

const WORK_TYPES: WorkType[] = [
  "FULL_TIME",
  "SHIFT",
  "FLEXIBLE",
  "REMOTE",
  "FREELANCE",
  "UNEMPLOYED",
  "OTHER",
];

const WORK_TYPE_LABELS: Record<WorkType, string> = {
  FULL_TIME: "상근직",
  SHIFT: "교대근무",
  FLEXIBLE: "유연근무",
  REMOTE: "재택근무",
  FREELANCE: "프리랜스",
  UNEMPLOYED: "무직",
  OTHER: "기타",
};

const HOUSEHOLD_COMPOSITIONS: HouseholdComposition[] = [
  "TWO_PARENT",
  "SINGLE_PARENT",
  "EXTENDED_FAMILY",
  "OTHER",
];

const HOUSEHOLD_COMPOSITION_LABELS: Record<HouseholdComposition, string> = {
  TWO_PARENT: "양부모 가정",
  SINGLE_PARENT: "한부모 가정",
  EXTENDED_FAMILY: "대가족",
  OTHER: "기타",
};

const GUARDIAN_TAG_LABELS: Record<string, string> = {
  ALLERGY_RESPONSE: "알레르기 대응 가능",
  MEDICATION_MANAGEMENT: "투약 관리 가능",
  FIRST_AID_CERTIFIED: "응급처치 이수",
  NON_SMOKING_HOUSEHOLD: "비흡연 가정",
  HAS_VEHICLE: "차량 보유",
};

function ChipButton({
  label,
  selected,
  onClick,
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        selected
          ? "rounded-full bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground"
          : "rounded-full border border-border bg-secondary px-3 py-1.5 text-xs text-foreground"
      }
    >
      {label}
    </button>
  );
}

export default function GuardianProfilePage() {
  const { accessToken } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  const [residenceH3, setResidenceH3] = useState("");
  const [jobCategory, setJobCategory] = useState<JobCategory | "">("");
  const [workType, setWorkType] = useState<WorkType | "">("");
  const [householdComposition, setHouseholdComposition] = useState<HouseholdComposition | "">("");
  const [tags, setTags] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!accessToken) return;
    guardianProfileApi
      .getGuardianProfile(accessToken)
      .then((profile) => {
        setResidenceH3(profile.residence_h3);
        setJobCategory(profile.job_category);
        setWorkType(profile.work_type);
        setHouseholdComposition(profile.household_composition);
        setTags(new Set(profile.tags));
      })
      .catch((err) => {
        // 404 = 아직 등록 전 — 정상 상태, 빈 폼으로 둔다.
        if (err instanceof ApiError && err.status !== 404) {
          setError(err.message);
        }
      })
      .finally(() => setIsLoading(false));
  }, [accessToken]);

  function toggleTag(tag: string) {
    setTags((prev) => {
      const next = new Set(prev);
      if (next.has(tag)) next.delete(tag);
      else next.add(tag);
      return next;
    });
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!accessToken) return;
    setError(null);
    setSavedMessage(null);
    setIsSubmitting(true);
    try {
      await guardianProfileApi.upsertGuardianProfile(
        {
          residence_h3: residenceH3,
          job_category: jobCategory as JobCategory,
          work_type: workType as WorkType,
          household_composition: householdComposition as HouseholdComposition,
          tags: Array.from(tags),
        },
        accessToken,
      );
      setSavedMessage("저장되었습니다.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "저장에 실패했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!accessToken) return null;

  if (isLoading) {
    return (
      <main className="flex min-h-screen justify-center bg-background px-6 py-10">
        <p className="text-sm text-muted-foreground">불러오는 중...</p>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen justify-center bg-background px-6 py-10">
      <div className="flex w-full max-w-[480px] flex-col gap-6">
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-secondary px-2 py-1 text-[11px] font-medium text-primary">
            1/5
          </span>
          <h1 className="text-sm font-medium text-foreground">보호자 프로필</h1>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-6">
          <div>
            <label htmlFor="residenceH3" className="mb-1 block text-xs font-medium text-foreground">
              거주지 (H3 인덱스) <span className="text-destructive">*</span>
            </label>
            <p className="mb-2 text-[11px] text-muted-foreground">
              매칭 거리 계산에 쓰이며, 화면에는 동 단위까지만 표시돼요.
            </p>
            <input
              id="residenceH3"
              required
              value={residenceH3}
              onChange={(event) => setResidenceH3(event.target.value)}
              className="w-full rounded-lg border border-border bg-secondary px-3 py-2.5 text-sm text-foreground"
            />
          </div>

          <div>
            <div className="mb-2 text-xs font-medium text-foreground">근무 형태</div>
            <div className="flex flex-wrap gap-2">
              {WORK_TYPES.map((value) => (
                <ChipButton
                  key={value}
                  label={WORK_TYPE_LABELS[value]}
                  selected={workType === value}
                  onClick={() => setWorkType(value)}
                />
              ))}
            </div>
          </div>

          <div>
            <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-foreground">
              <span className="text-muted-foreground">└</span>직군
            </div>
            <div className="flex flex-wrap gap-2">
              {JOB_CATEGORIES.map((value) => (
                <ChipButton
                  key={value}
                  label={JOB_CATEGORY_LABELS[value]}
                  selected={jobCategory === value}
                  onClick={() => setJobCategory(value)}
                />
              ))}
            </div>
          </div>

          <div>
            <div className="mb-2 text-xs font-medium text-foreground">가구 구성</div>
            <div className="flex flex-wrap gap-2">
              {HOUSEHOLD_COMPOSITIONS.map((value) => (
                <ChipButton
                  key={value}
                  label={HOUSEHOLD_COMPOSITION_LABELS[value]}
                  selected={householdComposition === value}
                  onClick={() => setHouseholdComposition(value)}
                />
              ))}
            </div>
          </div>

          <div>
            <div className="mb-2 text-xs font-medium text-foreground">보유 태그</div>
            <div className="flex flex-wrap gap-2">
              {GUARDIAN_TAG_CODES.map((tag) => (
                <ChipButton
                  key={tag}
                  label={GUARDIAN_TAG_LABELS[tag] ?? tag}
                  selected={tags.has(tag)}
                  onClick={() => toggleTag(tag)}
                />
              ))}
            </div>
          </div>

          {error && (
            <p className="rounded-lg bg-destructive/10 px-3 py-2.5 text-xs text-destructive">
              {error}
            </p>
          )}
          {savedMessage && <p className="text-xs text-muted-foreground">{savedMessage}</p>}

          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-lg bg-primary px-3 py-3 text-sm font-medium text-primary-foreground disabled:opacity-60"
          >
            {isSubmitting ? "저장 중..." : "저장"}
          </button>
        </form>
      </div>
    </main>
  );
}
