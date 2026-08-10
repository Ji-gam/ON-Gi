"""자체 검증. `python -m auth_kit.test_auth_kit` 또는 `pytest auth_kit/test_auth_kit.py`.

프레임워크 없이 assert만 쓴다. 여기서 검증하는 것은 "틀리면 실제로 사고가 나는" 로직만:
비밀번호 정책, 만14세 게이트, 약관 카탈로그 검증(400/409), 중복 409, 로그인 잠금,
refresh token 로테이션과 재사용 탐지.
"""

import asyncio
import os
from datetime import date, timedelta

# 환경변수는 auth_kit을 import하기 전에 세팅해야 config 모듈이 읽는다.
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-production-needs-32-bytes-minimum")
os.environ.setdefault("PII_HASH_KEY", "test-phone-hash-key")
os.environ.setdefault("REQUIRE_EMAIL_VERIFICATION", "true")
os.environ.setdefault("REQUIRE_PHONE_VERIFICATION", "true")
os.environ.setdefault("COOKIE_SECURE", "false")
try:
    from cryptography.fernet import Fernet

    os.environ.setdefault("PII_ENCRYPTION_KEY", Fernet.generate_key().decode())
except ImportError:  # pragma: no cover - EncryptedStr 컬럼을 쓰는 테스트만 건너뛴다
    pass

from fastapi import HTTPException  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from . import config, security, validators  # noqa: E402
from .models import Base, Gender, OnboardingStatus  # noqa: E402
from .schemas import SignUpRequest, TermAgreementItem  # noqa: E402
from .service import AuthService  # noqa: E402
from .terms_catalog import TERMS_CATALOG  # noqa: E402

GOOD_PASSWORD = "Password123!"


def _agreements(*, marketing: bool = True, stale: bool = False, drop_required: bool = False):
    items = []
    for spec in TERMS_CATALOG:
        if drop_required and spec.is_required and str(spec.terms_type) != "service":
            continue
        items.append(
            TermAgreementItem(
                terms_type=str(spec.terms_type),
                version="0.9" if stale else spec.version,
                agreed=marketing if not spec.is_required else True,
            )
        )
    return items


def _signup_request(email="hong@example.com", nickname="길동이", phone="010-1234-5678", **kw):
    return SignUpRequest(
        email=email,
        password=kw.get("password", GOOD_PASSWORD),
        name=kw.get("name", "홍길동"),
        nickname=nickname,
        birth_date=kw.get("birth_date", date(1990, 5, 5)),
        gender=Gender.MALE,
        phone_number=phone,
        agreements=kw.get("agreements", _agreements()),
    )


# ══════════════════════════════════════════════════════════════════════════
# 순수함수 (DB 불필요)
# ══════════════════════════════════════════════════════════════════════════
def test_password_policy():
    assert validators.validate_password(GOOD_PASSWORD) == GOOD_PASSWORD
    for bad, reason in [
        ("Pass1!", "8자 미만"),
        ("password123!", "대문자 없음"),
        ("PASSWORD123!", "소문자 없음"),
        ("Passwordabc!", "숫자 없음"),
        ("Password1234", "특수문자 없음"),
    ]:
        try:
            validators.validate_password(bad)
        except ValueError:
            continue
        raise AssertionError(f"통과되면 안 되는 비밀번호: {bad!r} ({reason})")


def test_password_hash_roundtrip():
    stored = security.hash_password(GOOD_PASSWORD)
    assert security.verify_password(GOOD_PASSWORD, stored)
    assert not security.verify_password(GOOD_PASSWORD + "x", stored)
    # 같은 비밀번호라도 salt가 달라 해시가 달라야 한다(레인보우 테이블 방어).
    assert stored != security.hash_password(GOOD_PASSWORD)
    # 깨진 해시로 로그인 경로가 500이 되면 안 된다.
    assert not security.verify_password(GOOD_PASSWORD, "garbage")
    assert not security.verify_password(GOOD_PASSWORD, "")
    assert not security.needs_rehash(stored)
    assert security.needs_rehash("bcrypt$2b$12$whatever")


