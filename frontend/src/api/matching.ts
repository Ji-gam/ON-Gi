import { apiRequest } from "./client";
import type { CandidateResponse } from "./matchingTypes";

export function getCandidates(accessToken: string): Promise<CandidateResponse[]> {
  return apiRequest<CandidateResponse[]>("/mat/candidates", { accessToken });
}
