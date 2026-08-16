"""가입 전 확인: 중복확인 + 이메일 인증 + 휴대폰 본인확인(REQ-F-ACC-01).

AuthService의 나머지(가입/로그인/소셜/탈퇴)와 달리 여기 메서드들은 서로만 부르고
바깥에서는 signup류의 사전조건 체크로만 쓰인다 - 그래서 따로 뗄 수 있다.
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import config, security, validators
from ._time import aware as _aware
from ._time import now as _now
from .models import EmailVerificationToken, PhoneVerificationToken, User


class VerificationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ══════════════════════════════════════════════════════════════════════
    # 중복확인 (가입 화면 onBlur + 가입 시 서버 최종 검사, 같은 규칙을 공유)
    # ══════════════════════════════════════════════════════════════════════
    async def is_email_taken(self, email: str) -> bool:
        normalized = validators.normalize_email(email)
        return await self.session.scalar(select(User.id).where(User.email == normalized).limit(1)) is not None

    async def is_nickname_taken(self, nickname: str) -> bool:
        return await self.session.scalar(select(User.id).where(User.nickname == nickname).limit(1)) is not None

    async def is_phone_taken(self, phone_number: str) -> bool:
        normalized = validators.normalize_phone_number(phone_number)
        phone_hash = security.hash_phone(normalized)
        return await self.session.scalar(select(User.id).where(User.phone_hash == phone_hash).limit(1)) is not None

    async def assert_unique(self, email: str | None, nickname: str, phone_number: str | None) -> None:
        """가입 직전 최종 검사. onBlur 확인과 실제 가입 사이의 시간차로 중복이 생길 수 있으므로
        프론트 확인만 믿으면 안 된다(그래도 경쟁 조건은 남으니 DB 유니크 제약이 최종 방어선)."""
        if email and await self.is_email_taken(email):
            raise HTTPException(status.HTTP_409_CONFLICT, "이미 사용중인 이메일입니다.")
        if await self.is_nickname_taken(nickname):
            raise HTTPException(status.HTTP_409_CONFLICT, "이미 사용중인 닉네임입니다.")
        if phone_number and await self.is_phone_taken(phone_number):
            raise HTTPException(status.HTTP_409_CONFLICT, "이미 사용중인 휴대폰 번호입니다.")

    # ══════════════════════════════════════════════════════════════════════
    # 이메일 인증 (가입 전제조건)
    # ══════════════════════════════════════════════════════════════════════
    async def request_email_verification(self, email: str) -> tuple[str, bool]:
        """(원문 토큰, 발송 성공 여부). 메일 발송은 이 모듈이 하지 않는다 - 토큰만 만들어
        돌려주고, 실제 발송은 프로젝트의 메일러가 라우터에서 처리한다(SMTP/SES/외부 API가
        프로젝트마다 달라서, 여기에 묶으면 그 의존성이 이 모듈에 따라붙는다)."""
        normalized = validators.normalize_email(email)
        if await self.is_email_taken(normalized):
            raise HTTPException(status.HTTP_409_CONFLICT, "이미 사용중인 이메일입니다.")

        token = security.new_url_token()
        self.session.add(
            EmailVerificationToken(
                email=normalized,
                token_hash=security.hash_token(token),
                expires_at=_now() + config.EMAIL_VERIFICATION_TTL,
            )
        )
        await self.session.commit()
        return token, True

    async def verify_email_token(self, token: str) -> str:
        """인증 링크 클릭 처리. 성공하면 해당 이메일이 signup을 통과할 수 있게 된다."""
        row = await self.session.scalar(
            select(EmailVerificationToken).where(EmailVerificationToken.token_hash == security.hash_token(token))
        )
        if row is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "유효하지 않은 인증 링크입니다.")
        if row.verified_at is not None:
            return row.email  # 같은 링크를 두 번 눌러도 에러가 아니다(메일 클라이언트 프리페치 등)
        if _aware(row.expires_at) < _now():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "인증 링크가 만료되었습니다. 다시 요청해주세요.")

        row.verified_at = _now()
        await self.session.commit()
        return row.email

    async def is_email_verified(self, email: str) -> bool:
        return (
            await self.session.scalar(
                select(EmailVerificationToken.id)
                .where(EmailVerificationToken.email == email, EmailVerificationToken.verified_at.is_not(None))
                .limit(1)
            )
            is not None
        )

    # ══════════════════════════════════════════════════════════════════════
    # 휴대폰 본인확인 (REQ-F-ACC-01, 가입 전제조건)
    # ══════════════════════════════════════════════════════════════════════
    async def request_phone_verification(self, phone_number: str) -> tuple[str, bool]:
        """(원문 OTP 코드, 발송 성공 여부). SMS 발송은 이 모듈이 하지 않는다 - 이메일 인증과
        같은 이유로 코드만 만들어 돌려주고, 실제 발송은 프로젝트의 SMS 게이트웨이가 라우터에서
        처리한다."""
        normalized = validators.normalize_phone_number(phone_number)
        if await self.is_phone_taken(normalized):
            raise HTTPException(status.HTTP_409_CONFLICT, "이미 사용중인 휴대폰 번호입니다.")

        code = security.new_otp_code()
        self.session.add(
            PhoneVerificationToken(
                phone_hash=security.hash_phone(normalized),
                code_hash=security.hash_token(code),
                expires_at=_now() + config.PHONE_VERIFICATION_TTL,
            )
        )
        await self.session.commit()
        return code, True

    async def verify_phone_code(self, phone_number: str, code: str) -> None:
        """OTP 검증. 5회 틀리면 그 코드는 재전송 전까지 다시 쓸 수 없다(무차별 대입 방어)."""
        phone_hash = security.hash_phone(validators.normalize_phone_number(phone_number))
        row = await self.session.scalar(
            select(PhoneVerificationToken)
            .where(PhoneVerificationToken.phone_hash == phone_hash, PhoneVerificationToken.verified_at.is_(None))
            .order_by(PhoneVerificationToken.id.desc())
            .limit(1)
        )
        if row is None or _aware(row.expires_at) < _now():
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "인증 코드가 만료되었거나 존재하지 않습니다. 다시 요청해주세요."
            )
        if row.attempts >= 5:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "시도 횟수를 초과했습니다. 인증을 다시 요청해주세요.")
        if row.code_hash != security.hash_token(code):
            row.attempts += 1
            await self.session.commit()
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "인증 코드가 올바르지 않습니다.")

        row.verified_at = _now()
        await self.session.commit()

    async def is_phone_verified(self, phone_number: str) -> bool:
        phone_hash = security.hash_phone(validators.normalize_phone_number(phone_number))
        return (
            await self.session.scalar(
                select(PhoneVerificationToken.id)
                .where(
                    PhoneVerificationToken.phone_hash == phone_hash,
                    PhoneVerificationToken.verified_at.is_not(None),
                )
                .limit(1)
            )
            is not None
        )
