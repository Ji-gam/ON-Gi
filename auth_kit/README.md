# auth_kit — 회원가입/인증 드롭인 모듈

AH_04_01 ~ AH_04_04 네 프로젝트의 회원가입 코드를 비교해서, 각자 잘 된 부분만 합친 것.
FastAPI + SQLAlchemy 2.0 async 기준. **백엔드만** 포함(프론트/앱은 미포함).

검증 상태: 자체 테스트 20/20 통과, FastAPI 앱 23개 엔드포인트 HTTP 왕복 확인.

> 품앗이온(ON) 요구사항정의서 v1.2 적용 이력(`docs/decision_log/2026-08-10.md`,
> `docs/tasks/T-ACC-1.md`): 휴대폰 본인확인(§1, REQ-F-ACC-01)과 제재 이력 보존형 탈퇴
> (§6, REQ-F-ACC-11)를 추가했다. User/Profile 분리는 이 프로젝트에 없다 - 대신
> `app/models/children.py`의 Child가 User에 직접 소유된다(`docs/CODING_RULES.md` §2-1).

---

## 1. 5분 배선

```bash
pip install fastapi "sqlalchemy[asyncio]" pyjwt "pydantic[email]" python-dateutil cryptography
# 개발/테스트용
pip install aiosqlite httpx
```

**`security_kit`이 같은 부모 디렉터리에 있어야 한다.** 비밀번호 해시·JWT·개인정보 암호화·
로그인 잠금·보안 쿠키는 모두 그 모듈이 단일 출처이고, auth_kit은 여기에 이 프로젝트의
TTL 정책만 얹는다. 보안 체크리스트도 `security_kit/README.md`에 있다.

`.env` (또는 배포 환경변수):

```bash
JWT_SECRET=<python -c "import secrets;print(secrets.token_urlsafe(48))">   # 32바이트 미만이면 실행 시 에러
PII_ENCRYPTION_KEY=<python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())">
PII_HASH_KEY=<python -c "import secrets;print(secrets.token_urlsafe(32))">
REQUIRE_EMAIL_VERIFICATION=false
REQUIRE_PHONE_VERIFICATION=true
COOKIE_SECURE=true          # 로컬 http 개발에서는 false
COOKIE_DOMAIN=
FRONTEND_BASE_URL=https://myapp.com
GOOGLE_CLIENT_ID=
KAKAO_NATIVE_APP_KEY=
```

`main.py`:

```python
from fastapi import FastAPI
from auth_kit import router as auth_router_mod
from auth_kit.router import auth_router, get_session
from myapp.db import get_db_session      # 프로젝트의 AsyncSession 의존성
from myapp.mailer import send_mail       # async (to, subject, html_body) -> bool

app = FastAPI()
app.include_router(auth_router, prefix="/api/v1")
app.dependency_overrides[get_session] = get_db_session
auth_router_mod.send_email = send_mail   # 안 바꾸면 인증 메일 링크가 로그로만 나간다
auth_router_mod.send_sms = send_text     # 안 바꾸면 본인확인 코드가 로그로만 나간다
```

Alembic `env.py`:

```python
from auth_kit.models import Base
target_metadata = Base.metadata   # 프로젝트 Base와 합칠 거면 같은 Base를 쓰거나 metadata를 병합
```

보호된 엔드포인트에서 로그인 사용자 꺼내기:

```python
from auth_kit.router import CurrentUser

@app.get("/api/v1/me/profile")
async def my_profile(user: CurrentUser):
    return {"nickname": user.nickname}
```

---

## 2. 엔드포인트

| 메서드 | 경로 | 용도 |
|---|---|---|
| GET | `/auth/terms` | 현재 유효한 약관 목록 (가입 화면이 이 `terms_type`/`version`을 되돌려 보낸다) |
| GET | `/auth/available/{email,nickname,phone}` | 중복확인 (가입 폼 onBlur) |
| POST | `/auth/email/verify-request` | 인증 메일 발송 |
| GET | `/auth/email/verify?token=` | 인증 링크 처리 |
| POST | `/auth/phone/verify-request` | 본인확인 코드(OTP) 발송 (REQ-F-ACC-01) |
| POST | `/auth/phone/verify` | 본인확인 코드 검증 |
| POST | `/auth/signup` | 이메일 회원가입 → **201 + 토큰 즉시 발급** |
| POST | `/auth/login` | 로그인 |
| POST | `/auth/token/refresh` | 액세스 토큰 재발급 (로테이션 + 재사용 탐지) |
| POST | `/auth/logout` | 로그아웃 (항상 204) |
| POST | `/auth/social/{google\|kakao}` | 소셜 로그인. 신규는 `signup_token`만 |
| POST | `/auth/social/complete` | 소셜 신규 가입 완료 (추가정보 + 동의) |
| POST | `/auth/guest` | 체험하기(게스트) |
| GET/POST | `/auth/me/agreements` | 동의 현황 / 제출·갱신 |
| DELETE | `/auth/me/agreements/{terms_type}` | 선택 동의 철회 |
| POST | `/auth/me/onboarding/complete` | 온보딩 완료 |
| POST | `/auth/find-email` | 아이디 찾기 (마스킹 이메일) |
| POST | `/auth/password/reset-request`, `/auth/password/reset` | 비밀번호 재설정 |
| DELETE | `/auth/me` | 회원탈퇴 |
| POST | `/auth/me/withdraw/cancel` | 탈퇴 취소 (유예기간 내) |

