"""자체 검증. `python -m security_kit.test_security_kit`

프레임워크 없이 assert만 쓴다. DB도 웹서버도 필요 없다 - 이 모듈이 순수 로직이라는 게
검증 가능하다는 뜻이기도 하다.
"""

import os
from datetime import timedelta

os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-production-needs-32-bytes-min")
os.environ.setdefault("PII_HASH_KEY", "test-lookup-hash-key")
os.environ.setdefault("COOKIE_SECURE", "false")

import jwt as pyjwt  # noqa: E402

from . import config, crypto, guards, tokens  # noqa: E402

PASSWORD = "Password123!"


# ══════════════════════════════════════════════════════════════════════════
# 비밀번호
# ══════════════════════════════════════════════════════════════════════════
def test_password_roundtrip():
    stored = crypto.hash_password(PASSWORD)
    assert crypto.verify_password(PASSWORD, stored)
    assert not crypto.verify_password(PASSWORD + "x", stored)
    assert not crypto.verify_password("", stored)
    # salt가 매번 달라야 한다 - 같으면 같은 비밀번호를 쓴 계정을 해시만 보고 알 수 있다.
    assert stored != crypto.hash_password(PASSWORD)
    # 평문이 해시 문자열에 남아 있으면 안 된다.
    assert PASSWORD not in stored


def test_password_broken_hash_never_raises():
    """로그인 경로가 500을 내면 안 된다 - 깨진 해시는 인증 실패로 처리."""
    for garbage in ["", "garbage", "scrypt$$$$", "scrypt$a$b$c$d$e", "bcrypt$2b$12$xx", "a$b$c$d$e$f"]:
        assert crypto.verify_password(PASSWORD, garbage) is False, garbage


def test_needs_rehash():
    assert not crypto.needs_rehash(crypto.hash_password(PASSWORD))
    assert crypto.needs_rehash("bcrypt$2b$12$whatever")  # 다른 알고리즘 → 이전 대상
    assert crypto.needs_rehash("scrypt$1024$8$1$c2FsdA==$aGFzaA==")  # 약한 파라미터
    assert crypto.needs_rehash("nonsense")


# ══════════════════════════════════════════════════════════════════════════
# 해시 / 마스킹
# ══════════════════════════════════════════════════════════════════════════
def test_lookup_hash_is_keyed():
    """전화번호 조회 해시는 키를 섞어야 한다 - 단순 sha256이면 전수조사로 복원된다."""
    import hashlib

    phone = "01012345678"
    digest = crypto.hash_lookup_value(phone)
    assert digest != hashlib.sha256(phone.encode()).hexdigest(), "키 없는 해시로 계산되고 있다"
    assert digest == crypto.hash_lookup_value(phone)  # 같은 입력 → 같은 결과(조회에 쓸 수 있어야 함)
    assert digest != crypto.hash_lookup_value("01012345679")

    os.environ["PII_HASH_KEY"] = "different-key"
    try:
        assert crypto.hash_lookup_value(phone) != digest, "키를 바꿨는데 결과가 같다"
    finally:
        os.environ["PII_HASH_KEY"] = "test-lookup-hash-key"


def test_constant_time_equals():
    assert crypto.constant_time_equals("123456", "123456")
    assert not crypto.constant_time_equals("123456", "123457")
    assert not crypto.constant_time_equals("123456", "")


def test_masking_and_redaction():
    assert crypto.mask_email("hongildong@example.com").startswith("hon")
    assert "hongildong" not in crypto.mask_email("hongildong@example.com")
    assert crypto.mask_email("ab@x.com").startswith("a*")
    assert crypto.mask_phone("01012345678") == "010****5678"
    assert crypto.mask_phone("010-1234-5678") == "010****5678"

    log = "가입 실패: hongildong@example.com / 010-1234-5678 중복"
    cleaned = crypto.redact(log)
    assert "hongildong@example.com" not in cleaned
    assert "1234-5678" not in cleaned and "01012345678" not in cleaned
    assert "가입 실패" in cleaned  # 메시지 자체는 남아야 로그가 쓸모 있다


def test_sanitize_credential():
    assert crypto.sanitize_credential(" pass​word\n") == "password"
    assert crypto.sanitize_credential("﻿Password123!") == "Password123!"
    assert crypto.sanitize_credential("normal") == "normal"


def test_random_is_unique():
    assert len({crypto.new_url_token() for _ in range(50)}) == 50
    assert len({crypto.new_nonce() for _ in range(50)}) == 50
    assert len(crypto.new_secret().encode()) >= config.MIN_SECRET_BYTES


