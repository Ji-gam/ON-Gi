// app/dtos/point_dto.py 와 수동 동기화 (CODING_RULES.md §3-4).

export interface BalanceResponse {
  user_id: number;
  balance: number;
  held_balance: number;
}

export interface TransactionEntryResponse {
  counterparty_id: number;
  reason: string;
  amount: number;
  created_at: string;
}