### 가입 흐름 (이메일)

```
GET  /auth/terms                     → 약관 목록을 화면에 그린다
GET  /auth/available/email|nickname  → onBlur마다 중복확인
POST /auth/email/verify-request      → 메일 발송
GET  /auth/email/verify?token=       → 사용자가 링크 클릭
POST /auth/phone/verify-request      → OTP 발송 (REQ-F-ACC-01)
POST /auth/phone/verify              → 코드 확인
POST /auth/signup                    → 201 + access_token + refresh 쿠키
                                       (프론트가 로그인을 다시 부를 필요 없음)
→ onboarding_status = profile_required 이므로 아동/보호자 프로필 화면으로
```

### 가입 흐름 (소셜)

```
POST /auth/social/google  {id_token, nonce}
   ├─ 기존 사용자 → is_new_user=false + access_token + refresh 쿠키
   └─ 신규       → is_new_user=true  + signup_token (계정은 아직 없음)
                     ↓
POST /auth/social/complete {signup_token, nickname, birth_date, gender, agreements}
                   → 201 + 토큰
```

소셜 콜백에서 곧바로 계정을 만들지 않는 이유: 공급자는 생년월일과 약관 동의를 주지 않는다.
그대로 만들면 **만14세 확인과 필수 동의를 건너뛴 계정**이 생긴다.

---

## 3. 네 프로젝트에서 무엇을 가져왔는지

| 기능 | 출처 | 채택 이유 |
|---|---|---|
| 계정/개인정보 분리 사고, 동의 타임스탬프, refresh 로테이션 + 재사용 탐지, 자격증명 zero-width 정리 | 01 | 토큰 탈취 탐지까지 하는 유일한 구현 |
| PII Fernet 암호화 + 조회용 phone_hash, 실시간 중복확인 엔드포인트, 탈퇴 30일 유예 | 02 | 건강정보 서비스에서 이름·전화번호 평문 저장은 위험 |
| 이메일 인증 필수, 닉네임 unique, 강한 비밀번호 정책, 소셜 2단계 가입, 아이디 찾기 | 03 | 가입 관문이 가장 두꺼웠던 구현 |
| 약관 정적 카탈로그 + **버전 관리**(구버전 409), `onboarding_status` 상태머신, ID token 서버 검증 + nonce 소비, 게스트 로그인 | 04 | 동의 개정 이력을 유일하게 다룬 구현 |

### 서로 어긋났던 부분을 어떻게 통일했는지

- **비밀번호 정책**: 01만 대문자를 안 받았다 → 강한 쪽(대·소·숫·특 8자↑)으로 통일. `config.PASSWORD_REQUIRE_UPPERCASE`로 조절.
- **동의 저장**: 02는 서버에 아예 안 남기고, 03은 boolean, 01은 타임스탬프, 04는 버전+테이블 → **04 방식으로 통일**. boolean만으로는 약관 개정 시 "무엇에 동의했는지"를 증명할 수 없다.
- **소셜 계정**: 01은 `users.sns_provider/sns_id` 컬럼 → `SocialAccount` 테이블로 분리. 컬럼 방식은 한 사용자가 구글+카카오를 동시에 연결하는 걸 나중에 못 붙인다.
- **이메일 최대 길이**: 네 곳 모두 40자 → **254자**(RFC 5321). 40자는 실제로 존재하는 긴 회사 이메일의 가입을 막는다.
- **가입 후 자동 로그인**: 네 곳 모두 프론트가 signup 직후 login을 한 번 더 호출했다 → signup 응답에 토큰을 바로 담는다. 두 번째 호출 실패가 "계정은 생겼는데 가입 실패"로 보이는 문제가 사라진다.
- **비밀번호 해시**: bcrypt/passlib 대신 stdlib `hashlib.scrypt` + 버전 프리픽스. 의존성이 하나 줄고, `needs_rehash()`로 argon2 등으로 점진 이전이 가능하다.
- **죽은 코드**: 04의 `validate_password`/`validate_phone_number`는 복사만 되고 호출부가 없었다 → 실제로 스키마에 연결했다.

---

## 4. 정책 조절 (`config.py`)

