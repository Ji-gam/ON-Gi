import { apiRequest } from "./client";
import type { NotificationResponse } from "./notificationTypes";

export function listNotifications(accessToken: string): Promise<NotificationResponse[]> {
  return apiRequest<NotificationResponse[]>("/com/notifications", { accessToken });
}

export function markNotificationRead(
  notificationId: number,
  accessToken: string,
): Promise<NotificationResponse> {
  return apiRequest<NotificationResponse>(`/com/notifications/${notificationId}/read`, {
    method: "POST",
    accessToken,
  });
}
