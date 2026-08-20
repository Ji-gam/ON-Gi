// app/dtos/care_session_dto.py 와 수동 동기화 (CODING_RULES.md §3-4).

export type CareSessionStatus = "REQUESTED" | "CONFIRMED" | "REJECTED" | "CANCELLED" | "NO_SHOW";

export interface CareRequestCreate {
  provider_id: number;
  child_id: number;
  meeting_h3: string;
  care_date: string;
  start_slot: number;
  end_slot: number;
  is_solo?: boolean;
}

export interface CancelRequest {
  reason?: string | null;
}

export interface CareSessionResponse {
  id: number;
  requester_id: number;
  provider_id: number;
  child_id: number;
  meeting_h3: string;
  care_date: string;
  start_slot: number;
  end_slot: number;
  status: CareSessionStatus;
  checkin_at: string | null;
  checkin_distance_m: number | null;
  checkin_out_of_range: boolean;
  checkin_reason: string | null;
  checkout_at: string | null;
  actual_minutes: number | null;
  cancelled_at: string | null;
  cancel_reason: string | null;
  at_fault_user_id: number | null;
}