def test_age_gate():
    today = date.today()
    ok = today.replace(year=today.year - config.MIN_SIGNUP_AGE - 1)
    assert validators.validate_birth_date(ok) == ok
    for bad in (today, today.replace(year=today.year - config.MIN_SIGNUP_AGE + 1), today + timedelta(days=1)):
        try:
            validators.validate_birth_date(bad)
        except ValueError:
            continue
        raise AssertionError(f"통과되면 안 되는 생년월일: {bad}")


def test_normalizers():
    assert validators.normalize_email("  Test@Example.COM ") == "test@example.com"
    assert validators.normalize_phone_number("010-1234-5678") == "01012345678"
    assert validators.normalize_phone_number("+821012345678") == "01012345678"
    assert validators.sanitize_credential(" pass​word\n") == "password"
    assert validators.mask_email("hongildong@example.com").endswith("@example.com")
    assert "hongildong" not in validators.mask_email("hongildong@example.com")


def test_jwt_type_confusion():
    """refresh token을 access token 자리에 넣어 쓰지 못해야 한다."""
    import jwt as pyjwt

    refresh, _, _ = security.create_refresh_token(1)
    try:
        security.decode(refresh, "access")
    except pyjwt.InvalidTokenError:
        return
    raise AssertionError("refresh token이 access token으로 통과되었다")


# ══════════════════════════════════════════════════════════════════════════
# 서비스 (in-memory SQLite)
# ══════════════════════════════════════════════════════════════════════════
_ENGINES = []


