import { apiRequest } from "./client";
import type { BalanceResponse, TransactionEntryResponse } from "./pointTypes";

export function getBalance(accessToken: string): Promise<BalanceResponse> {
  return apiRequest<BalanceResponse>("/pnt/balance", { accessToken });
}

export function listTransactions(accessToken: string): Promise<TransactionEntryResponse[]> {
  return apiRequest<TransactionEntryResponse[]>("/pnt/transactions", { accessToken });
}
