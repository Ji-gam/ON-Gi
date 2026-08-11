import type { ChildCreateRequest, ChildDetailResponse, ChildResponse } from "./childrenTypes";
import { apiRequest } from "./client";

export function listChildren(accessToken: string): Promise<ChildResponse[]> {
  return apiRequest<ChildResponse[]>("/acc/children", { accessToken });
}

export function createChild(
  request: ChildCreateRequest,
  accessToken: string,
): Promise<ChildDetailResponse> {
  return apiRequest<ChildDetailResponse>("/acc/children", {
    method: "POST",
    body: request,
    accessToken,
  });
}

export function deleteChild(childId: number, accessToken: string): Promise<void> {
  return apiRequest<void>(`/acc/children/${childId}`, { method: "DELETE", accessToken });
}
