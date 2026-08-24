import { apiRequest } from "./client";
import type { TrustScoreResponse } from "./trustTypes";

export function getScore(userId: number, accessToken: string): Promise<TrustScoreResponse> {
  return apiRequest<TrustScoreResponse>(`/trs/users/${userId}/score`, { accessToken });
}
