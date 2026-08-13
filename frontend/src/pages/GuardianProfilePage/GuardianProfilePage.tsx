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

const WORK_TYPES: WorkType[] = [
  "FULL_TIME",
  "SHIFT",
  "FLEXIBLE",
  "REMOTE",
  "FREELANCE",
  "UNEMPLOYED",
  "OTHER",
];

const HOUSEHOLD_COMPOSITIONS: HouseholdComposition[] = [
  "TWO_PARENT",
  "SINGLE_PARENT",
  "EXTENDED_FAMILY",
  "OTHER",
];

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
      <main>
        <h1>보호자 프로필</h1>
        <p>불러오는 중...</p>
      </main>
    );
  }

  return (
    <main>
      <h1>보호자 프로필</h1>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="residenceH3">거주지(H3 인덱스)</label>
          <input
            id="residenceH3"
            required
            value={residenceH3}
            onChange={(event) => setResidenceH3(event.target.value)}
          />
        </div>
        <div>
          <label htmlFor="jobCategory">직군</label>
          <select
            id="jobCategory"
            required
            value={jobCategory}
            onChange={(event) => setJobCategory(event.target.value as JobCategory)}
          >
            <option value="" disabled>
              선택
            </option>
            {JOB_CATEGORIES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="workType">근무 형태</label>
          <select
            id="workType"
            required
            value={workType}
            onChange={(event) => setWorkType(event.target.value as WorkType)}
          >
            <option value="" disabled>
              선택
            </option>
            {WORK_TYPES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="householdComposition">가구 구성</label>
          <select
            id="householdComposition"
            required
            value={householdComposition}
            onChange={(event) =>
              setHouseholdComposition(event.target.value as HouseholdComposition)
            }
          >
            <option value="" disabled>
              선택
            </option>
            {HOUSEHOLD_COMPOSITIONS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
        <fieldset>
          <legend>보유 태그</legend>
          {GUARDIAN_TAG_CODES.map((tag) => (
            <div key={tag}>
              <label>
                <input type="checkbox" checked={tags.has(tag)} onChange={() => toggleTag(tag)} />
                {tag}
              </label>
            </div>
          ))}
        </fieldset>
        {error && <p>{error}</p>}
        {savedMessage && <p>{savedMessage}</p>}
        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "저장 중..." : "저장"}
        </button>
      </form>
    </main>
  );
}