| 값 | 기본 | 비고 |
|---|---|---|
| `PASSWORD_MIN_LENGTH` / `PASSWORD_REQUIRE_UPPERCASE` | 8 / True | |
| `MIN_SIGNUP_AGE` | 14 | 가입자(보호자) 본인의 나이 하한. 미만은 가입 차단 |
| `REQUIRE_EMAIL_VERIFICATION` | false | true면 이메일 인증 완료 전 가입 차단 |
| `REQUIRE_PHONE_VERIFICATION` | true | false면 본인확인 없이 바로 가입 (REQ-F-ACC-01) |
| `PHONE_VERIFICATION_TTL` | 5분 | OTP 유효시간 |
| `MAX_LOGIN_ATTEMPTS` / `LOCKOUT_DURATION` | 5 / 15분 | 영구 잠금은 쓰지 말 것(DoS + 자력복구 불가) |
| `ACCESS_TOKEN_TTL` / `REFRESH_TOKEN_TTL` | 30분 / 14일 | |
| `WITHDRAWAL_GRACE` | 30일 | `timedelta(0)`이면 즉시 완전 삭제(제재 계정이면 phone_hash만 남김, REQ-F-ACC-11) |

약관을 바꿀 때는 `terms_catalog.py`만 고친다. **문안을 수정하면 반드시 `version`을 올린다** —
안 올리면 "무엇에 동의했는지"의 근거가 사라지고, 올리면 기존 사용자가 자동으로 재동의 대상이 된다.
`GUARDIAN_CONSENT`는 가입 시점 필수가 아니다 - 아동을 등록하려는 사용자만 그 직전에
제출하면 된다(`app/services/child_service.py`가 확인한다).

스케줄러에 붙일 것 두 개:

```python
await AuthService(session).purge_deactivated()      # 유예 지난 탈퇴 계정 물리 삭제
await AuthService(session).purge_expired_tokens()   # 만료 토큰/nonce 정리
```

---

## 5. 테스트

```bash
python -m auth_kit.test_auth_kit
```

검증 대상: 비밀번호 정책, 해시 왕복·손상 해시 내성, 만14세 게이트, 정규화, JWT 타입 혼동,
가입 happy path, 이메일·휴대폰 인증 강제, 잘못된 OTP 거부, 중복 3종 409, 약관 검증(400/409)
및 개정 후 재동의, 선택 동의 철회·필수 철회 차단, 로그인 잠금, refresh 로테이션·재사용 탐지,
로그아웃 멱등성, 재설정 후 전 세션 무효화, 게스트·탈퇴·탈퇴취소, 제재 이력 재가입 차단,
아이디 찾기 마스킹.

---

## 6. 의도적으로 넣지 않은 것

- **본인확인 코드는 이 모듈이 발송하지 않는다** — `send_sms`가 기본으로는 로그만 남긴다.
  실제 SMS 발송(PASS/NICE 등 유료 서비스 또는 통신사 API)은 프로젝트가 주입한다
  (§1 배선 참고). OTP 발급·검증·시도횟수 제한 자체는 이미 구현돼 있다.
- **다중 계정 유형** (환자/보호자/기관) — 이 서비스는 보호자만 로그인 계정을 가진다
  (아동은 `app/models/children.py`의 Child, 계정 없음). 여러 계정 유형이 필요해지면 `User`에
  `account_type` 컬럼을 추가하고 중복 유니크를 `(email, account_type)`으로 바꾼다.
- **웹 리다이렉트 OAuth** — 이 모듈은 앱 SDK의 ID token 검증 방식만 구현했다. 웹이라면
  authorization code 교환 후 `SocialProfile`을 만들어 `AuthService.social_login()`에 넘기면
  그 뒤 로직(계정 연결·2단계 가입)은 그대로 재사용된다.
- **신고 확정 판정 자체** — `AuthService.record_sanction(user_id, reason)`은 운영자(ADM) 도메인이
  신고를 확정했을 때 호출하는 훅이다. 신고 접수·조사·확정 워크플로 자체는 이 모듈 범위 밖.
- **관리자 약관 관리 화면** — 약관 목록이 코드 상수라 배포로 바뀐다.

## 알려진 한계

- 비밀번호 재설정 토큰은 JWT라서 **만료 전에는 여러 번 쓸 수 있다.** 1회용으로 막아야 하면
  `PasswordResetToken` 테이블(`used_at`)을 추가해 `hash_token`으로 조회·소비하는 방식으로 바꾼다
  (이메일 인증 토큰은 이미 그 방식이다).
- 중복확인 → 가입 사이의 경쟁 조건은 DB 유니크 제약이 최종 방어선이다(`IntegrityError` → 409).
- `EncryptedStr` 컬럼은 `WHERE`/정렬/`LIKE`가 불가능하다. 검색이 필요한 값은 `phone_hash`처럼
  해시 컬럼을 따로 둔다. 그래서 `find_email`은 이름이 아니라 닉네임으로 조회한 뒤 이름을 대조한다.
- 로그인 실패 잠금은 계정 단위다. 인증 메일 발송·코드 검증 같은 경로의 빈도 제한은
  `security_kit.RateLimiter`를 라우터에 직접 걸어 쓴다(이 모듈은 기본으로 걸어두지 않았다 —
  적용 지점과 한도가 서비스마다 달라서다). 사용법은 `security_kit/README.md` 1절 참고.
