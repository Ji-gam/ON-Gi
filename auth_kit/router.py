"""FastAPI 라우터. 세션 의존성(get_session)과 메일 발송(send_email)만 프로젝트가 주입한다.

배선:
    from auth_kit.router import auth_router, get_session, send_email
    app.include_router(auth_router, prefix="/api/v1")
    app.dependency_overrides[get_session] = my_get_session
    auth_kit.router.send_email = my_send_email   # 안 바꾸면 메일 링크가 로그로만 나간다
"""

import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from security_kit.guards import clear_refresh_cookie, set_refresh_cookie

from . import config
from .models import AuthProvider, OnboardingStatus, User
from .schemas import (
    AgreementStatusResponse,
    AgreementSubmitRequest,
    AuthResponse,
    AuthUser,
    AvailabilityResponse,
    EmailVerificationRequest,
    FindEmailRequest,
    FindEmailResponse,
    LoginRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PhoneVerificationConfirmRequest,
    PhoneVerificationRequest,
    SignUpRequest,
    SocialAuthResponse,
    SocialLoginRequest,
    SocialSignUpCompleteRequest,
    TermResponse,
    TermsListResponse,
    TokenRefreshResponse,
    VerificationResponse,
    WithdrawRequest,
)
from .security import (
    GOOGLE_ISSUER,
    GOOGLE_JWKS_URL,
    KAKAO_ISSUER,
    KAKAO_JWKS_URL,
    verify_oidc_id_token,
)
from .service import AuthResult, AuthService, SocialProfile
from .terms_catalog import TERMS_CATALOG

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["auth"])


# ── 프로젝트가 주입해야 하는 두 가지 ────────────────────────────────────────
async def get_session() -> AsyncIterator[AsyncSession]:
    raise NotImplementedError(
        "app.dependency_overrides[auth_kit.router.get_session] = 프로젝트의 세션 의존성 으로 주입하세요."
    )


async def send_email(to: str, subject: str, html_body: str) -> bool:
    """기본 구현은 발송하지 않고 로그만 남긴다(로컬 개발에서 링크를 복사해 쓸 수 있게).
    운영에서는 반드시 실제 메일러로 교체한다."""
    logger.warning("send_email이 주입되지 않았습니다. to=%s subject=%s\n%s", to, subject, html_body)
    return False


async def send_sms(to: str, body: str) -> bool:
    """기본 구현은 발송하지 않고 로그만 남긴다(로컬 개발에서 OTP를 로그로 확인).
    운영에서는 반드시 실제 SMS 게이트웨이로 교체한다: `auth_kit.router.send_sms = my_send_sms`."""
    logger.warning("send_sms이 주입되지 않았습니다. to=%s\n%s", to, body)
    return False


def _service(session: AsyncSession) -> AuthService:
    return AuthService(session)


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "인증이 필요합니다.")
    return await _service(session).get_user_by_access_token(authorization.split(" ", 1)[1].strip())


CurrentUser = Annotated[User, Depends(get_current_user)]
Session = Annotated[AsyncSession, Depends(get_session)]


# ── 응답 조립 ───────────────────────────────────────────────────────────────
def _auth_user(user: User) -> AuthUser:
    return AuthUser(
        id=user.id,
        nickname=user.nickname,
        email=user.email,
        onboarding_status=user.onboarding_status,
        is_guest=user.is_guest,
        has_password=user.password_hash is not None,
    )


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """httpOnly + secure + samesite 플래그와 max_age 처리는 security_kit.guards가 담당한다."""
    set_refresh_cookie(response, refresh_token, config.REFRESH_TOKEN_TTL)


def _auth_response(response: Response, result: AuthResult) -> AuthResponse:
    _set_refresh_cookie(response, result.tokens.refresh_token)
    return AuthResponse(
        user=_auth_user(result.user), access_token=result.tokens.access_token, is_new_user=result.is_new_user
    )


