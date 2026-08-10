"""SQLAlchemy 2.0 모델. 회원가입/인증에 필요한 테이블만.

설계 요점:
- 계정(User)에 이름/전화번호 같은 개인정보를 같이 두되, 유출 피해가 큰 값은 EncryptedStr로
  암호화한다. 계정과 개인정보를 아예 다른 테이블로 쪼개는 방식(User/Profile 분리)도 있지만,
  가족 대리 프로필처럼 "한 계정에 여러 사람"이 필요할 때만 값을 한다 - 필요해지면 그때 쪼갠다.
- 소셜 계정은 User 컬럼(sns_provider/sns_id)이 아니라 SocialAccount 테이블로 뺀다.
  컬럼으로 두면 한 사용자가 구글+카카오를 동시에 연결하는 걸 나중에 못 붙인다.
- 동의는 boolean 컬럼이 아니라 TermsAgreement 행으로 남긴다. 무엇에, 어느 버전에, 언제
  동의했는지가 남아야 법적 근거가 된다(boolean만으로는 약관 개정 이력을 못 증명한다).
"""

from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base  # 프로젝트 전역 단일 metadata(User/Profile/도메인테이블 공유)

from .security import EncryptedStr


class Gender(StrEnum):
    MALE = "M"
    FEMALE = "F"


class AuthProvider(StrEnum):
    LOCAL = "local"  # 이메일+비밀번호
    GOOGLE = "google"
    KAKAO = "kakao"
    NAVER = "naver"
    APPLE = "apple"


class OnboardingStatus(StrEnum):
    """가입 이후 남은 단계를 서버가 들고 있게 한다.

    프론트가 localStorage로 관리하면 기기를 바꾸거나 캐시를 지우면 단계가 초기화되고,
    "동의했는지"의 근거가 클라이언트에만 남는 문제가 생긴다. 라우트 가드는 로그인 응답의
    이 값만 보고 어디로 보낼지 결정한다.
    """

    PENDING = "pending"  # 계정만 있음 (소셜/게스트 첫 로그인 직후)
    TERMS_AGREED = "terms_agreed"  # 필수 약관 동의 완료
    PROFILE_REQUIRED = "profile_required"  # 기본 정보까지 완료, 건강 프로필 입력 대기
    COMPLETED = "completed"


