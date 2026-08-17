import { apiRequest } from "./client";
import type {
  AuthResponse,
  AvailabilityResponse,
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

export function checkNicknameAvailability(nickname: string): Promise<AvailabilityResponse> {
  return apiRequest<AvailabilityResponse>(
    `/auth/available/nickname?nickname=${encodeURIComponent(nickname)}`,
  );
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