# ══════════════════════════════════════════════════════════════════════════
# 약관
# ══════════════════════════════════════════════════════════════════════════
@auth_router.get("/terms", response_model=TermsListResponse, summary="현재 유효한 약관 목록")
async def list_terms() -> TermsListResponse:
    """가입 화면이 이 응답의 terms_type/version을 그대로 되돌려 보내야 한다.
    임의의 값을 보내면 400, 구버전을 보내면 409로 거부된다."""
    return TermsListResponse(
        terms=[
            TermResponse(
                terms_type=str(s.terms_type),
                version=s.version,
                title=s.title,
                url=s.url,
                is_required=s.is_required,
                revocable=s.revocable,
            )
            for s in TERMS_CATALOG
        ]
    )


# ══════════════════════════════════════════════════════════════════════════
# 중복확인 (가입 화면 onBlur)
# ══════════════════════════════════════════════════════════════════════════
@auth_router.get("/available/email", response_model=AvailabilityResponse, summary="이메일 사용 가능 여부")
async def check_email(session: Session, email: str) -> AvailabilityResponse:
    taken = await _service(session).is_email_taken(email)
    return AvailabilityResponse(
        available=not taken, message="이미 사용중인 이메일이에요." if taken else "사용 가능한 이메일이에요."
    )


@auth_router.get("/available/nickname", response_model=AvailabilityResponse, summary="닉네임 사용 가능 여부")
async def check_nickname(session: Session, nickname: str) -> AvailabilityResponse:
    taken = await _service(session).is_nickname_taken(nickname)
    return AvailabilityResponse(
        available=not taken, message="이미 사용중인 닉네임이에요." if taken else f"'{nickname}' 사용 가능해요."
    )


@auth_router.get("/available/phone", response_model=AvailabilityResponse, summary="휴대폰 번호 사용 가능 여부")
async def check_phone(session: Session, phone_number: str) -> AvailabilityResponse:
    taken = await _service(session).is_phone_taken(phone_number)
    return AvailabilityResponse(
        available=not taken, message="이미 사용중인 번호예요." if taken else "사용 가능한 번호예요."
    )


# ══════════════════════════════════════════════════════════════════════════
# 이메일 인증
# ══════════════════════════════════════════════════════════════════════════
@auth_router.post(
    "/email/verify-request",
    response_model=VerificationResponse,
    summary="이메일 인증 메일 발송",
    responses={status.HTTP_409_CONFLICT: {"description": "이미 사용중인 이메일"}},
)
async def request_email_verification(session: Session, request: EmailVerificationRequest) -> VerificationResponse:
    token, _ = await _service(session).request_email_verification(str(request.email))
    link = f"{config.FRONTEND_BASE_URL}/auth/email/verify?token={token}"
    minutes = int(config.EMAIL_VERIFICATION_TTL.total_seconds() // 60)
    sent = await send_email(
        to=str(request.email),
        subject="[인증] 이메일 인증을 완료해주세요",
        html_body=f'<p>아래 링크를 클릭하면 인증이 완료됩니다. (유효시간 {minutes}분)</p><p><a href="{link}">{link}</a></p>',
    )
    # 발송 실패로 500을 내지 않는다 - 토큰 행은 이미 만들어졌고, 프론트는 "재발송" 안내만 하면 된다.
    return VerificationResponse(
        verification_sent=sent,
        message="인증 메일을 보냈습니다." if sent else "메일 발송에 실패했습니다. 잠시 후 다시 시도해주세요.",
    )


@auth_router.get("/email/verify", summary="이메일 인증 링크 처리")
async def verify_email(session: Session, token: str) -> dict[str, str]:
    email = await _service(session).verify_email_token(token)
    return {"detail": "이메일 인증이 완료되었습니다.", "email": email}


# ══════════════════════════════════════════════════════════════════════════
# 휴대폰 본인확인 (REQ-F-ACC-01)
# ══════════════════════════════════════════════════════════════════════════
@auth_router.post(
    "/phone/verify-request",
    response_model=VerificationResponse,
    summary="휴대폰 본인확인 코드(OTP) 발송",
    responses={status.HTTP_409_CONFLICT: {"description": "이미 사용중인 휴대폰 번호"}},
)
async def request_phone_verification(session: Session, request: PhoneVerificationRequest) -> VerificationResponse:
    code, _ = await _service(session).request_phone_verification(request.phone_number)
    minutes = int(config.PHONE_VERIFICATION_TTL.total_seconds() // 60)
    sent = await send_sms(
        to=request.phone_number, body=f"[인증] 인증번호 [{code}]를 입력해주세요. (유효시간 {minutes}분)"
    )
    return VerificationResponse(
        verification_sent=sent,
        message="인증 코드를 보냈습니다." if sent else "코드 발송에 실패했습니다. 잠시 후 다시 시도해주세요.",
    )


@auth_router.post("/phone/verify", summary="휴대폰 본인확인 코드 검증")
async def verify_phone(session: Session, request: PhoneVerificationConfirmRequest) -> dict[str, str]:
    await _service(session).verify_phone_code(request.phone_number, request.code)
    return {"detail": "휴대폰 본인확인이 완료되었습니다."}


# ══════════════════════════════════════════════════════════════════════════
# 회원가입 / 로그인
# ══════════════════════════════════════════════════════════════════════════
@auth_router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="이메일 회원가입",
    description="가입과 동시에 토큰을 발급한다 - 프론트가 가입 직후 로그인을 다시 호출할 필요가 없다.",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "이메일 미인증 또는 필수 약관 미동의"},
        status.HTTP_409_CONFLICT: {"description": "이메일/닉네임/휴대폰 중복, 또는 약관 버전 불일치"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "비밀번호/생년월일/휴대폰 형식 오류, 만14세 미만"},
    },
)
async def signup(session: Session, request: SignUpRequest, response: Response) -> AuthResponse:
    result = await _service(session).signup(request)
    response.status_code = status.HTTP_201_CREATED
    return _auth_response(response, result)


