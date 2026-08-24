import type { MessageResponse } from "./chatTypes";
import { apiRequest } from "./client";

export function listMessages(partnerId: number, accessToken: string): Promise<MessageResponse[]> {
  return apiRequest<MessageResponse[]>(`/com/chats/${partnerId}/messages`, { accessToken });
}

export function sendMessage(
  partnerId: number,
  content: string,
  accessToken: string,
): Promise<MessageResponse> {
  return apiRequest<MessageResponse>(`/com/chats/${partnerId}/messages`, {
    method: "POST",
    body: { content },
    accessToken,
  });
}
