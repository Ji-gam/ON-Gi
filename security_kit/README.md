# security_kit — 도메인 무관 보안 모듈

AH_04_01 ~ AH_04_04 네 프로젝트에서 보안 관련 코드만 뽑아 회원가입 도메인과 분리한 것.
회원가입이 없는 프로젝트에도 그대로 붙는다. 표준 라이브러리 + PyJWT만 쓴다
(개인정보 암호화 컬럼을 쓸 때만 `cryptography`, ORM 컬럼을 쓸 때만 `SQLAlchemy`).

검증: 자체 테스트 24/24 통과 (`python -m security_kit.test_security_kit`).
`auth_kit`이 이 모듈을 그대로 가져다 쓴다 — 구현은 여기 한 곳에만 있다.

```
security_kit/
  config.py   비밀값 환경변수 접근자, TIMEZONE, naive datetime 보정
  crypto.py   비밀번호/토큰 해시, 조회용 HMAC, 개인정보 암호화 컬럼, 마스킹·리댁션
  tokens.py   JWT 발급·검증(typ 강제), 소셜 OIDC ID token 검증
  guards.py   로그인 잠금, 요청 빈도 제한, 재생 방어, 보안 쿠키·헤더
```

---

## 1. 필요한 것만 골라 쓰기

### 비밀번호

```python
from security_kit import hash_password, verify_password, needs_rehash

user.password_hash = hash_password(plain)          # scrypt, salt 자동
if not verify_password(plain, user.password_hash): # 깨진 해시도 예외 없이 False
    raise Unauthorized
if needs_rehash(user.password_hash):               # 파라미터를 올린 뒤 점진 이전
    user.password_hash = hash_password(plain)      # 로그인 성공 직후가 유일한 기회
```

### 토큰

```python
from security_kit import issue_access, issue_refresh, decode
from datetime import timedelta

access = issue_access(user.id, timedelta(minutes=30))
refresh, jti, expires_at = issue_refresh(user.id, timedelta(days=14))  # jti를 DB에 저장

payload = decode(token, "access")   # typ이 다르면 InvalidTokenError
```

### 개인정보 (이름·전화번호·주소)

```python
from security_kit import EncryptedStr, hash_lookup_value

class User(Base):
    name: Mapped[str | None] = mapped_column(EncryptedStr)          # 저장 시 암호화
    phone: Mapped[str | None] = mapped_column(EncryptedStr)
    phone_hash: Mapped[str | None] = mapped_column(String(64), index=True)  # 검색용

user.phone = "01012345678"
user.phone_hash = hash_lookup_value("01012345678")
# 조회는 반드시 해시로 (암호화 컬럼은 WHERE/정렬/LIKE 불가)
await session.scalar(select(User).where(User.phone_hash == hash_lookup_value(q)))
```

### 로그인 잠금

```python
from security_kit import LockoutPolicy

LOCKOUT = LockoutPolicy(max_attempts=5, duration=timedelta(minutes=15))

if LOCKOUT.is_locked(user.locked_until):
    raise Locked(f"{LOCKOUT.remaining_minutes(user.locked_until)}분 후 다시 시도해주세요")

if not verify_password(pw, user.password_hash):
    s = LOCKOUT.on_failure(user.failed_login_attempts, user.locked_until)
    user.failed_login_attempts, user.locked_until = s.failed_attempts, s.locked_until
    raise Unauthorized
s = LOCKOUT.on_success()
user.failed_login_attempts, user.locked_until = s.failed_attempts, s.locked_until
```

ORM을 모르는 순수 로직이라 어떤 스택에도 붙고, 단독으로 테스트된다.

### 요청 빈도 제한

계정 잠금이 못 막는 것들: 인증 메일 발송 남발, 6자리 코드 브루트포스, 가입 스팸.

```python
from security_kit import RateLimiter

MAIL_LIMIT = RateLimiter(max_calls=3, window=timedelta(minutes=10))

if not MAIL_LIMIT.allow(f"verify:{email}"):
    raise TooManyRequests(retry_after=MAIL_LIMIT.retry_after(f"verify:{email}"))
```

### 보안 헤더

```python
from security_kit import security_headers_middleware
uvicorn.run(security_headers_middleware(app), ...)
```

nosniff / X-Frame-Options DENY / Referrer-Policy no-referrer / CSP / HSTS(https일 때만).
순수 ASGI라 추가 의존성이 없다.

### 로그 마스킹

```python
from security_kit import redact
logger.info(redact(f"가입 실패: {email} / {phone}"))   # hon***@x.com / 010****5678
```

---

