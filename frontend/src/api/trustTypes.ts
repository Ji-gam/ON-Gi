// app/dtos/trust_dto.py, app/dtos/trust_level_dto.py 와 수동 동기화 (CODING_RULES.md §3-4).

export type TrustLevel = "L1" | "L2" | "L3";

export type JointCareSessionStatus = "SCHEDULED" | "COMPLETED" | "CANCELLED";

export interface TrustScoreResponse {
  user_id: number;
  score: number;
}

export interface TrustRelationshipResponse {
  id: number;
  user_a_id: number;
  user_b_id: number;
  level: TrustLevel;
  joint_session_count: number;
  updated_at: string;
}

export interface JointCareSessionCreate {
  partner_id: number;
  place: string;
  scheduled_date: string;
}

export interface JointCareSessionResponse {
  id: number;
  initiator_id: number;
  partner_id: number;
  place: string;
  scheduled_date: string;
  confirmed_by_initiator: boolean;
  confirmed_by_partner: boolean;
  status: JointCareSessionStatus;
}

export interface TrustSettingsResponse {
  user_id: number;
  required_joint_count: number;
}

export interface EvaluationResponse {
  id: number;
  session_id: number;
  evaluator_id: number;
  evaluatee_id: number;
  rating: number;
}
