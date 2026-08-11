// auth_kit/schemas.py 와 수동 동기화 (CODING_RULES.md §3-4) — 백엔드 DTO 변경 시 같은 PR에서 갱신.

export interface AuthUser {
  id: number;
  nickname: string;
  email: string | null;
  onboarding_status: string;
  is_guest: boolean;
  has_password: boolean;
}

export interface AuthResponse {
  user: AuthUser;
  access_token: string;
  token_type: string;
  is_new_user: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
}
