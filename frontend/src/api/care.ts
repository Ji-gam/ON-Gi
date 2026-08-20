import type { CancelRequest, CareRequestCreate, CareSessionResponse } from "./careTypes";
import { apiRequest } from "./client";

export function createRequest(
  request: CareRequestCreate,
  accessToken: string,
): Promise<CareSessionResponse> {
  return apiRequest<CareSessionResponse>("/car/requests", {
    method: "POST",
    body: request,
    accessToken,
  });
}

export function listRequests(accessToken: string): Promise<CareSessionResponse[]> {
  return apiRequest<CareSessionResponse[]>("/car/requests", { accessToken });
}

export function getRequest(sessionId: number, accessToken: string): Promise<CareSessionResponse> {
  return apiRequest<CareSessionResponse>(`/car/requests/${sessionId}`, { accessToken });
}

export function acceptRequest(
  sessionId: number,
  accessToken: string,
): Promise<CareSessionResponse> {
  return apiRequest<CareSessionResponse>(`/car/requests/${sessionId}/accept`, {
    method: "POST",
    accessToken,
  });
}

export function rejectRequest(
  sessionId: number,
  accessToken: string,
): Promise<CareSessionResponse> {
  return apiRequest<CareSessionResponse>(`/car/requests/${sessionId}/reject`, {
    method: "POST",
    accessToken,
  });
}

export function cancelRequest(
  sessionId: number,
  request: CancelRequest,
  accessToken: string,
): Promise<CareSessionResponse> {
  return apiRequest<CareSessionResponse>(`/car/requests/${sessionId}/cancel`, {
    method: "POST",
    body: request,
    accessToken,
  });
}
