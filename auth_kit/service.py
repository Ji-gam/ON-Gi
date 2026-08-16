"""회원가입/인증 비즈니스 로직 전부. 라우터는 이 클래스를 부르기만 한다.

Repository 계층을 따로 두지 않았다 - 쿼리가 대부분 한 줄짜리 select라, 레포지토리를
끼우면 파일만 하나 늘고 같은 시그니처를 두 번 쓰게 된다. 쿼리가 복잡해지거나 다른
도메인과 공유하게 되면 그때 분리한다.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import jwt
from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from security_kit.guards import LockoutPolicy

from . import config, security, validators
from ._time import now as _now
from .models import (
    AuthProvider,
    EmailVerificationToken,
    Gender,
    OAuthNonce,
    OnboardingStatus,
    RefreshToken,
    SanctionedIdentity,
    SocialAccount,
    TermsAgreement,
    User,
)
from .schemas import SignUpRequest, SocialSignUpCompleteRequest, TermAgreementItem
from .terms_catalog import CATALOG_BY_TYPE, REQUIRED_TYPES, TERMS_CATALOG
from .verification_service import VerificationService

logger = logging.getLogger(__name__)

LOCKOUT = LockoutPolicy(max_attempts=config.MAX_LOGIN_ATTEMPTS, duration=config.LOCKOUT_DURATION)


@dataclass(frozen=True)
class Tokens:
    access_token: str
    refresh_token: str
    refresh_expires_at: datetime


@dataclass(frozen=True)
class AuthResult:
    user: User
    tokens: Tokens
    is_new_user: bool = False


@dataclass(frozen=True)
class SocialProfile:
    """공급자에서 받아온 사용자 정보. ID token 검증이든 code 교환이든 이 형태로 맞춰서 넘긴다."""

    provider: AuthProvider
    provider_uid: str
    email: str | None = None
    name: str | None = None


@dataclass(frozen=True)
class SocialAuthResult:
    is_new_user: bool
    signup_token: str | None = None
    result: AuthResult | None = None


class AuthService:
    """가입/로그인/소셜/탈퇴 본체. 중복확인·이메일/휴대폰 인증은 서로만 부르고 여기서는
    사전조건 체크로만 쓰이므로 `VerificationService`로 뗐다 - 위임 메서드만 남긴다."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.verification = VerificationService(session)

    # 라우터/테스트가 기존과 같은 방식(AuthService 인스턴스)으로 부를 수 있도록 위임한다.
    async def is_email_taken(self, email: str) -> bool:
        return await self.verification.is_email_taken(email)

    async def is_nickname_taken(self, nickname: str) -> bool:
        return await self.verification.is_nickname_taken(nickname)

    async def is_phone_taken(self, phone_number: str) -> bool:
        return await self.verification.is_phone_taken(phone_number)

    async def request_email_verification(self, email: str) -> tuple[str, bool]:
        return await self.verification.request_email_verification(email)

    async def verify_email_token(self, token: str) -> str:
        return await self.verification.verify_email_token(token)

    async def request_phone_verification(self, phone_number: str) -> tuple[str, bool]:
        return await self.verification.request_phone_verification(phone_number)

    async def verify_phone_code(self, phone_number: str, code: str) -> None:
        await self.verification.verify_phone_code(phone_number, code)

    # ══════════════════════════════════════════════════════════════════════
    # 제재 이력 (REQ-F-ACC-11)
    # ══════════════════════════════════════════════════════════════════════
    async def _assert_not_sanctioned(self, phone_number: str) -> None:
        phone_hash = security.hash_phone(validators.normalize_phone_number(phone_number))
        blocked = await self.session.scalar(
            select(SanctionedIdentity.id).where(SanctionedIdentity.phone_hash == phone_hash).limit(1)
        )
        if blocked is not None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "이용 제한 이력이 있어 가입할 수 없습니다.")

    async def record_sanction(self, user_id: int, reason: str) -> None:
        """신고 확정 등으로 이용을 제한할 때 운영자(ADM) 도메인이 호출한다. 탈퇴(물리삭제)
        시점에 `_seal_sanction_if_needed`가 phone_hash를 영구 보존 테이블로 옮긴다."""
        user = await self.session.get(User, user_id)
        if user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "존재하지 않는 계정입니다.")
        user.is_sanctioned = True
        user.sanction_reason = reason
        await self.session.commit()

    async def _seal_sanction_if_needed(self, user: User) -> None:
        """탈퇴(물리삭제) 직전에만 호출한다 - 제재된 계정이면 phone_hash를 남겨 재가입을 막는다."""
        if not user.is_sanctioned or not user.phone_hash:
            return
        self.session.add(SanctionedIdentity(phone_hash=user.phone_hash, reason=user.sanction_reason or "제재 확정"))

    # ══════════════════════════════════════════════════════════════════════
    # 약관 동의
    # ══════════════════════════════════════════════════════════════════════
    def _validate_agreements(self, items: list[TermAgreementItem]) -> dict[str, TermAgreementItem]:
        """카탈로그 기준 검증. 같은 종류가 여러 번 오면 마지막 값을 쓴다.

        - 카탈로그에 없는 종류      → 400 (앱 변조 또는 오타)
        - 버전이 현재와 다름        → 409 (화면이 구버전. 최신 문안 재동의로 유도)
        - 필수인데 누락/false       → 400
        """
        submitted = {item.terms_type: item for item in items}

        unknown = sorted(t for t in submitted if t not in CATALOG_BY_TYPE)
        if unknown:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"존재하지 않는 약관입니다: {', '.join(unknown)}")

        stale = sorted(t for t, item in submitted.items() if item.version != CATALOG_BY_TYPE[t].version)
        if stale:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "약관이 변경되었습니다. 최신 약관을 확인한 뒤 다시 동의해주세요."
            )

        missing = sorted(t for t in REQUIRED_TYPES if t not in submitted or not submitted[t].agreed)
        if missing:
            titles = ", ".join(CATALOG_BY_TYPE[t].title for t in missing)
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"필수 약관에 동의해주세요: {titles}")

        return submitted

    async def _store_agreements(self, user_id: int, submitted: dict[str, TermAgreementItem]) -> None:
        """version/is_required는 클라이언트 값이 아니라 카탈로그 값으로 저장한다."""
        existing = {
            row.terms_type: row
            for row in (
                await self.session.scalars(select(TermsAgreement).where(TermsAgreement.user_id == user_id))
            ).all()
        }
        now = _now()
        for terms_type, item in submitted.items():
            spec = CATALOG_BY_TYPE[terms_type]
            row = existing.get(terms_type)
            if row is None:
                row = TermsAgreement(user_id=user_id, terms_type=terms_type, is_required=spec.is_required)
                self.session.add(row)
            row.version = spec.version
            row.is_required = spec.is_required
            row.agreed_at = now if item.agreed else None
            row.revoked_at = None if item.agreed else now

    async def submit_agreements(self, user: User, items: list[TermAgreementItem]) -> User:
        """가입 이후(소셜 첫 로그인, 약관 개정 시 재동의) 동의를 제출하는 경로."""
        submitted = self._validate_agreements(items)
        await self._store_agreements(user.id, submitted)
        if user.onboarding_status == OnboardingStatus.PENDING:
            user.onboarding_status = OnboardingStatus.TERMS_AGREED
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def revoke_agreement(self, user: User, terms_type: str) -> None:
        """선택 항목만 철회할 수 있다. 필수 약관 철회는 곧 서비스 이용 불가라 탈퇴로 안내한다."""
        spec = CATALOG_BY_TYPE.get(terms_type)
        if spec is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "존재하지 않는 약관입니다.")
        if not spec.revocable:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "필수 약관은 철회할 수 없습니다. 서비스 이용을 중단하려면 회원탈퇴를 진행해주세요.",
            )
        await self.session.execute(
            update(TermsAgreement)
            .where(TermsAgreement.user_id == user.id, TermsAgreement.terms_type == terms_type)
            .values(revoked_at=_now())
        )
        await self.session.commit()

    async def agreement_status(self, user: User) -> list[dict[str, object]]:
        """약관 개정 시 재동의가 필요한 항목을 프론트가 알 수 있게 한다."""
        rows = {
            row.terms_type: row
            for row in (
                await self.session.scalars(select(TermsAgreement).where(TermsAgreement.user_id == user.id))
            ).all()
        }
        result: list[dict[str, object]] = []
        for spec in TERMS_CATALOG:
            row = rows.get(str(spec.terms_type))
            active = row is not None and row.is_active
            result.append(
                {
                    "terms_type": str(spec.terms_type),
                    "agreed_version": row.version if row is not None else None,
                    "current_version": spec.version,
                    "is_required": spec.is_required,
                    "agreed": active,
                    # 필수인데 미동의거나, 동의했지만 그 사이 약관이 개정된 경우
                    "needs_reagreement": spec.is_required
                    and (not active or (row is not None and row.version != spec.version)),
                }
            )
        return result

    # ══════════════════════════════════════════════════════════════════════
    # 이메일 회원가입
    # ══════════════════════════════════════════════════════════════════════
    async def signup(self, data: SignUpRequest) -> AuthResult:
        email = validators.normalize_email(str(data.email))

        if config.require_email_verification() and not await self.verification.is_email_verified(email):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "이메일 인증이 완료되지 않았습니다.")
        if config.require_phone_verification() and not await self.verification.is_phone_verified(data.phone_number):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "휴대폰 본인확인이 완료되지 않았습니다.")

        await self.verification.assert_unique(email, data.nickname, data.phone_number)
        await self._assert_not_sanctioned(data.phone_number)
        submitted = self._validate_agreements(data.agreements)

        phone = validators.normalize_phone_number(data.phone_number)
        user = User(
            email=email,
            password_hash=security.hash_password(data.password),
            name=data.name,
            nickname=data.nickname,
            phone_number=phone,
            phone_hash=security.hash_phone(phone),
            birth_date=data.birth_date,
            gender=data.gender,
            email_verified=True,
            phone_verified=True,
            # 약관·기본정보를 가입에서 다 받았으니 남은 건 아동/보호자 프로필뿐이다.
            onboarding_status=OnboardingStatus.PROFILE_REQUIRED,
        )
        self.session.add(user)
        try:
            await self.session.flush()  # user.id 확보 + 유니크 제약 위반을 여기서 잡는다
        except IntegrityError as e:
            await self.session.rollback()
            # onBlur 확인과 가입 사이에 같은 값으로 다른 사람이 먼저 가입한 경쟁 조건.
            raise HTTPException(status.HTTP_409_CONFLICT, "이미 사용중인 정보가 있습니다. 다시 확인해주세요.") from e

        await self._store_agreements(user.id, submitted)
        tokens = await self._issue_tokens(user)
        await self.session.commit()
        await self.session.refresh(user)
        return AuthResult(user=user, tokens=tokens, is_new_user=True)

    # ══════════════════════════════════════════════════════════════════════
    # 로그인 / 잠금
    # ══════════════════════════════════════════════════════════════════════
    async def authenticate(self, email: str, password: str) -> User:
        normalized = validators.normalize_email(email)
        user = await self.session.scalar(select(User).where(User.email == normalized))

        # 계정 없음과 비밀번호 틀림을 같은 메시지로 준다 - 구분해서 알려주면 어느 이메일이
        # 가입돼 있는지 확인하는 열거 공격이 가능해진다. 구분은 서버 로그에만 남긴다.
        invalid = HTTPException(status.HTTP_400_BAD_REQUEST, "이메일 또는 비밀번호가 올바르지 않습니다.")
        if user is None:
            logger.info("login failed: no account for given email")
            raise invalid

        if user.deactivated_at is not None:
            raise HTTPException(status.HTTP_423_LOCKED, "탈퇴 처리 중인 계정입니다. 고객센터로 문의해주세요.")

        # 잠금 판정/카운터 갱신 규칙은 security_kit.guards.LockoutPolicy가 단독으로 들고 있다
        # (자동 해제 후 카운터 리셋 같은 미묘한 규칙을 여기에 다시 쓰지 않는다).
        if LOCKOUT.is_locked(user.locked_until):
            raise HTTPException(
                status.HTTP_423_LOCKED,
                f"로그인 시도 횟수를 초과해 계정이 잠겼습니다. "
                f"{LOCKOUT.remaining_minutes(user.locked_until)}분 후 다시 시도해주세요.",
            )

        if user.password_hash is None or not security.verify_password(password, user.password_hash):
            state = LOCKOUT.on_failure(user.failed_login_attempts, user.locked_until)
            user.failed_login_attempts = state.failed_attempts
            user.locked_until = state.locked_until
            if state.just_locked:
                logger.info("account locked: user_id=%s", user.id)
            await self.session.commit()
            raise invalid

        if not user.is_active:
            raise HTTPException(status.HTTP_423_LOCKED, "비활성화된 계정입니다.")

        if user.failed_login_attempts or user.locked_until is not None:
            state = LOCKOUT.on_success()
            user.failed_login_attempts = state.failed_attempts
            user.locked_until = state.locked_until

        # 해시 파라미터를 올린 뒤 처음 로그인하는 사용자를 조용히 재해시한다.
        if security.needs_rehash(user.password_hash):
            user.password_hash = security.hash_password(password)

        return user

    async def login(self, email: str, password: str) -> AuthResult:
        user = await self.authenticate(email, password)
        tokens = await self._issue_tokens(user)
        await self.session.commit()
        return AuthResult(user=user, tokens=tokens)

    async def _issue_tokens(self, user: User) -> Tokens:
        user.last_login_at = _now()
        access = security.create_access_token(user.id)
        refresh, jti, expires_at = security.create_refresh_token(user.id)
        self.session.add(RefreshToken(user_id=user.id, jti=jti, expires_at=expires_at))
        return Tokens(access_token=access, refresh_token=refresh, refresh_expires_at=expires_at)

    # ══════════════════════════════════════════════════════════════════════
    # 토큰 로테이션 / 로그아웃
    # ══════════════════════════════════════════════════════════════════════
    async def rotate_refresh_token(self, raw_token: str) -> Tokens:
        """갱신할 때마다 refresh token을 새 값으로 바꾸고 방금 쓴 건 즉시 무효화한다.

        이미 무효화된 토큰이 다시 오면 = 토큰이 탈취되어 공격자와 정상 사용자가 각자
        쓰고 있다는 신호이므로, 그 계정의 모든 세션을 강제 로그아웃시킨다.
        """
        try:
            payload = security.decode(raw_token, "refresh")
        except jwt.InvalidTokenError as e:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "유효하지 않은 토큰입니다.") from e

        row = await self.session.scalar(select(RefreshToken).where(RefreshToken.jti == payload["jti"]))
        if row is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "유효하지 않은 토큰입니다.")

        if row.is_revoked:
            await self._revoke_all_for_user(row.user_id)
            await self.session.commit()
            logger.warning("refresh token reuse detected: user_id=%s", row.user_id)
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "토큰 재사용이 감지되어 모든 세션이 로그아웃되었습니다. 다시 로그인해주세요.",
            )

        user = await self.session.get(User, row.user_id)
        if user is None or not user.is_active or user.deactivated_at is not None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "사용할 수 없는 계정입니다.")

        row.revoked_at = _now()
        tokens = await self._issue_tokens(user)
        await self.session.commit()
        return tokens

    async def logout(self, raw_token: str | None) -> None:
        """로그아웃은 사용자 입장에서 항상 성공해야 한다 - 토큰이 이미 만료/위조됐어도 조용히 넘긴다."""
        if not raw_token:
            return
        try:
            payload = security.decode(raw_token, "refresh")
        except jwt.InvalidTokenError:
            return
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.jti == payload["jti"], RefreshToken.revoked_at.is_(None))
            .values(revoked_at=_now())
        )
        await self.session.commit()

    async def _revoke_all_for_user(self, user_id: int) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=_now())
        )

    # ══════════════════════════════════════════════════════════════════════
    # 소셜 로그인/가입
    # ══════════════════════════════════════════════════════════════════════
    async def consume_nonce(self, provider: AuthProvider, nonce: str) -> None:
        """검증에 성공한 nonce를 한 번만 쓰이게 소비한다. PK 충돌 = 같은 ID token 재사용."""
        self.session.add(OAuthNonce(nonce_hash=security.hash_token(nonce), provider=str(provider)))
        try:
            await self.session.flush()
        except IntegrityError as e:
            await self.session.rollback()
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "이미 사용된 로그인 요청입니다.") from e

    async def social_login(self, profile: SocialProfile) -> SocialAuthResult:
        """기존 연결이 있으면 로그인, 없으면 signup_token만 발급하고 계정은 만들지 않는다.

        여기서 곧바로 계정을 만들지 않는 이유: 공급자는 이메일/이름만 주고 생년월일과
        약관 동의는 주지 않는다. 그대로 만들면 만14세 확인과 필수 동의를 건너뛴 계정이 생긴다.
        """
        account = await self.session.scalar(
            select(SocialAccount).where(
                SocialAccount.provider == profile.provider, SocialAccount.provider_uid == profile.provider_uid
            )
        )
        if account is not None:
            user = await self.session.get(User, account.user_id)
            if user is None:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "사용할 수 없는 계정입니다.")
            if user.deactivated_at is not None:
                raise HTTPException(status.HTTP_423_LOCKED, "탈퇴 처리 중인 계정입니다.")
            if not user.is_active:
                raise HTTPException(status.HTTP_423_LOCKED, "비활성화된 계정입니다.")
            tokens = await self._issue_tokens(user)
            await self.session.commit()
            return SocialAuthResult(is_new_user=False, result=AuthResult(user=user, tokens=tokens))

        # 같은 이메일이 이미 다른 방식으로 가입돼 있으면 자동 연결하지 않고 막는다.
        # 자동 연결은 공급자가 이메일 소유를 검증했다는 보장이 있어야 안전하다(미검증 이메일을
        # 주는 공급자가 있으면 남의 계정을 탈취하는 경로가 된다).
        if profile.email and await self.is_email_taken(profile.email):
            raise HTTPException(
                status.HTTP_409_CONFLICT, "이미 이 이메일로 가입된 계정이 있습니다. 이메일로 로그인해주세요."
            )

        signup_token = security.create_social_signup_token(
            str(profile.provider), profile.provider_uid, profile.email, profile.name
        )
        return SocialAuthResult(is_new_user=True, signup_token=signup_token)

    async def complete_social_signup(self, data: SocialSignUpCompleteRequest) -> AuthResult:
        try:
            payload = security.decode(data.signup_token, "social_signup")
        except jwt.InvalidTokenError as e:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "가입 세션이 만료되었습니다. 다시 로그인해주세요.") from e

        provider = AuthProvider(payload["provider"])
        provider_uid = payload["provider_uid"]
        email = validators.normalize_email(payload["email"]) if payload.get("email") else None

        if config.require_phone_verification() and not await self.verification.is_phone_verified(data.phone_number):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "휴대폰 본인확인이 완료되지 않았습니다.")

        await self.verification.assert_unique(email, data.nickname, data.phone_number)
        await self._assert_not_sanctioned(data.phone_number)
        submitted = self._validate_agreements(data.agreements)

        phone = validators.normalize_phone_number(data.phone_number)
        user = User(
            email=email,
            password_hash=None,  # 소셜 계정은 비밀번호가 없다
            name=data.name or payload.get("name"),
            nickname=data.nickname,
            phone_number=phone,
            phone_hash=security.hash_phone(phone),
            birth_date=data.birth_date,
            gender=data.gender,
            email_verified=bool(email),  # 공급자가 검증한 이메일
            phone_verified=True,
            onboarding_status=OnboardingStatus.PROFILE_REQUIRED,
        )
        self.session.add(user)
        try:
            await self.session.flush()
            self.session.add(SocialAccount(user_id=user.id, provider=provider, provider_uid=provider_uid))
            await self.session.flush()
        except IntegrityError as e:
            await self.session.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "이미 가입된 계정입니다. 로그인해주세요.") from e

        await self._store_agreements(user.id, submitted)
        tokens = await self._issue_tokens(user)
        await self.session.commit()
        await self.session.refresh(user)
        return AuthResult(user=user, tokens=tokens, is_new_user=True)

    async def link_social_account(self, user: User, profile: SocialProfile) -> None:
        """이미 로그인한 사용자가 소셜 계정을 추가로 연결한다(비밀번호 분실 대비 등)."""
        self.session.add(SocialAccount(user_id=user.id, provider=profile.provider, provider_uid=profile.provider_uid))
        try:
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "이미 다른 계정에 연결된 소셜 계정입니다.") from e

    # ══════════════════════════════════════════════════════════════════════
    # 게스트(체험하기)
    # ══════════════════════════════════════════════════════════════════════
    async def guest_login(self) -> AuthResult:
        """개인정보를 하나도 받지 않고 임시 계정을 만든다. 매 호출마다 새 계정이다.

        게스트는 약관 동의가 없으므로 건강정보 저장 같은 민감 기능은 막아야 한다 -
        is_guest 플래그로 판정하고, 정식 가입 전환은 link_social_account 또는 별도
        전환 API에서 다룬다(이 모듈 범위 밖).
        """
        for _ in range(5):  # 닉네임 랜덤 충돌 재시도
            user = User(nickname=security.random_nickname(), is_guest=True, onboarding_status=OnboardingStatus.PENDING)
            self.session.add(user)
            try:
                await self.session.flush()
                break
            except IntegrityError:
                await self.session.rollback()
        else:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "게스트 계정 생성에 실패했습니다.")

        tokens = await self._issue_tokens(user)
        await self.session.commit()
        await self.session.refresh(user)
        return AuthResult(user=user, tokens=tokens, is_new_user=True)

    # ══════════════════════════════════════════════════════════════════════
    # 아이디 찾기 / 비밀번호 재설정
    # ══════════════════════════════════════════════════════════════════════
    async def find_email(self, name: str, nickname: str) -> str:
        """이름은 암호화 컬럼이라 WHERE로 못 찾는다 - 유니크한 닉네임으로 찾고 이름을 대조한다."""
        user = await self.session.scalar(select(User).where(User.nickname == nickname))
        if user is None or user.name != name or user.email is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "일치하는 회원 정보를 찾을 수 없습니다.")
        return validators.mask_email(user.email)

    async def create_password_reset_token(self, email: str) -> tuple[str | None, str]:
        """(토큰, 안내메시지). 가입 안 된 이메일이어도 404를 주지 않는다 - 404를 주면
        어느 이메일이 가입돼 있는지 확인하는 열거 공격이 된다. 토큰이 None이면 발송하지 않는다."""
        normalized = validators.normalize_email(email)
        user = await self.session.scalar(select(User).where(User.email == normalized))
        message = "가입된 이메일이라면 재설정 링크를 보냈습니다. 메일함을 확인해주세요."
        if user is None or user.password_hash is None or user.deactivated_at is not None:
            logger.info("password reset requested for non-resettable account")
            return None, message
        return security.create_password_reset_token(user.id), message

    async def reset_password(self, token: str, new_password: str) -> None:
        try:
            payload = security.decode(token, "password_reset")
        except jwt.InvalidTokenError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "재설정 링크가 만료되었거나 유효하지 않습니다.") from e

        user = await self.session.get(User, int(payload["sub"]))
        if user is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "유효하지 않은 재설정 링크입니다.")

        user.password_hash = security.hash_password(new_password)
        # 비밀번호를 바꾸면 잠금을 풀고, 기존 세션을 전부 끊는다(탈취 대응이 재설정의 목적).
        user.failed_login_attempts = 0
        user.locked_until = None
        await self._revoke_all_for_user(user.id)
        await self.session.commit()

    # ══════════════════════════════════════════════════════════════════════
    # 회원탈퇴
    # ══════════════════════════════════════════════════════════════════════
    async def withdraw(self, user: User, password: str | None) -> None:
        """유예기간을 두고 비활성화한다. WITHDRAWAL_GRACE가 0이면 즉시 완전 삭제.

        비밀번호 재확인을 요구하는 이유: 탈취된 access token만으로 탈퇴가 되면 안 된다.
        단, 소셜/게스트 계정은 비밀번호가 애초에 없으므로 재확인을 요구하면 탈퇴 자체가
        불가능해진다 - 그 경우는 유효한 토큰만으로 허용한다.
        """
        if user.password_hash is not None:
            if password is None or not security.verify_password(password, user.password_hash):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "비밀번호가 올바르지 않습니다.")

        await self._revoke_all_for_user(user.id)
        if config.WITHDRAWAL_GRACE <= timedelta(0):
            await self._seal_sanction_if_needed(user)
            await self.session.delete(user)
        else:
            user.deactivated_at = _now()
            user.purge_at = _now() + config.WITHDRAWAL_GRACE
            user.is_active = False
        await self.session.commit()

    async def cancel_withdrawal(self, email: str, password: str) -> AuthResult:
        """탈퇴 신청 후에는 로그인이 막히므로, 로그인과 같은 방식으로 본인 확인만 다시 한다."""
        normalized = validators.normalize_email(email)
        user = await self.session.scalar(select(User).where(User.email == normalized))
        if user is None or user.password_hash is None or not security.verify_password(password, user.password_hash):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "이메일 또는 비밀번호가 올바르지 않습니다.")
        if user.deactivated_at is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "탈퇴 신청 상태가 아닙니다.")

        user.deactivated_at = None
        user.purge_at = None
        user.is_active = True
        tokens = await self._issue_tokens(user)
        await self.session.commit()
        return AuthResult(user=user, tokens=tokens)

    async def purge_deactivated(self) -> int:
        """유예기간이 지난 탈퇴 계정을 물리 삭제한다. 스케줄러(하루 1회)에서 호출한다.

        일괄 DELETE가 아니라 한 행씩 삭제하는 이유: 제재된 계정(`is_sanctioned`)이면 삭제
        직전에 phone_hash를 `SanctionedIdentity`로 옮겨야 한다(REQ-F-ACC-11). 통계를 남겨야
        하면 여기서 삭제 전에 식별정보 없는 형태로(나이대·성별 등) 따로 적재한다 - 개인정보
        보호법 제28조의2(가명정보 통계작성) 범위 안에서만.
        """
        rows = (
            await self.session.scalars(select(User).where(User.purge_at.is_not(None), User.purge_at <= _now()))
        ).all()
        for user in rows:
            await self._seal_sanction_if_needed(user)
            await self.session.delete(user)
        await self.session.commit()
        return len(rows)

    async def purge_expired_tokens(self) -> None:
        """만료된 refresh/이메일 인증 토큰 정리. 스케줄러에서 같이 돌린다."""
        now = _now()
        await self.session.execute(delete(RefreshToken).where(RefreshToken.expires_at <= now))
        await self.session.execute(delete(EmailVerificationToken).where(EmailVerificationToken.expires_at <= now))
        await self.session.execute(delete(OAuthNonce).where(OAuthNonce.created_at <= now - timedelta(days=1)))
        await self.session.commit()

    # ══════════════════════════════════════════════════════════════════════
    # 온보딩 상태
    # ══════════════════════════════════════════════════════════════════════
    async def advance_onboarding(self, user: User, to: OnboardingStatus) -> User:
        user.onboarding_status = to
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get_user_by_access_token(self, token: str) -> User:
        """라우터 의존성에서 쓴다. 잠금/탈퇴/비활성 계정은 토큰이 유효해도 거부한다."""
        try:
            payload = security.decode(token, "access")
        except jwt.InvalidTokenError as e:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "유효하지 않은 토큰입니다.") from e

        user = await self.session.get(User, int(payload["sub"]))
        if user is None or not user.is_active or user.deactivated_at is not None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "사용할 수 없는 계정입니다.")
        return user


__all__ = ["AuthService", "AuthResult", "SocialAuthResult", "SocialProfile", "Tokens", "Gender"]
