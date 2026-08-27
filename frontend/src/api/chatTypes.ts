// app/dtos/chat_dto.py 와 수동 동기화 (CODING_RULES.md §3-4).

export interface MessageResponse {
  id: number;
  sender_id: number;
  content: string;
  pii_masked: boolean;
  created_at: string;
}
