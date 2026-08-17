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

export type Gender = "M" | "F";

export interface TermItem {
  terms_type: string;
  version: string;
  title: string;
  url: string;
  is_required: boolean;
  revocable: boolean;
}

export interface TermsListResponse {
  terms: TermItem[];
}

export interface TermAgreementItem {
  terms_type: string;
  version: string;
  agreed: boolean;
}

export interface AvailabilityResponse {
  available: boolean;
  message: string;
}

export interface PhoneVerificationRequest {
  phone_number: string;
}

export interface PhoneVerificationResponse {
  verification_sent: boolean;
  message: string;
}

export interface PhoneVerificationConfirmRequest {
  phone_number: string;
  code: string;
}

export interface SignupRequest {
  email: string;
  password: string;
  name: string;
  nickname: string;
  birth_date: string;
  gender: Gender;
  phone_number: string;
  agreements: TermAgreementItem[];
}
