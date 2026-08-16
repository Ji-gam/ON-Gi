"""요청/응답 DTO. 형식 검증은 여기서 끝내고, DB가 필요한 검증(중복 등)은 service.py에서 한다."""

from datetime import date
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, model_validator

from . import validators
from .models import Gender, OnboardingStatus


class TermAgreementItem(BaseModel):
    terms_type: Annotated[str, Field(description="약관 종류. GET /auth/terms의 terms_type을 그대로 보낸다.")]
    version: Annotated[str, Field(description="화면에 보여준 약관 버전. 구버전이면 409로 거부된다.")]
    agreed: bool


class SignUpRequest(BaseModel):
    """이메일 회원가입 요청.

    동의를 boolean 3개(terms_agreed/privacy_agreed/...)로 받지 않고 목록으로 받는 이유:
    약관이 하나 늘거나 버전이 오를 때마다 DTO·DB 컬럼·프론트를 같이 고쳐야 하는 구조를
    피하기 위함이다. 카탈로그만 고치면 나머지가 따라온다.
    """

    email: Annotated[EmailStr, Field(max_length=254, examples=["hong@example.com"])]
    password: Annotated[
        str,
        Field(description="영문 대·소문자, 숫자, 특수문자 각 1자 이상 포함 8자 이상", examples=["Password123!"]),
        AfterValidator(validators.sanitize_credential),
        AfterValidator(validators.validate_password),
    ]
    name: Annotated[str, Field(max_length=20, description="실명. 암호화되어 저장된다.", examples=["홍길동"])]
    nickname: Annotated[str, Field(min_length=2, max_length=12), AfterValidator(validators.validate_nickname)]
    birth_date: Annotated[date, AfterValidator(validators.validate_birth_date)]
    gender: Gender
    # REQ-F-ACC-01: 가입 전 /auth/phone/verify로 본인확인을 마친 번호만 받는다.
    phone_number: Annotated[str, Field(examples=["010-1234-5678"]), AfterValidator(validators.validate_phone_number)]
    agreements: Annotated[list[TermAgreementItem], Field(min_length=1)]


class LoginRequest(BaseModel):
    email: EmailStr
    password: Annotated[str, AfterValidator(validators.sanitize_credential)]


