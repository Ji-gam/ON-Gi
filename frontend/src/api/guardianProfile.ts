import { apiRequest } from "./client";
import type { GuardianProfileResponse, GuardianProfileUpsertRequest } from "./guardianProfileTypes";

export function getGuardianProfile(accessToken: string): Promise<GuardianProfileResponse> {
  return apiRequest<GuardianProfileResponse>("/acc/guardian-profile", { accessToken });
}

export function upsertGuardianProfile(
  request: GuardianProfileUpsertRequest,
  accessToken: string,
): Promise<GuardianProfileResponse> {
  return apiRequest<GuardianProfileResponse>("/acc/guardian-profile", {
    method: "PUT",
    body: request,
    accessToken,
  });
}