@auth_router.post(
    "/login",
    response_model=AuthResponse,
    summary="이메일 로그인",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "이메일 또는 비밀번호 불일치"},
        status.HTTP_423_LOCKED: {"description": "시도 횟수 초과로 잠김, 비활성 또는 탈퇴 처리 중"},
    },
)
async def login(session: Session, request: LoginRequest, response: Response) -> AuthResponse:
    result = await _service(session).login(str(request.email), request.password)
    return _auth_response(response, result)


@auth_router.post(
    "/token/refresh",
    response_model=TokenRefreshResponse,
    summary="액세스 토큰 재발급",
    description=(
        "쿠키의 refresh_token으로 새 액세스 토큰을 발급한다. 요청 본문은 없다. "
        "[로테이션] refresh_token 자체도 새 값으로 교체되고, 예전 값은 즉시 무효화된다. "
        "무효화된 토큰이 다시 오면 탈취로 간주해 그 계정의 모든 세션이 로그아웃된다."
    ),
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "쿠키 없음/만료/무효화/재사용 탐지"}},
)
async def refresh_token(
    session: Session, response: Response, refresh_token: Annotated[str | None, Cookie()] = None
) -> TokenRefreshResponse:
    if not refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh_token 쿠키가 없습니다.")
    tokens = await _service(session).rotate_refresh_token(refresh_token)
    _set_refresh_cookie(response, tokens.refresh_token)
    return TokenRefreshResponse(access_token=tokens.access_token)


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="로그아웃")
async def logout(session: Session, response: Response, refresh_token: Annotated[str | None, Cookie()] = None) -> None:
    """쿠키가 없거나 이미 만료됐어도 항상 성공한다."""
    await _service(session).logout(refresh_token)
    clear_refresh_cookie(response)


# ══════════════════════════════════════════════════════════════════════════
# 소셜 로그인/가입 (모바일 SDK ID token 흐름)
# ══════════════════════════════════════════════════════════════════════════
_PROVIDER_OIDC = {
    AuthProvider.GOOGLE: (GOOGLE_ISSUER, GOOGLE_JWKS_URL, config.google_client_id),
    AuthProvider.KAKAO: (KAKAO_ISSUER, KAKAO_JWKS_URL, config.kakao_app_key),
}