class AuthUser(BaseModel):
    """로그인/가입 응답에 공통으로 들어가는 사용자 요약."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nickname: str
    email: str | None
    onboarding_status: OnboardingStatus
    is_guest: bool
    # 소셜 가입자는 비밀번호가 없다 - 프론트가 비밀번호 변경/탈퇴 화면에서 입력란 자체를
    # 숨기는 데 쓴다(없는 비밀번호를 요구해서 탈퇴가 막히는 사고를 방지).
    has_password: bool


class AuthResponse(BaseModel):
    """가입·로그인·소셜 완료가 모두 같은 형태로 응답한다.

    가입 응답에 곧바로 토큰을 담는 이유: 안 그러면 프론트가 가입 직후 사용자가 방금 입력한
    비밀번호로 로그인을 한 번 더 호출해야 하고, 그 두 번째 호출이 실패하면 "계정은
    만들어졌는데 가입이 실패한 것처럼" 보인다.
    """

    user: AuthUser
    access_token: str
    # CODING_RULES.md §11-4 — 로그인/가입/토큰재발급 응답 바디엔 access_token만.
    token_type: str = "bearer"
    is_new_user: bool = False
    # refresh token은 응답 body에 넣지 않는다 - httpOnly 쿠키로만 내려간다.
    # body에 담아 localStorage에 저장하면 XSS 한 번으로 장기 토큰이 전부 털린다.


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AvailabilityResponse(BaseModel):
    """가입 화면에서 onBlur마다 부르는 중복확인 응답.

    상태코드가 아니라 body의 available로 판단하게 한다(200/409로 신호를 주면 프론트가
    정상 흐름을 try/catch로 다뤄야 하고, 네트워크 오류와 중복을 구분하기 어렵다).
    """

    available: bool
    message: str


class EmailVerificationRequest(BaseModel):
    email: Annotated[EmailStr, Field(max_length=254)]


class VerificationResponse(BaseModel):
    """이메일 인증메일/휴대폰 OTP 발송 응답 공통 형태.

    SMTP/SMS 설정 누락 등으로 발송 자체가 실패해도 500으로 터뜨리지 않고 이 값으로 알려준다.
    """

    verification_sent: bool
    message: str


class PhoneVerificationRequest(BaseModel):
    phone_number: Annotated[str, Field(examples=["010-1234-5678"]), AfterValidator(validators.validate_phone_number)]


class PhoneVerificationConfirmRequest(BaseModel):
    phone_number: Annotated[str, Field(examples=["010-1234-5678"]), AfterValidator(validators.validate_phone_number)]
    code: Annotated[str, Field(pattern=r"^\d{6}$", examples=["123456"])]


class TermResponse(BaseModel):
    terms_type: str
    version: str
    title: str
    url: str
    is_required: bool
    revocable: bool


class TermsListResponse(BaseModel):
    terms: list[TermResponse]


class AgreementSubmitRequest(BaseModel):
    agreements: Annotated[list[TermAgreementItem], Field(min_length=1)]


class AgreementStatusItem(BaseModel):
    terms_type: str
    agreed_version: str | None
    current_version: str
    is_required: bool
    agreed: bool
    needs_reagreement: bool


class AgreementStatusResponse(BaseModel):
    onboarding_status: OnboardingStatus
    agreements: list[AgreementStatusItem]


class SocialLoginRequest(BaseModel):
    """모바일 앱 SDK 흐름. 웹 리다이렉트 OAuth라면 authorization_code를 쓴다."""

    id_token: Annotated[str, Field(min_length=1, max_length=10000)]
    nonce: Annotated[str, Field(min_length=16, max_length=512, description="ID token 발급 요청에 사용한 nonce")]


class SocialAuthResponse(BaseModel):
    """신규 사용자는 계정이 아직 만들어지지 않았다 - access_token 대신 signup_token이 온다.

    소셜에서 받은 이메일/이름만으로 곧바로 계정을 만들어버리면 필수 약관 동의와 만14세
    확인을 건너뛰게 된다. 그래서 신규는 2단계로 나눈다.
    """

    is_new_user: bool
    signup_token: str | None = None
    user: AuthUser | None = None
    access_token: str | None = None
    token_type: str = "bearer"


class SocialSignUpCompleteRequest(BaseModel):
    signup_token: str
    nickname: Annotated[str, Field(min_length=2, max_length=12), AfterValidator(validators.validate_nickname)]
    birth_date: Annotated[date, AfterValidator(validators.validate_birth_date)]
    gender: Gender
    name: Annotated[str | None, Field(None, max_length=20)]
    # REQ-F-ACC-01: 소셜 가입도 본인확인을 거친다 - SignUpRequest와 동일하게 필수.
    phone_number: Annotated[str, Field(examples=["010-1234-5678"]), AfterValidator(validators.validate_phone_number)]
    agreements: Annotated[list[TermAgreementItem], Field(min_length=1)]


class FindEmailRequest(BaseModel):
    name: Annotated[str, Field(max_length=20)]
    nickname: Annotated[str, Field(min_length=2, max_length=12)]


class FindEmailResponse(BaseModel):
    email: Annotated[str, Field(description="마스킹된 이메일. 전체 주소는 돌려주지 않는다.")]


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: Annotated[
        str, AfterValidator(validators.sanitize_credential), AfterValidator(validators.validate_password)
    ]
    new_password_confirm: str

    @model_validator(mode="after")
    def check_match(self) -> Self:
        if self.new_password != validators.sanitize_credential(self.new_password_confirm):
            raise ValueError("새 비밀번호가 일치하지 않습니다.")
        return self


class WithdrawRequest(BaseModel):
    password: Annotated[
        str | None,
        Field(None, description="본인 확인용 현재 비밀번호. 소셜/게스트 계정은 비밀번호가 없어 생략한다."),
    ]
    reason: Annotated[str | None, Field(None, max_length=500)]
