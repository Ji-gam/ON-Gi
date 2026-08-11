import { apiRequest } from "./client";
import type { ShiftRegisterRequest, WorkScheduleResponse } from "./workScheduleTypes";

export function registerShift(
  request: ShiftRegisterRequest,
  accessToken: string,
): Promise<WorkScheduleResponse[]> {
  return apiRequest<WorkScheduleResponse[]>("/sch/schedule", {
    method: "PUT",
    body: request,
    accessToken,
  });
}

export function getSchedule(
  start: string,
  end: string | undefined,
  accessToken: string,
): Promise<WorkScheduleResponse[]> {
  const query = end ? `?start=${start}&end=${end}` : `?start=${start}`;
  return apiRequest<WorkScheduleResponse[]>(`/sch/schedule${query}`, { accessToken });
}