## 2. 체크리스트 — 네 프로젝트에서 실제로 겪은 것들

각 항목은 4개 레포에서 문제가 됐거나 고쳐진 흔적이 있는 것만 적었다.

### 비밀번호

- [ ] 평문·역산 가능한 형태로 저장하지 않는다. 해시에 salt가 자동 포함되는지 확인
- [ ] **서버에도 정책이 있다.** 프론트만 검사하면 API 직접 호출로 `"1"` 짜리 비밀번호가 들어온다
      (실제로 한 레포는 `password: str | None`로 받고 검증이 아예 없었다)
- [ ] 응답 DTO에 해시 필드를 넣지 않는다 (`*Public` 응답 모델 분리)
- [ ] 실패 메시지에서 "계정 없음"과 "비밀번호 틀림"을 구분하지 않는다 → 이메일 열거 방지
- [ ] 깨진 해시로 로그인 경로가 500을 내지 않는다

### 토큰 / 세션

- [ ] 모든 토큰에 `typ`이 있고 검증 시 기대 타입을 명시한다. 없으면 refresh token으로 일반 API 호출 가능
- [ ] JWT 서명키 32바이트 이상. 짧으면 기동 시 막는다
- [ ] **refresh token을 응답 body에 넣지 않는다.** httpOnly 쿠키만. 한 레포는 처음에 body로
      내려 localStorage에 저장했고, XSS 한 번에 14일 토큰이 전부 털리는 회귀였다
- [ ] 토큰 갱신 시 refresh token 자체를 교체하고(로테이션) 예전 값을 즉시 무효화한다
- [ ] **무효화된 토큰이 다시 오면 그 계정의 전 세션을 로그아웃한다** (탈취 탐지)
- [ ] 비밀번호 재설정 성공 시 기존 세션을 전부 끊는다 (탈취 대응이 재설정의 목적)
- [ ] DB에는 토큰 원문이 아니라 jti나 해시만 남긴다
- [ ] 로그아웃은 토큰이 이미 만료·위조됐어도 성공한다(멱등)

### 개인정보

- [ ] 이름·전화번호를 평문 컬럼으로 두지 않는다 (건강·의료 데이터는 특히)
- [ ] 검색이 필요한 값은 **키 있는 HMAC** 해시로 조회 키를 만든다. 단순 sha256은 전화번호
      경우의 수(1억 수준)를 전수조사로 복원할 수 있다
- [ ] 이메일은 저장·조회 양쪽에서 같은 정규화 함수를 통과시킨다. 안 하면 `" Test@x.com "`과
      `"test@x.com"`이 별개 계정이 되어 "가입은 됐는데 로그인이 안 되는" 상태가 된다
- [ ] 아이디 찾기 응답은 마스킹된 이메일만 준다
- [ ] 로그·예외 메시지에 개인정보를 남기지 않는다 (`redact()`)
- [ ] 탈퇴 시 파기 정책이 정해져 있다 (즉시 하드삭제 / 유예 후 purge). 통계가 필요하면
      식별정보 없는 형태로만 (개인정보보호법 제28조의2)

### 동의 (개인정보보호법)

- [ ] 동의 근거가 **서버 DB**에 남는다. 프론트 localStorage나 체크박스 통과만으로는 근거가 없다
      (한 레포는 4개 항목 체크박스가 스텝 게이트일 뿐 DB에 컬럼이 없었다)
- [ ] 무엇에, **어느 버전**에, 언제 동의했는지가 남는다. boolean 하나로는 약관 개정 이력을 증명 못 한다
- [ ] 약관 개정 시 버전을 올리고, 구버전 동의는 재동의로 유도한다
- [ ] `version`/`is_required`는 클라이언트가 보낸 값이 아니라 서버 카탈로그 값으로 저장한다
- [ ] 필수 동의는 철회 불가(탈퇴로 안내), 선택 동의는 철회 가능 + 철회 시각 기록
- [ ] 만14세 미만 차단이 **서버에** 있다. 앱에만 있으면 API 직접 호출로 뚫린다
      (한 레포는 서버 검증 함수가 있는데 호출부가 없는 죽은 코드였다)

### 소셜 로그인

- [ ] ID token을 서명 검증 없이 payload만 꺼내 쓰지 않는다 (누구나 임의 `sub`로 위조 가능)
- [ ] 서명 + `aud`(우리 앱 ID) + `iss` + `exp` + `nonce`를 모두 검증한다.
      `aud`가 빠지면 다른 앱용 유효 토큰을 가져와 쓸 수 있다