@auth_router.post(
    "/social/{provider}",
    response_model=SocialAuthResponse,
    summary="소셜 로그인 (신규는 signup_token만 발급)",
    description=(
        "앱 SDK가 받은 ID token을 서버가 검증한다. 기존 사용자는 곧바로 로그인되고, "
        "신규는 계정을 만들지 않고 signup_token만 돌려준다 - 약관 동의와 생년월일을 받지 않은 "
        "계정이 생기면 안 되기 때문이다. 이어서 /social/complete를 호출한다."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "서명/aud/iss/만료/nonce 검증 실패 또는 nonce 재사용"},
        status.HTTP_409_CONFLICT: {"description": "이미 다른 방식으로 가입된 이메일"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "공급자 설정 누락 또는 공개키 서버 연결 실패"},
    },
)
async def social_login(
    session: Session, provider: AuthProvider, request: SocialLoginRequest, response: Response
) -> SocialAuthResponse:
    import jwt as pyjwt

    oidc = _PROVIDER_OIDC.get(provider)
    if oidc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"지원하지 않는 provider입니다: {provider}")
    issuer, jwks_url, audience_getter = oidc
    audience = audience_getter()
    if not audience:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"{provider} 로그인이 설정되지 않았습니다.")

    try:
        claims = await verify_oidc_id_token(request.id_token, request.nonce, issuer, audience, jwks_url)
    except pyjwt.InvalidTokenError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "소셜 로그인 토큰 검증에 실패했습니다.") from e
    except Exception as e:  # JWKS 조회 실패 등 네트워크 문제
        logger.exception("소셜 공개키 조회 실패: provider=%s", provider)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "소셜 로그인 서버에 연결할 수 없습니다.") from e

    service = _service(session)
    await service.consume_nonce(provider, request.nonce)
    profile = SocialProfile(
        provider=provider,
        provider_uid=str(claims["sub"]),
        email=claims.get("email"),
        name=claims.get("name") or claims.get("nickname"),
    )
    outcome = await service.social_login(profile)
    if outcome.is_new_user:
        return SocialAuthResponse(is_new_user=True, signup_token=outcome.signup_token)

    assert outcome.result is not None
    _set_refresh_cookie(response, outcome.result.tokens.refresh_token)
    return SocialAuthResponse(
        is_new_user=False, user=_auth_user(outcome.result.user), access_token=outcome.result.tokens.access_token
    )


@auth_router.post(
    "/social/complete",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="소셜 신규 가입 완료 (추가정보 + 약관 동의)",
)
async def complete_social_signup(
    session: Session, request: SocialSignUpCompleteRequest, response: Response
) -> AuthResponse:
    result = await _service(session).complete_social_signup(request)
    response.status_code = status.HTTP_201_CREATED
    return _auth_response(response, result)


@auth_router.post("/guest", response_model=AuthResponse, summary="체험하기(게스트) 로그인")
async def guest_login(session: Session, response: Response) -> AuthResponse:
    """개인정보를 받지 않고 임시 계정을 만든다. 매 호출마다 새 계정이다."""
    result = await _service(session).guest_login()
    return _auth_response(response, result)


# ══════════════════════════════════════════════════════════════════════════
# 동의 관리 (가입 이후 / 약관 개정 시 재동의)
# ══════════════════════════════════════════════════════════════════════════
@auth_router.get("/me/agreements", response_model=AgreementStatusResponse, summary="내 동의 현황")
async def get_agreements(session: Session, user: CurrentUser) -> AgreementStatusResponse:
    items = await _service(session).agreement_status(user)
    return AgreementStatusResponse.model_validate({"onboarding_status": user.onboarding_status, "agreements": items})