# ══════════════════════════════════════════════════════════════════════════
# JWT
# ══════════════════════════════════════════════════════════════════════════
def test_token_type_confusion_blocked():
    """토큰 종류를 바꿔치기해 쓰지 못해야 한다."""
    access = tokens.issue_access(1, timedelta(minutes=5))
    refresh, jti, _ = tokens.issue_refresh(1, timedelta(days=1))
    reset = tokens.issue("password_reset", timedelta(minutes=5), sub="1")

    assert tokens.decode(access, "access")["sub"] == "1"
    assert tokens.decode(refresh, "refresh")["jti"] == jti

    for token, wrong in [(refresh, "access"), (reset, "access"), (access, "refresh"), (access, "password_reset")]:
        try:
            tokens.decode(token, wrong)
        except pyjwt.InvalidTokenError:
            continue
        raise AssertionError(f"{wrong} 자리에 다른 종류의 토큰이 통과되었다")


def test_expired_token_rejected():
    expired = tokens.issue("access", timedelta(seconds=-10), sub="1")
    try:
        tokens.decode(expired, "access")
    except pyjwt.InvalidTokenError:
        return
    raise AssertionError("만료된 토큰이 통과되었다")


def test_tampered_token_rejected():
    token = tokens.issue_access(1, timedelta(minutes=5))
    head, payload, sig = token.split(".")
    for broken in [f"{head}.{payload}.{'A' * len(sig)}", f"{head}.{payload}."]:
        try:
            tokens.decode(broken, "access")
        except pyjwt.InvalidTokenError:
            continue
        raise AssertionError("서명이 조작된 토큰이 통과되었다")


def test_short_secret_rejected():
    original = os.environ["JWT_SECRET"]
    os.environ["JWT_SECRET"] = "short"
    try:
        tokens.issue_access(1, timedelta(minutes=5))
    except RuntimeError as e:
        assert "짧습니다" in str(e)
    else:
        raise AssertionError("32바이트 미만 비밀키가 통과되었다")
    finally:
        os.environ["JWT_SECRET"] = original

    os.environ["JWT_SECRET"] = ""
    try:
        tokens.issue_access(1, timedelta(minutes=5))
    except RuntimeError as e:
        assert "필요합니다" in str(e)
    else:
        raise AssertionError("비밀키 없이 토큰이 발급되었다")
    finally:
        os.environ["JWT_SECRET"] = original


# ══════════════════════════════════════════════════════════════════════════
# 로그인 잠금
# ══════════════════════════════════════════════════════════════════════════
def test_lockout_locks_after_max_attempts():
    policy = guards.LockoutPolicy(max_attempts=3, duration=timedelta(minutes=10))
    now = config.now()

    state = guards.LockoutState(0, None)
    for i in range(2):
        state = policy.on_failure(state.failed_attempts, state.locked_until, now)
        assert state.locked_until is None, f"{i + 1}회 실패에서 벌써 잠겼다"
        assert not state.just_locked

    state = policy.on_failure(state.failed_attempts, state.locked_until, now)
    assert state.just_locked and state.locked_until is not None
    assert policy.is_locked(state.locked_until, now)
    assert policy.remaining_minutes(state.locked_until, now) == 11


def test_lockout_auto_release_resets_counter():
    """자동 해제 후에는 실패 횟수를 0부터 다시 센다.

    이게 없으면 잠금이 풀린 직후 단 한 번의 오타로 즉시 재잠금되어(옛 카운터가 임계치에
    남아 있으므로) "자동 해제로 새 기회를 준다"는 의도가 무의미해진다.
    """
    policy = guards.LockoutPolicy(max_attempts=3, duration=timedelta(minutes=10))
    now = config.now()
    locked_until = now - timedelta(minutes=1)  # 이미 만료된 잠금

    assert not policy.is_locked(locked_until, now)
    state = policy.on_failure(3, locked_until, now)
    assert state.failed_attempts == 1, "만료된 잠금의 카운터가 그대로 누적되고 있다"
    assert state.locked_until is None, "자동 해제 직후 한 번의 실패로 재잠금되었다"


def test_lockout_success_resets():
    policy = guards.LockoutPolicy()
    state = policy.on_success()
    assert state.failed_attempts == 0 and state.locked_until is None


def test_lockout_handles_naive_datetime():
    """MySQL은 DATETIME을 naive로 돌려준다 - 비교에서 TypeError가 나면 로그인이 500이 된다."""
    policy = guards.LockoutPolicy(duration=timedelta(minutes=10))
    naive_future = (config.now() + timedelta(minutes=5)).replace(tzinfo=None)
    assert policy.is_locked(naive_future) is True
    assert policy.remaining_minutes(naive_future) > 0

    naive_past = (config.now() - timedelta(minutes=5)).replace(tzinfo=None)
    assert policy.is_locked(naive_past) is False


