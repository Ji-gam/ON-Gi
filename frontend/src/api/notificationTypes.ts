// app/dtos/notification_dto.py 와 수동 동기화 (CODING_RULES.md §3-4).

export type NotificationType =
  | "REQUEST_CREATED"
  | "REQUEST_ACCEPTED"
  | "REQUEST_REJECTED"
  | "SESSION_COMPLETED"
  | "SESSION_CANCELLED"
  | "NO_SHOW_REPORTED"
  | "TRUST_LEVEL_TRANSITION";

export interface NotificationResponse {
  id: number;
  type: NotificationType;
  message: string;
  payload: Record<string, unknown> | null;
  read_at: string | null;
  created_at: string;
}
