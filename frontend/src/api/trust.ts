import { apiRequest } from "./client";
import type {
  EvaluationResponse,
  JointCareSessionCreate,
  JointCareSessionResponse,
  TrustRelationshipResponse,
  TrustScoreResponse,
  TrustSettingsResponse,
} from "./trustTypes";

export function getScore(userId: number, accessToken: string): Promise<TrustScoreResponse> {
  return apiRequest<TrustScoreResponse>(`/trs/users/${userId}/score`, { accessToken });
}

// 관계가 아직 없으면(첫 만남 전) 서버가 null을 반환한다.
export function getRelationship(
  otherUserId: number,
  accessToken: string,
): Promise<TrustRelationshipResponse | null> {
  return apiRequest<TrustRelationshipResponse | null>(`/trs/relationships/${otherUserId}`, {
    accessToken,
  });
}

export function createJointSession(
  otherUserId: number,
  request: JointCareSessionCreate,
  accessToken: string,
): Promise<JointCareSessionResponse> {
  return apiRequest<JointCareSessionResponse>(`/trs/relationships/${otherUserId}/joint-sessions`, {
    method: "POST",
    body: request,
    accessToken,
  });
}

export function confirmJointSession(
  jointSessionId: number,
  accessToken: string,
): Promise<JointCareSessionResponse> {
  return apiRequest<JointCareSessionResponse>(`/trs/joint-sessions/${jointSessionId}/confirm`, {
    method: "POST",
    accessToken,
  });
}

export function updateRequiredJointCount(
  count: number,
  accessToken: string,
): Promise<TrustSettingsResponse> {
  return apiRequest<TrustSettingsResponse>("/trs/settings/joint-count", {
    method: "PUT",
    body: { required_joint_count: count },
    accessToken,
  });
}

export function submitEvaluation(
  sessionId: number,
  rating: number,
  tags: string[],
  accessToken: string,
): Promise<EvaluationResponse> {
  return apiRequest<EvaluationResponse>(`/trs/sessions/${sessionId}/evaluations`, {
    method: "POST",
    body: { rating, tags },
    accessToken,
  });
}
