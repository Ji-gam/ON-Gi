import type {
  CancelRequest,
  CareLogResponse,
  CareLogUpsert,
  CareRequestCreate,
  CareSessionResponse,
  CheckinRequest,
} from "./careTypes";
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

export function checkin(
  sessionId: number,
  request: CheckinRequest,
  accessToken: string,
): Promise<CareSessionResponse> {
  return apiRequest<CareSessionResponse>(`/car/requests/${sessionId}/checkin`, {
    method: "POST",
    body: request,
    accessToken,
  });
}

export function checkout(sessionId: number, accessToken: string): Promise<CareSessionResponse> {
  return apiRequest<CareSessionResponse>(`/car/requests/${sessionId}/checkout`, {
    method: "POST",
    accessToken,
  });
}

export function upsertJournal(
  sessionId: number,
  request: CareLogUpsert,
  accessToken: string,
): Promise<CareLogResponse> {
  return apiRequest<CareLogResponse>(`/car/requests/${sessionId}/journal`, {
    method: "PUT",
    body: request,
    accessToken,
  });
}

export function getJournal(
  sessionId: number,
  accessToken: string,
): Promise<CareLogResponse | null> {
  return apiRequest<CareLogResponse | null>(`/car/requests/${sessionId}/journal`, { accessToken });
}
