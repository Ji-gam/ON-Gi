import { apiRequest } from "./client";
import type { AuthResponse, LoginRequest } from "./types";

export function login(request: LoginRequest): Promise<AuthResponse> {
  return apiRequest<AuthResponse>("/auth/login", { method: "POST", body: request });
}
