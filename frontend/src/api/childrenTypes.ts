// app/dtos/children.py 와 수동 동기화 (CODING_RULES.md §3-4).

export type ChildGender = "M" | "F";

export interface ChildCreateRequest {
  months_old: number;
  gender: ChildGender;
  temperament_memo: string | null;
  allergies: string | null;
  conditions: string | null;
  medications: string | null;
}

export interface ChildResponse {
  id: number;
  months_old: number;
  gender: ChildGender;
  temperament_memo: string | null;
  has_sensitive_info: boolean;
  created_at: string;
}

export interface ChildDetailResponse extends ChildResponse {
  allergies: string | null;
  conditions: string | null;
  medications: string | null;
}
