import { apiRequest } from "./client";
import type {
  AuthResponse,
  EmailVerificationResponse,
  EmailVerifyResult,
  LoginRequest,
  PhoneVerificationConfirmRequest,
  PhoneVerificationResponse,
  SignupRequest,
  TermsListResponse,
} from "./types";

export function login(request: LoginRequest): Promise<AuthResponse> {
  return apiRequest<AuthResponse>("/auth/login", { method: "POST", body: request });
}

export function getTerms(): Promise<TermsListResponse> {
  return apiRequest<TermsListResponse>("/auth/terms");
}

export function requestEmailVerification(email: string): Promise<EmailVerificationResponse> {
  return apiRequest<EmailVerificationResponse>("/auth/email/verify-request", {
    method: "POST",
    body: { email },
  });
}

export function verifyEmail(token: string): Promise<EmailVerifyResult> {
  return apiRequest<EmailVerifyResult>(`/auth/email/verify?token=${encodeURIComponent(token)}`);
}

export function requestPhoneVerification(phoneNumber: string): Promise<PhoneVerificationResponse> {
  return apiRequest<PhoneVerificationResponse>("/auth/phone/verify-request", {
    method: "POST",
    body: { phone_number: phoneNumber },
  });
}

export function verifyPhone(request: PhoneVerificationConfirmRequest): Promise<{ detail: string }> {
  return apiRequest<{ detail: string }>("/auth/phone/verify", { method: "POST", body: request });
}

export function signup(request: SignupRequest): Promise<AuthResponse> {
  return apiRequest<AuthResponse>("/auth/signup", { method: "POST", body: request });
}