# ══════════════════════════════════════════════════════════════════════════
# 요청 빈도 제한
# ══════════════════════════════════════════════════════════════════════════
def test_rate_limiter_allows_then_blocks():
    rl = guards.RateLimiter(max_calls=3, window=timedelta(seconds=60))
    for i in range(3):
        assert rl.allow("kim@example.com", at=100.0), f"{i + 1}번째가 막혔다"
    assert not rl.allow("kim@example.com", at=100.0)
    # 다른 키는 영향 없어야 한다
    assert rl.allow("other@example.com", at=100.0)


def test_rate_limiter_window_slides():
    rl = guards.RateLimiter(max_calls=2, window=timedelta(seconds=60))
    assert rl.allow("k", at=0.0)
    assert rl.allow("k", at=30.0)
    assert not rl.allow("k", at=50.0)
    assert rl.allow("k", at=61.0), "창이 지났는데도 막혀 있다"


def test_rate_limiter_denied_calls_do_not_extend_block():
    """거부된 요청까지 세면 창이 끝없이 밀려 사실상 영구 차단이 된다."""
    rl = guards.RateLimiter(max_calls=1, window=timedelta(seconds=10))
    assert rl.allow("k", at=0.0)
    for t in (1.0, 2.0, 3.0, 9.0):
        assert not rl.allow("k", at=t)
    assert rl.allow("k", at=11.0), "거부된 시도가 창을 밀어냈다"


def test_rate_limiter_retry_after_and_reset():
    rl = guards.RateLimiter(max_calls=1, window=timedelta(seconds=60))
    assert rl.retry_after("k", at=0.0) == 0
    rl.allow("k", at=0.0)
    assert 1 <= rl.retry_after("k", at=10.0) <= 61
    rl.reset("k")
    assert rl.allow("k", at=10.0)


def test_rate_limiter_sweep_frees_keys():
    rl = guards.RateLimiter(max_calls=1, window=timedelta(seconds=1))
    for i in range(100):
        rl.allow(f"key{i}", at=0.0)
    assert len(rl._hits) == 100
    rl.sweep()  # monotonic now가 0보다 훨씬 크므로 전부 만료
    assert rl._hits == {}, "만료된 키가 정리되지 않아 메모리가 계속 늘어난다"


# ══════════════════════════════════════════════════════════════════════════
# 재생 공격 방어
# ══════════════════════════════════════════════════════════════════════════
def test_nonce_consumed_once():
    store = guards.NonceStore(ttl=timedelta(minutes=10))
    nonce = crypto.new_nonce()
    assert store.consume(nonce, at=0.0) is True
    assert store.consume(nonce, at=1.0) is False, "같은 nonce가 두 번 소비되었다(재생 공격 가능)"
    assert store.consume(crypto.new_nonce(), at=1.0) is True


# ══════════════════════════════════════════════════════════════════════════
# 응답 헤더 / 쿠키
# ══════════════════════════════════════════════════════════════════════════
def test_security_headers_middleware():
    import asyncio

    async def dummy_app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"ok"})

    wrapped = guards.security_headers_middleware(dummy_app, hsts=True)
    captured = {}

    async def send(message):
        if message["type"] == "http.response.start":
            captured.update({k.decode(): v.decode() for k, v in message["headers"]})

    asyncio.run(wrapped({"type": "http"}, None, send))
    assert captured["x-content-type-options"] == "nosniff"
    assert captured["x-frame-options"] == "DENY"
    assert "strict-transport-security" in captured
    assert captured["content-type"] == "text/plain", "기존 헤더를 덮어썼다"

    # hsts=False면 붙지 않아야 한다(http 개발환경에서 접속이 막히면 안 된다)
    captured.clear()
    asyncio.run(guards.security_headers_middleware(dummy_app, hsts=False)({"type": "http"}, None, send))
    assert "strict-transport-security" not in captured


def test_refresh_cookie_flags():
    class FakeResponse:
        def __init__(self):
            self.kwargs = {}

        def set_cookie(self, **kwargs):
            self.kwargs = kwargs

    resp = FakeResponse()
    guards.set_refresh_cookie(resp, "tok", timedelta(days=14))
    assert resp.kwargs["httponly"] is True, "httponly가 아니면 XSS로 토큰이 털린다"
    assert resp.kwargs["samesite"] == "lax"
    assert resp.kwargs["max_age"] == 14 * 24 * 3600
    assert "expires" not in resp.kwargs, "expires는 UTC만 받아 KST에서 ValueError가 난다"

    os.environ["COOKIE_SECURE"] = "true"
    try:
        resp = FakeResponse()
        guards.set_refresh_cookie(resp, "tok", timedelta(days=1))
        assert resp.kwargs["secure"] is True
    finally:
        os.environ["COOKIE_SECURE"] = "false"


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_")]


def main() -> int:
    failed = []
    for fn in TESTS:
        try:
            fn()
            print(f"  ok  {fn.__name__}")
        except Exception as e:
            failed.append(fn.__name__)
            print(f"FAIL  {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(TESTS) - len(failed)}/{len(TESTS)} 통과")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
