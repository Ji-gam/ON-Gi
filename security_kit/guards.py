"""공격 방어 로직. ORM·프레임워크에 묶이지 않은 순수 정책 + 얇은 ASGI/쿠키 헬퍼.

LockoutPolicy와 RateLimiter는 DB를 모른다 - 상태값을 받아 다음 상태를 돌려주기만 하므로,
어떤 ORM을 쓰든 그대로 붙고 단독으로 테스트된다.
"""

import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from . import config


# ══════════════════════════════════════════════════════════════════════════
# 로그인 시도 제한 (브루트포스)
# ══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class LockoutState:
    """계정에 반영할 다음 상태. 호출부가 그대로 컬럼에 대입하면 된다."""

    failed_attempts: int
    locked_until: datetime | None
    just_locked: bool = False


@dataclass(frozen=True)
class LockoutPolicy:
    """연속 실패 N회 → 일정 시간 잠금.

    영구 잠금은 쓰지 말 것. 두 가지 문제가 있다:
    1. 자력 복구 수단이 없는 계정(전화번호만으로 가입 등)이 영영 못 들어온다.
    2. 이메일만 아는 공격자가 비인증 상태로 아무 계정이나 잠글 수 있다 = DoS.
    """

    max_attempts: int = 5
    duration: timedelta = timedelta(minutes=15)

    def is_locked(self, locked_until: datetime | None, at: datetime | None = None) -> bool:
        at = at or config.now()
        locked_until = config.aware(locked_until)
        return locked_until is not None and locked_until > at

    def remaining_minutes(self, locked_until: datetime | None, at: datetime | None = None) -> int:
        at = at or config.now()
        locked_until = config.aware(locked_until)
        if locked_until is None or locked_until <= at:
            return 0
        return max(1, int((locked_until - at).total_seconds() // 60) + 1)

    def on_failure(
        self, failed_attempts: int, locked_until: datetime | None, at: datetime | None = None
    ) -> LockoutState:
        """비밀번호 불일치를 반영한다.

        잠금 기간이 이미 지났으면(자동 해제 대상) 실패 횟수를 0부터 다시 센다. 그러지 않으면
        만료된 옛 잠금의 실패 횟수(이미 임계치 근처) 위에 누적돼, 자동 해제 직후 단 한 번의
        오타로 즉시 재잠금된다 - "자동 해제로 새 기회를 준다"는 의도가 무의미해진다.
        """
        at = at or config.now()
        if locked_until is not None and not self.is_locked(locked_until, at):
            failed_attempts = 0

        attempts = failed_attempts + 1
        if attempts >= self.max_attempts:
            return LockoutState(failed_attempts=attempts, locked_until=at + self.duration, just_locked=True)
        return LockoutState(failed_attempts=attempts, locked_until=None)

    def on_success(self) -> LockoutState:
        """로그인 성공 - 실패 카운터와 잠금을 모두 초기화한다."""
        return LockoutState(failed_attempts=0, locked_until=None)


# ══════════════════════════════════════════════════════════════════════════
# 요청 빈도 제한
# ══════════════════════════════════════════════════════════════════════════
class RateLimiter:
    """슬라이딩 윈도우 방식. 계정 잠금이 막지 못하는 것들(인증 메일 발송 남발, 인증코드
    브루트포스, 가입 스팸)을 IP·이메일 단위로 막는다.

    쓰는 곳: 인증 메일/SMS 발송, 비밀번호 재설정 요청, 6자리 코드 검증, 회원가입.

    ponytail: 프로세스 로컬 메모리다. 워커가 여러 개면 워커당 따로 세므로 실효 한도가
    워커 수만큼 늘어난다. 정확한 전역 제한이 필요하면 Redis(INCR + EXPIRE)로 교체 -
    인터페이스는 그대로 두고 내부만 바꾸면 된다.
    """

    def __init__(self, max_calls: int, window: timedelta):
        self.max_calls = max_calls
        self.window_seconds = window.total_seconds()
        self._hits: dict[str, deque[float]] = {}

    def _prune(self, key: str, at: float) -> deque[float]:
        hits = self._hits.get(key)
        if hits is None:
            hits = deque()
            self._hits[key] = hits
        cutoff = at - self.window_seconds
        while hits and hits[0] <= cutoff:
            hits.popleft()
        return hits

    def allow(self, key: str, at: float | None = None) -> bool:
        """허용되면 True를 돌려주고 호출을 1회 기록한다. 거부되면 기록하지 않는다
        (거부된 요청까지 세면 창이 끝없이 밀려 영구 차단이 된다)."""
        at = time.monotonic() if at is None else at
        hits = self._prune(key, at)
        if len(hits) >= self.max_calls:
            return False
        hits.append(at)
        return True

    def retry_after(self, key: str, at: float | None = None) -> int:
        """다시 시도 가능해질 때까지 남은 초. HTTP 429의 Retry-After 헤더에 넣는다."""
        at = time.monotonic() if at is None else at
        hits = self._prune(key, at)
        if len(hits) < self.max_calls:
            return 0
        return max(1, int(hits[0] + self.window_seconds - at) + 1)

    def reset(self, key: str) -> None:
        """정상 완료 후 해당 키의 카운터를 비운다(예: 인증코드를 맞게 입력함)."""
        self._hits.pop(key, None)

    def sweep(self) -> None:
        """만료된 키를 정리한다. 스케줄러에서 주기적으로 호출 - 없으면 키가 무한히 쌓인다."""
        at = time.monotonic()
        for key in list(self._hits):
            if not self._prune(key, at):
                self._hits.pop(key, None)


# ══════════════════════════════════════════════════════════════════════════
# 재생 공격 방어 (일회성 값 소비)
# ══════════════════════════════════════════════════════════════════════════
class NonceStore:
    """nonce·인증코드처럼 "한 번만 유효해야 하는" 값의 소비 기록.

    검증에 성공했다는 것만으로는 부족하다. 유효한 값을 그대로 다시 보내는 재생 공격을
    막으려면 "이미 썼다"를 기록해야 한다. DB 유니크 제약으로 하면 경쟁 조건까지 막힌다
    (INSERT 충돌 = 이미 쓰인 값). 이 클래스는 DB가 없는 경우의 메모리 버전이다.

    ponytail: 프로세스 로컬. 멀티 워커·재시작 내구성이 필요하면 유니크 PK를 가진 테이블
    (auth_kit.models.OAuthNonce 참고)이나 Redis SETNX로 교체.
    """

    def __init__(self, ttl: timedelta = timedelta(minutes=10)):
        self.ttl_seconds = ttl.total_seconds()
        self._seen: dict[str, float] = {}

    def consume(self, key: str, at: float | None = None) -> bool:
        """처음 쓰는 값이면 True(소비 성공), 이미 쓴 값이면 False(재생 시도)."""
        at = time.monotonic() if at is None else at
        self._sweep(at)
        if key in self._seen:
            return False
        self._seen[key] = at
        return True

    def _sweep(self, at: float) -> None:
        cutoff = at - self.ttl_seconds
        for key, seen_at in list(self._seen.items()):
            if seen_at <= cutoff:
                self._seen.pop(key, None)


# ══════════════════════════════════════════════════════════════════════════
# 응답 측 방어 (쿠키 / 헤더)
# ══════════════════════════════════════════════════════════════════════════
def set_refresh_cookie(response: Any, token: str, ttl: timedelta, key: str = "refresh_token") -> None:
    """장기 토큰은 응답 body가 아니라 httpOnly 쿠키로만 내려보낸다.

    body에 담아 프론트가 localStorage에 저장하면 XSS 한 번으로 장기 토큰이 전부 털린다
    (httpOnly 쿠키는 JS가 읽을 수 없어 같은 XSS로도 값을 빼내지 못한다).

    expires 대신 max_age를 쓴다 - Starlette의 expires는 UTC datetime만 받고(KST aware를
    주면 ValueError), max_age는 상대시간이라 서버·클라이언트 시계 차이에도 영향이 없다.
    """
    response.set_cookie(
        key=key,
        value=token,
        httponly=True,
        secure=config.cookie_secure(),
        samesite="lax",  # CSRF 완화. 크로스 사이트로 쿠키를 보내야 하면 "none" + secure 필수
        domain=config.cookie_domain(),
        max_age=int(ttl.total_seconds()),
        path="/",
    )


def clear_refresh_cookie(response: Any, key: str = "refresh_token") -> None:
    """삭제할 때도 domain·path가 설정 시와 같아야 실제로 지워진다."""
    response.delete_cookie(key=key, domain=config.cookie_domain(), path="/")


# API 서버 기본값. HTML을 직접 서빙하면 CSP를 화면 요구에 맞게 바꿔야 한다.
DEFAULT_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",  # 응답을 브라우저가 임의 타입으로 재해석하는 것 차단
    "X-Frame-Options": "DENY",  # 클릭재킹(iframe 삽입) 차단
    "Referrer-Policy": "no-referrer",  # 외부 링크로 URL(토큰 포함 가능)이 새는 것 차단
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}
# HSTS는 https로 서비스할 때만. http 개발 환경에 걸면 브라우저가 https를 강제해 접속이 막힌다.
HSTS_HEADER = ("Strict-Transport-Security", "max-age=31536000; includeSubDomains")


def security_headers_middleware(
    app: Callable[..., Awaitable[None]],
    *,
    headers: dict[str, str] | None = None,
    hsts: bool | None = None,
) -> Callable[..., Awaitable[None]]:
    """응답에 보안 헤더를 붙이는 순수 ASGI 미들웨어(추가 의존성 없음).

        app.add_middleware(BaseHTTPMiddleware, ...)  # 대신
        app = security_headers_middleware(app)       # 이렇게 감싼다

    FastAPI에서는 `app.middleware_stack` 대신 서버 실행 시점에 감싸는 게 간단하다:
        uvicorn.run(security_headers_middleware(app), ...)
    """
    extra = dict(headers or DEFAULT_SECURITY_HEADERS)
    if hsts if hsts is not None else config.cookie_secure():
        extra[HSTS_HEADER[0]] = HSTS_HEADER[1]
    encoded = [(k.lower().encode(), v.encode()) for k, v in extra.items()]

    async def middleware(scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await app(scope, receive, send)
            return

        async def send_wrapper(message: Any) -> None:
            if message["type"] == "http.response.start":
                existing = {k.lower() for k, _ in message.get("headers", [])}
                message["headers"] = list(message.get("headers", [])) + [
                    (k, v) for k, v in encoded if k not in existing
                ]
            await send(message)

        await app(scope, receive, send_wrapper)

    return middleware
