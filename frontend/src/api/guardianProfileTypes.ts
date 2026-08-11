// app/dtos/guardian_profile_dto.py, app/models/guardian_profile.py 와 수동 동기화 (CODING_RULES.md §3-4).

export type JobCategory =
  | "OFFICE_WORKER"
  | "SERVICE"
  | "SELF_EMPLOYED"
  | "HEALTHCARE"
  | "EDUCATION"
  | "IT"
  | "PUBLIC_SERVANT"
  | "HOMEMAKER"
  | "FREELANCER"
  | "OTHER";

export type WorkType =
  "FULL_TIME" | "SHIFT" | "FLEXIBLE" | "REMOTE" | "FREELANCE" | "UNEMPLOYED" | "OTHER";

export type HouseholdComposition = "TWO_PARENT" | "SINGLE_PARENT" | "EXTENDED_FAMILY" | "OTHER";

// app/core/utils/guardian_tags.py — 완화 불가 4종 + 선택 태그(추후 확정 예정, 확장 가능한 문자열 코드).
export const GUARDIAN_TAG_CODES = [
  "ALLERGY_RESPONSE",
  "MEDICATION_MANAGEMENT",
  "FIRST_AID_CERTIFIED",
  "NON_SMOKING_HOUSEHOLD",
  "HAS_VEHICLE",
] as const;

export interface GuardianProfileUpsertRequest {
  residence_h3: string;
  job_category: JobCategory;
  work_type: WorkType;
  household_composition: HouseholdComposition;
  tags: string[];
}

export interface GuardianProfileResponse {
  residence_h3: string;
  job_category: JobCategory;
  work_type: WorkType;
  household_composition: HouseholdComposition;
  tags: string[];
  updated_at: string;
}