- [ ] 검증 통과한 nonce를 **한 번만** 쓰이게 소비한다 (DB 유니크 제약이면 경쟁 조건까지 막힌다)
- [ ] 같은 이메일이 다른 방식으로 이미 가입돼 있으면 자동 연결하지 않는다 (계정 탈취 경로)
- [ ] 소셜 계정은 비밀번호가 없다 → 탈퇴·비밀번호 확인 흐름에서 이를 전제한다.
      한 레포는 소셜 가입자가 비밀번호 재확인을 통과할 수 없어 **탈퇴 자체가 불가능**했다
- [ ] `(provider, provider_uid)` 유니크. 소셜 계정을 User 컬럼이 아니라 별도 테이블로 두면
      한 사용자의 다중 공급자 연결을 나중에 붙일 수 있다

### 요청 빈도 / 잠금

- [ ] 연속 실패 N회 → 잠금. **영구 잠금은 금지** (자력 복구 불가 + 남의 계정 잠그는 DoS)
- [ ] 자동 해제 후에는 실패 카운터를 리셋한다. 안 하면 해제 직후 오타 한 번에 재잠금된다
- [ ] 인증 메일/SMS 발송, 코드 검증, 가입에 빈도 제한이 걸려 있다
- [ ] 여러 계정이 같은 식별자를 공유할 수 있는 구조라면, **대상이 아닌 형제 계정의 실패
      횟수를 올리지 않는다.** 한 레포는 전화번호 로그인에서 후보를 순회하며 검증해, 정확한
      비밀번호로 5번 로그인하면 같은 번호의 다른 역할 계정이 잠겨버렸다.
      부작용 없는 확인을 먼저 하고, 일치한 계정에만 기록한다

### 응답 / 전송

- [ ] 쿠키에 `httpOnly` + `secure` + `samesite`. 삭제할 때 `domain`/`path`가 설정 시와 같아야 실제로 지워진다
- [ ] 보안 헤더(nosniff / X-Frame-Options / Referrer-Policy / CSP)
- [ ] https일 때만 HSTS. http 개발 환경에 걸면 접속이 막힌다
- [ ] 개인정보를 URL 쿼리스트링에 넣지 않는다 (접근 로그·Referer로 유출)

### 운영

- [ ] 비밀값이 코드·git에 없다. 환경변수를 **모듈 상수로 굳히지 않는다** — dotenv를 나중에
      로드하는 배선에서 빈 문자열로 남아 "키 없이 그냥 돌아가는" 상태가 된다
- [ ] 만료 토큰·nonce·유예 지난 탈퇴 계정 정리 작업이 스케줄러에 걸려 있다
- [ ] 인증 실패·잠금·토큰 재사용 탐지가 로그로 남는다 (개인정보는 마스킹해서)

---

## 3. 환경변수

```bash
JWT_SECRET=            # python -c "from security_kit import new_secret; print(new_secret())"
PII_ENCRYPTION_KEY=    # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
PII_HASH_KEY=          # new_secret()
COOKIE_SECURE=true     # 로컬 http 개발만 false
COOKIE_DOMAIN=
```

`PII_ENCRYPTION_KEY`를 잃으면 암호화된 이름·전화번호를 **영구히 복호화할 수 없다.**
키 관리(백업·교체 절차)를 배포 문서에 반드시 남길 것. 교체는 `MultiFernet([new, old])`로
읽기 호환을 유지하며 배치 재저장하는 방식.

## 4. 알려진 한계

- `RateLimiter`·`NonceStore`는 프로세스 로컬 메모리다. 워커가 여러 개면 실효 한도가 워커 수만큼
  늘어난다. 정확한 전역 제한이 필요하면 Redis(`INCR`+`EXPIRE`, `SETNX`)로 교체 — 인터페이스는
  그대로 두고 내부만 바꾸면 된다. nonce는 DB 유니크 제약 방식이 더 견고하다
  (`auth_kit.models.OAuthNonce` 참고).
- `RateLimiter.sweep()`을 호출하지 않으면 활성 키만큼 메모리를 쓴다. 스케줄러에 걸어둘 것.
- CSRF 토큰은 없다. `samesite=lax` + Authorization 헤더 방식이면 대부분 충분하지만,
  쿠키만으로 상태 변경 요청을 인증한다면 별도 CSRF 토큰이 필요하다.
- `EncryptedStr`은 결정적 암호화가 아니라(같은 값도 매번 다른 암호문) 검색·정렬이 불가능하다.
  범위 검색까지 필요하면 애플리케이션 레벨 암호화보다 DB의 투명 암호화(TDE)를 검토할 것.