async def _session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    _ENGINES.append(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


async def _dispose_engines():
    """엔진을 정리하지 않으면 이벤트 루프 종료 후 GC가 커넥션을 닫으려다
    'greenlet is being finalized' 잡음을 대량으로 뿜는다."""
    while _ENGINES:
        await _ENGINES.pop().dispose()


async def _verify_phone(service: AuthService, phone: str = "010-1234-5678") -> None:
    code, _ = await service.request_phone_verification(phone)
    await service.verify_phone_code(phone, code)


async def _verified_service(email="hong@example.com", phone="010-1234-5678"):
    """이메일+휴대폰 인증까지 통과한 상태의 서비스를 돌려준다."""
    factory = await _session_factory()
    session = factory()
    service = AuthService(session)
    token, _ = await service.request_email_verification(email)
    await service.verify_email_token(token)
    await _verify_phone(service, phone)
    return service


async def _expect(status_code: int, coro, label: str):
    try:
        await coro
    except HTTPException as e:
        assert e.status_code == status_code, f"{label}: {status_code} 기대했으나 {e.status_code} ({e.detail})"
        return e
    raise AssertionError(f"{label}: {status_code}가 나와야 하는데 성공했다")


async def test_signup_happy_path():
    service = await _verified_service()
    result = await service.signup(_signup_request())

    assert result.is_new_user
    assert result.tokens.access_token and result.tokens.refresh_token
    user = result.user
    assert user.email == "hong@example.com"
    assert user.password_hash is not None and GOOD_PASSWORD not in user.password_hash
    assert user.onboarding_status == OnboardingStatus.PROFILE_REQUIRED
    # 전화번호는 정규화 저장 + 조회용 해시가 같이 채워져야 한다.
    assert user.phone_number == "01012345678"
    assert user.phone_hash == security.hash_phone("01012345678")

    # 동의는 카탈로그의 모든 항목이 행으로 남고, 필수 항목은 전부 활성이어야 한다.
    rows = {a["terms_type"]: a for a in await service.agreement_status(user)}
    assert len(rows) == len(TERMS_CATALOG)
    for spec in TERMS_CATALOG:
        row = rows[str(spec.terms_type)]
        assert row["current_version"] == spec.version
        if spec.is_required:
            assert row["agreed"] and not row["needs_reagreement"], f"{spec.terms_type} 필수 동의 누락"


async def test_signup_requires_email_verification():
    factory = await _session_factory()
    service = AuthService(factory())  # 인증 없이 바로 가입 시도
    await _expect(400, service.signup(_signup_request()), "이메일 미인증")


async def test_signup_requires_phone_verification():
    factory = await _session_factory()
    service = AuthService(factory())
    token, _ = await service.request_email_verification("hong@example.com")
    await service.verify_email_token(token)  # 이메일만 인증, 휴대폰은 인증 안 함
    await _expect(400, service.signup(_signup_request()), "휴대폰 미인증")


async def test_phone_verification_wrong_code_rejected():
    service = await _verified_service()
    code, _ = await service.request_phone_verification("010-2222-3333")
    wrong = "000000" if code != "000000" else "111111"
    await _expect(400, service.verify_phone_code("010-2222-3333", wrong), "잘못된 인증 코드")
    await service.verify_phone_code("010-2222-3333", code)  # 올바른 코드는 통과해야 한다


async def test_duplicate_checks():
    service = await _verified_service()
    await service.signup(_signup_request())

    # 이메일 중복
    await _verify_phone(service, "010-9999-8888")
    await _expect(409, service.signup(_signup_request(nickname="다른닉네임", phone="010-9999-8888")), "이메일 중복")
    # 닉네임 중복
    token, _ = await service.request_email_verification("other@example.com")
    await service.verify_email_token(token)
    await _expect(409, service.signup(_signup_request(email="other@example.com", phone="010-9999-8888")), "닉네임 중복")
    # 휴대폰 중복
    await _expect(
        409,
        service.signup(_signup_request(email="other@example.com", nickname="다른닉네임")),
        "휴대폰 중복",
    )
    # onBlur 중복확인 엔드포인트도 같은 판정을 내려야 한다
    assert await service.is_email_taken("HONG@example.com") is True  # 정규화 후 비교
    assert await service.is_nickname_taken("길동이") is True
    assert await service.is_phone_taken("010-1234-5678") is True
    assert await service.is_phone_taken("010-0000-0000") is False


async def test_agreement_validation():
    service = await _verified_service()
    # 카탈로그에 없는 약관
    bad = _agreements() + [TermAgreementItem(terms_type="not_a_real_term", version="1.0", agreed=True)]
    await _expect(400, service.signup(_signup_request(agreements=bad)), "존재하지 않는 약관")
    # 구버전 제출 -> 재동의 유도
    await _expect(409, service.signup(_signup_request(agreements=_agreements(stale=True))), "구버전 약관")
    # 필수 누락
    await _expect(400, service.signup(_signup_request(agreements=_agreements(drop_required=True))), "필수 약관 누락")


async def test_agreement_version_bump_needs_reagreement():
    """약관 문안이 개정되면(version 상승) 기존 사용자가 재동의 대상으로 잡혀야 한다."""
    # service 모듈이 `from .terms_catalog import TERMS_CATALOG`로 이름을 가져왔으므로,
    # 카탈로그 모듈이 아니라 service의 이름을 갈아야 한다.
    from . import service as service_module

    service = await _verified_service()
    result = await service.signup(_signup_request())

    original_tuple = service_module.TERMS_CATALOG
    original = service_module.CATALOG_BY_TYPE["service"]
    bumped = type(original)(
        original.terms_type, "2.0", original.title, original.url, original.is_required, original.revocable
    )
    service_module.TERMS_CATALOG = tuple(bumped if str(s.terms_type) == "service" else s for s in original_tuple)
    service_module.CATALOG_BY_TYPE["service"] = bumped
    try:
        rows = {a["terms_type"]: a for a in await service.agreement_status(result.user)}
        assert rows["service"]["agreed_version"] == "1.0"
        assert rows["service"]["current_version"] == "2.0"
        assert rows["service"]["needs_reagreement"], "약관 개정 후에도 재동의가 필요하지 않다고 나온다"
        # 구버전 문안으로 다시 제출하면 409로 막혀야 한다
        await _expect(
            409,
            service.submit_agreements(result.user, _agreements(stale=True)),
            "개정 후 구버전 재제출",
        )
    finally:
        service_module.TERMS_CATALOG = original_tuple
        service_module.CATALOG_BY_TYPE["service"] = original


async def test_marketing_revocable_required_not():
    service = await _verified_service()
    result = await service.signup(_signup_request())
    await service.revoke_agreement(result.user, "marketing")
    rows = {a["terms_type"]: a for a in await service.agreement_status(result.user)}
    assert rows["marketing"]["agreed"] is False
    # 필수 약관은 철회 불가 - 탈퇴로 안내
    await _expect(400, service.revoke_agreement(result.user, "service"), "필수 약관 철회 차단")


async def test_login_and_lockout():
    service = await _verified_service()
    await service.signup(_signup_request())

    # 이메일 대소문자/공백이 달라도 로그인돼야 한다
    ok = await service.login(" HONG@Example.com ", GOOD_PASSWORD)
    assert ok.user.email == "hong@example.com"
    assert ok.user.failed_login_attempts == 0

    for i in range(config.MAX_LOGIN_ATTEMPTS - 1):
        await _expect(400, service.login("hong@example.com", "WrongPass1!"), f"실패 {i + 1}회")
    # 마지막 실패에서 잠긴다 - 응답은 여전히 400(계정 존재 여부를 노출하지 않기 위함)
    await _expect(400, service.login("hong@example.com", "WrongPass1!"), "잠금 유발 실패")
    # 이제는 올바른 비밀번호여도 423
    await _expect(423, service.login("hong@example.com", GOOD_PASSWORD), "잠긴 계정")


async def test_refresh_rotation_and_reuse_detection():
    service = await _verified_service()
    result = await service.signup(_signup_request())
    first = result.tokens.refresh_token

    second = await service.rotate_refresh_token(first)
    assert second.refresh_token != first, "로테이션되지 않았다 - 같은 refresh token이 계속 유효하다"

    # 예전 토큰 재사용 -> 탈취로 간주해 전 세션 로그아웃
    await _expect(401, service.rotate_refresh_token(first), "재사용 탐지")
    # 재사용 탐지가 방금 발급한 토큰까지 무효화했는지
    await _expect(401, service.rotate_refresh_token(second.refresh_token), "재사용 탐지 후 전 세션 무효화")


async def test_logout_is_idempotent():
    service = await _verified_service()
    result = await service.signup(_signup_request())
    await service.logout(result.tokens.refresh_token)
    await service.logout(result.tokens.refresh_token)  # 두 번째도 조용히 성공
    await service.logout(None)
    await service.logout("완전히-잘못된-토큰")
    await _expect(401, service.rotate_refresh_token(result.tokens.refresh_token), "로그아웃된 토큰")


async def test_password_reset_revokes_sessions():
    service = await _verified_service()
    result = await service.signup(_signup_request())
    token, _ = await service.create_password_reset_token("hong@example.com")
    assert token is not None

    await service.reset_password(token, "NewPassword456!")
    # 기존 세션은 끊기고, 새 비밀번호로만 로그인된다
    await _expect(401, service.rotate_refresh_token(result.tokens.refresh_token), "재설정 후 기존 세션")
    await _expect(400, service.login("hong@example.com", GOOD_PASSWORD), "옛 비밀번호")
    assert (await service.login("hong@example.com", "NewPassword456!")).user.id == result.user.id
    # 같은 재설정 링크를 두 번 쓸 수 있는지 - JWT 만료 전이라 통과한다(알려진 한계, README 참고)

    # 가입 안 된 이메일도 404가 아니라 조용히 None (이메일 열거 방지)
    missing, _ = await service.create_password_reset_token("nobody@example.com")
    assert missing is None


async def test_guest_and_withdrawal():
    service = await _verified_service()
    guest = await service.guest_login()
    assert guest.user.is_guest and guest.user.password_hash is None
    # 게스트는 비밀번호가 없으므로 비밀번호 없이 탈퇴 가능해야 한다(불가하면 영구 잔존 계정이 된다)
    await service.withdraw(guest.user, None)

    result = await service.signup(_signup_request())
    await _expect(400, service.withdraw(result.user, "틀린비밀번호1!"), "탈퇴 시 비밀번호 재확인")
    await service.withdraw(result.user, GOOD_PASSWORD)
    # 탈퇴 신청 후에는 로그인이 막히고, 유예기간 안에는 취소된다
    await _expect(423, service.login("hong@example.com", GOOD_PASSWORD), "탈퇴 처리 중 로그인")
    restored = await service.cancel_withdrawal("hong@example.com", GOOD_PASSWORD)
    assert restored.user.deactivated_at is None
    assert (await service.login("hong@example.com", GOOD_PASSWORD)).user.id == restored.user.id


async def test_sanctioned_identity_blocks_resignup():
    """REQ-F-ACC-11: 제재 확정 후 물리삭제된 계정의 휴대폰 본인확인값으로는 재가입이 막혀야 한다."""
    service = await _verified_service()
    result = await service.signup(_signup_request())
    await service.record_sanction(result.user.id, "허위 신고 확정")

    original_grace = config.WITHDRAWAL_GRACE
    config.WITHDRAWAL_GRACE = timedelta(0)  # 유예 없이 즉시 물리삭제 -> phone_hash 봉인 경로 실행
    try:
        await service.withdraw(result.user, GOOD_PASSWORD)
    finally:
        config.WITHDRAWAL_GRACE = original_grace

    # 같은 휴대폰으로 다른 이메일/닉네임으로 재가입해도 차단돼야 한다.
    await _verify_phone(service, "010-1234-5678")
    token, _ = await service.request_email_verification("hong2@example.com")
    await service.verify_email_token(token)
    await _expect(
        403,
        service.signup(_signup_request(email="hong2@example.com", nickname="새닉네임")),
        "제재 이력 재가입 차단",
    )


async def test_find_email_masks():
    service = await _verified_service()
    await service.signup(_signup_request())
    masked = await service.find_email("홍길동", "길동이")
    assert masked != "hong@example.com" and masked.endswith("@example.com")
    await _expect(404, service.find_email("다른사람", "길동이"), "이름 불일치")


ASYNC_TESTS = [
    test_signup_happy_path,
    test_signup_requires_email_verification,
    test_signup_requires_phone_verification,
    test_phone_verification_wrong_code_rejected,
    test_duplicate_checks,
    test_agreement_validation,
    test_agreement_version_bump_needs_reagreement,
    test_marketing_revocable_required_not,
    test_login_and_lockout,
    test_refresh_rotation_and_reuse_detection,
    test_logout_is_idempotent,
    test_password_reset_revokes_sessions,
    test_guest_and_withdrawal,
    test_sanctioned_identity_blocks_resignup,
    test_find_email_masks,
]
SYNC_TESTS = [
    test_password_policy,
    test_password_hash_roundtrip,
    test_age_gate,
    test_normalizers,
    test_jwt_type_confusion,
]


def main() -> int:
    failed = []
    for fn in SYNC_TESTS:
        try:
            fn()
            print(f"  ok  {fn.__name__}")
        except Exception as e:
            failed.append((fn.__name__, e))
            print(f"FAIL  {fn.__name__}: {e}")

    async def _run(fn):
        try:
            await fn()
        finally:
            await _dispose_engines()

    for fn in ASYNC_TESTS:
        try:
            asyncio.run(_run(fn))
            print(f"  ok  {fn.__name__}")
        except Exception as e:
            failed.append((fn.__name__, e))
            print(f"FAIL  {fn.__name__}: {type(e).__name__}: {e}")

    total = len(SYNC_TESTS) + len(ASYNC_TESTS)
    print(f"\n{total - len(failed)}/{total} 통과")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