# SQLite는 INTEGER PRIMARY KEY만 autoincrement한다 - BIGINT로 두면 로컬/테스트에서
# "NOT NULL constraint failed: ...id"가 난다. 운영(MySQL/Postgres)에서는 BIGINT를 쓰고
# SQLite에서만 INTEGER로 내려가게 변형(variant)을 걸어둔다.
_PK = BigInteger().with_variant(Integer, "sqlite")


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    return [e.value for e in enum_cls]


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)

    # 소셜 전용/게스트 계정은 이메일이 없을 수 있어 nullable. 길이는 RFC 5321 상한(254)에 맞춘다
    # (40자로 잡아두면 실제로 존재하는 긴 회사 이메일이 가입 자체를 못 한다).
    email: Mapped[str | None] = mapped_column(String(254), unique=True, nullable=True)
    # 소셜/게스트 계정은 비밀번호가 없다(본인이 정한 적 없음). None이면 이메일 로그인 대상이 아니다.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    name: Mapped[str | None] = mapped_column(EncryptedStr, nullable=True)
    nickname: Mapped[str] = mapped_column(String(12), unique=True, nullable=False)
    phone_number: Mapped[str | None] = mapped_column(EncryptedStr, nullable=True)
    # 암호화된 phone_number로는 WHERE 검색이 안 되므로 조회/중복확인은 이 해시로 한다.
    phone_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[Gender | None] = mapped_column(
        Enum(Gender, values_callable=_enum_values, name="gender_enum"), nullable=True
    )

    onboarding_status: Mapped[OnboardingStatus] = mapped_column(
        Enum(OnboardingStatus, values_callable=_enum_values, name="onboarding_status_enum"),
        nullable=False,
        default=OnboardingStatus.PENDING,
    )
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # REQ-F-ACC-01. 소셜/게스트 계정은 공급자가 본인확인을 대신하지 않으므로 이 값이 False로 남는다
    # - 그 상태에서 아동 등록 등 민감 기능을 열어주지 않는 것은 서비스 정책(§CAR/ACC) 몫이다.
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # REQ-F-ACC-11. 신고 확정 등으로 이용제한이 걸린 계정 - 운영자(ADM) 도메인이
    # AuthService.record_sanction()으로 세운다. 탈퇴 시 이 값이 True면 개인정보 파기와
    # 별개로 phone_hash를 SanctionedIdentity에 남겨 재가입을 막는다.
    is_sanctioned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sanction_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 체험하기(게스트) 계정. 개인정보를 하나도 안 받고 만들어지므로 정식 가입 전환 전까지
    # 알림 발송·통계 집계 대상에서 빼야 한다.
    is_guest: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 브루트포스 방어. 로그인 성공 시 둘 다 초기화한다.
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 탈퇴 신청 시각. 채워지면 로그인이 막히고, purge_at이 지나면 물리 삭제된다.
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purge_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    social_accounts: Mapped[list["SocialAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    agreements: Mapped[list["TermsAgreement"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )


class SocialAccount(Base):
    __tablename__ = "social_accounts"
    # 같은 provider의 같은 계정이 두 사용자에게 연결되면 로그인이 누구 계정인지 모호해진다.
    __table_args__ = (UniqueConstraint("provider", "provider_uid", name="uq_social_provider_uid"),)

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[AuthProvider] = mapped_column(
        Enum(AuthProvider, values_callable=_enum_values, name="auth_provider_enum"), nullable=False
    )
    provider_uid: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates="social_accounts")


class TermsAgreement(Base):
    """사용자별 동의 결과. version/is_required는 클라이언트가 보낸 값이 아니라
    서버 카탈로그 값으로 저장한다(클라이언트 값을 믿으면 동의 기록을 위조할 수 있다)."""

    __tablename__ = "terms_agreements"
    __table_args__ = (UniqueConstraint("user_id", "terms_type", name="uq_agreement_user_type"),)

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    terms_type: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    agreed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 선택 항목(revocable)을 껐을 때의 시각. agreed_at이 있고 revoked_at이 없으면 "현재 동의 중".
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="agreements")

    @property
    def is_active(self) -> bool:
        return self.agreed_at is not None and self.revoked_at is None


class RefreshToken(Base):
    """발급한 refresh token의 jti만 추적한다(토큰 원문은 저장하지 않는다).
    로테이션과 재사용 탐지를 하려면 "이 jti가 이미 쓰였는지"를 알아야 한다."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    jti: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None


class EmailVerificationToken(Base):
    """가입 전 이메일 인증. user_id가 아니라 email로 묶인다 - 계정이 아직 없는 상태이므로."""

    __tablename__ = "email_verification_tokens"
    __table_args__ = (Index("ix_email_verification_email_verified", "email", "verified_at"),)

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PhoneVerificationToken(Base):
    """가입 전 휴대폰 본인확인(REQ-F-ACC-01). user_id가 아니라 phone_hash로 묶인다 - 계정이
    아직 없는 상태이므로. 코드 원문은 저장하지 않는다(email 인증과 동일하게 hash_token)."""

    __tablename__ = "phone_verification_tokens"
    __table_args__ = (Index("ix_phone_verification_hash_verified", "phone_hash", "verified_at"),)

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    phone_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SanctionedIdentity(Base):
    """REQ-F-ACC-11. 제재 확정 후 탈퇴한 계정의 본인확인값(phone_hash)만 단방향으로 보존한다.
    개인정보(이름·전화번호 원문)는 탈퇴 시 이미 파기된 뒤이므로 재가입 차단에만 쓰인다."""

    __tablename__ = "sanctioned_identities"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    phone_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OAuthNonce(Base):
    """성공적으로 검증된 소셜 ID token의 nonce. PK 충돌 = 같은 토큰 재사용(재생 공격)."""

    __tablename__ = "oauth_nonces"

    nonce_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