@auth_router.post("/me/agreements", response_model=AgreementStatusResponse, summary="약관 동의 제출/갱신")
async def submit_agreements(
    session: Session, user: CurrentUser, request: AgreementSubmitRequest
) -> AgreementStatusResponse:
    service = _service(session)
    updated = await service.submit_agreements(user, request.agreements)
    items = await service.agreement_status(updated)
    return AgreementStatusResponse.model_validate({"onboarding_status": updated.onboarding_status, "agreements": items})


@auth_router.delete(
    "/me/agreements/{terms_type}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="선택 동의 철회",
    description="선택 항목만 철회할 수 있다. 필수 약관 철회는 400 - 회원탈퇴로 안내한다.",
)
async def revoke_agreement(session: Session, user: CurrentUser, terms_type: str) -> None:
    await _service(session).revoke_agreement(user, terms_type)


@auth_router.post("/me/onboarding/complete", response_model=AuthUser, summary="온보딩 완료 처리")
async def complete_onboarding(session: Session, user: CurrentUser) -> AuthUser:
    return _auth_user(await _service(session).advance_onboarding(user, OnboardingStatus.COMPLETED))


# ══════════════════════════════════════════════════════════════════════════
# 아이디 찾기 / 비밀번호 재설정
# ══════════════════════════════════════════════════════════════════════════
@auth_router.post("/find-email", response_model=FindEmailResponse, summary="아이디(이메일) 찾기")
async def find_email(session: Session, request: FindEmailRequest) -> FindEmailResponse:
    return FindEmailResponse(email=await _service(session).find_email(request.name, request.nickname))


@auth_router.post("/password/reset-request", summary="비밀번호 재설정 메일 발송")
async def request_password_reset(session: Session, request: PasswordResetRequest) -> dict[str, str]:
    """가입 안 된 이메일이어도 성공처럼 응답한다 - 어느 이메일이 가입돼 있는지 노출하지 않기 위함."""
    token, message = await _service(session).create_password_reset_token(str(request.email))
    if token:
        link = f"{config.FRONTEND_BASE_URL}/auth/password/reset?token={token}"
        minutes = int(config.PASSWORD_RESET_TTL.total_seconds() // 60)
        await send_email(
            to=str(request.email),
            subject="[인증] 비밀번호 재설정 안내",
            html_body=f'<p>아래 링크에서 비밀번호를 재설정해주세요. (유효시간 {minutes}분)</p><p><a href="{link}">{link}</a></p>',
        )
    return {"detail": message}


@auth_router.post("/password/reset", summary="비밀번호 재설정 확정")
async def reset_password(session: Session, request: PasswordResetConfirmRequest) -> dict[str, str]:
    await _service(session).reset_password(request.token, request.new_password)
    return {"detail": "비밀번호가 재설정되었습니다. 기존 로그인 세션은 모두 종료되었습니다."}


# ══════════════════════════════════════════════════════════════════════════
# 회원탈퇴
# ══════════════════════════════════════════════════════════════════════════
@auth_router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="회원탈퇴",
    description=(
        "본인 확인용 현재 비밀번호를 재확인한 뒤 처리한다(탈취된 토큰만으로 탈퇴되는 것을 막는다). "
        "소셜/게스트 계정은 비밀번호가 없어 생략한다. WITHDRAWAL_GRACE 기간 안에는 취소할 수 있고, "
        "지나면 purge_deactivated()가 물리 삭제한다."
    ),
    responses={status.HTTP_400_BAD_REQUEST: {"description": "비밀번호 불일치"}},
)
async def withdraw(session: Session, user: CurrentUser, request: WithdrawRequest, response: Response) -> None:
    await _service(session).withdraw(user, request.password)
    clear_refresh_cookie(response)


@auth_router.post("/me/withdraw/cancel", response_model=AuthResponse, summary="회원탈퇴 취소")
async def cancel_withdrawal(session: Session, request: LoginRequest, response: Response) -> AuthResponse:
    """탈퇴 신청 후에는 로그인이 막히므로 인증 없이 이메일+비밀번호로만 본인 확인한다."""
    result = await _service(session).cancel_withdrawal(str(request.email), request.password)
    return _auth_response(response, result)
