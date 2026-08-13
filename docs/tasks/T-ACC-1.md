# Task Contract T-ACC-1 (회원가입/인증/보안 모듈 도입)

> **이력**: 최초 작성 시(원래 `T-AUTH-1`) 아직 요구사항정의서가 없어 무관한 ReMedi 템플릿의
> User/Profile(`profile_id`) 규칙을 따랐다. 2026-08-10에 품앗이온 요구사항정의서 v1.2 기준으로
> User→Child 직접소유 구조·휴대폰 본인확인·법정대리인 동의·제재 이력 보존형 탈퇴를 다시
> 구현했다(아래 완료 정의는 이 재작업 기준). 배경: `docs/decision_log/2026-08-10.md`.

### 참조
- 담당: 백엔드(`docs/SQUAD_MAP.md` §1, 접두어 `acc_*`)
- 출처: `D:\Personal\auth_kit`, `D:\Personal\security_kit` (4개 선행 프로젝트 회원가입 구현 비교 통합본)
- 관련 REQ: REQ-F-ACC-01/02/03/05/06/09/11, REQ-NF-SEC-01/03/05, REQ-NF-LAW-01/02/03

### 목표
- 이메일/소셜(구글·카카오 ID token)/게스트 회원가입 + 휴대폰 본인확인, 로그인, refresh
  로테이션+재사용 탐지, 약관 버전관리, 아동(Child) 등록(법정대리인 동의 게이트), 회원탈퇴
  (유예 + 제재 이력 보존)까지 ACC 도메인 백엔드를 도입한다.
- `docs/CODING_RULES.md` §2-1 User→Child 직접소유 구조를 만족시킨다(Profile 없음).

### 완료 정의
- [x] `security_kit`(도메인 무관 보안 프리미티브) + `auth_kit`(회원가입/인증 도메인) 프로젝트 루트에 도입
- [x] `auth_kit.models.Base` → 프로젝트 공유 `app.models.base.Base`로 일원화 (Alembic 단일 metadata)
- [x] `app/models/children.py`: `Child`(user_id FK 직접소유) + `ChildSensitiveInfo`(물리분리+암호화) 신설
- [x] `app/services/child_service.py`: 아동 등록은 `GUARDIAN_CONSENT` 동의 확인 후에만 허용(REQ-F-ACC-03),
      소유자 아닌 조회/삭제는 404(REQ-F-ACC-05/06)
- [x] `app/apis/v1/acc_routers.py`: `/api/v1/acc/children` CRUD, `app/dependencies.get_current_user` 사용
- [x] 휴대폰 본인확인(REQ-F-ACC-01): `PhoneVerificationToken`, `/auth/phone/verify-request`,
      `/auth/phone/verify`, 가입 전제조건으로 `signup`/`complete_social_signup`에 게이트 추가
- [x] 제재 이력 보존형 탈퇴(REQ-F-ACC-11): `User.is_sanctioned`, `AuthService.record_sanction()`,
      `SanctionedIdentity`(phone_hash), 물리삭제(`withdraw`/`purge_deactivated`) 직전 봉인 + 재가입 차단(403)
- [x] `terms_catalog.py`: ReMedi 잔재(`sensitive_health`/`ai_chat`) 제거, `location`(REQ-NF-LAW-02)
      +`guardian_consent`(REQ-F-ACC-03, 가입시점 비필수) 추가
- [x] JWT/응답 바디에서 `profile_id` 전부 제거 - `sub`(user_id)만 담는다
- [x] `app/apis/v1`에 `auth_router`+`acc_router` 등록, `app/main.py`에 `get_session` 의존성 오버라이드
- [x] `security_kit.test_security_kit` 24/24, `auth_kit.test_auth_kit` 20/20, `pytest app/tests` 3/3 통과
- [x] `ruff check`/`ruff format` 통과 (신규/수정 파일)
- [x] `TestClient`로 실제 호출 확인: 본인확인 → 가입(profile_id 없음 확인) → 법정대리인 동의 →
      아동 등록(민감정보 암호화 저장·목록에는 미노출) 전체 흐름
- [x] Alembic 마이그레이션 생성 — `app/core/db/migrations/versions/ff9d99f5db23_auth_kit_children_초기_스키마.py`,
      `mysql` 컨테이너의 `ai_health_on` DB(같은 컨테이너에 이미 다른 워크트리용 `ai_health` DB가
      옛 ReMedi 스키마로 떠 있어 이름 충돌 회피)에 `alembic upgrade head` 적용 확인
- [x] `docs/dev/ERD.dbml` 신규 작성 — 위 마이그레이션의 10테이블 전부 반영(v1.0)
- [ ] 프로젝트 메일러/SMS 게이트웨이 연결 — 현재 `send_email`/`send_sms`는 로그 stub(`app/main.py`의 TODO 참고).
      우선순위 낮춤(5주 MVP, 비용 제약 감안 발표 직전 연결 가능)

### 후속 필요 (T-ACC-2로 분리, 이 계약 범위 밖)
- REQ-F-ACC-04 보호자 프로필 확장(거주지 H3 인덱스, 직군, 근무형태, 가구구성, 보유태그) —
  MAT 도메인의 하드필터 입력값이라 그때 같이 설계하는 편이 나음
- REQ-F-ACC-07/08/10 바움린드 8문항 진단 + 자유서술 LLM 보정 — AI(`ai_worker`) 담당 영역과 맞물림
- ADM 도메인의 신고 접수→확정 워크플로 — `AuthService.record_sanction()`은 훅만 만들어둠

### 가정 (Assumptions)
- 휴대폰 본인확인은 실제 PASS/NICE 계약 없이 자체 OTP(6자리, 5분 TTL, 5회 시도 제한)로
  구현했다 - `send_sms`를 실제 SMS 게이트웨이로 교체하면 그대로 동작한다(5주 MVP, 비용 제약).
- `record_sanction()`을 호출할 ADM 신고 확정 기능이 아직 없어, 이 Task에서는 서비스 메서드와
  탈퇴 시 봉인 로직만 만들고 자체 테스트로 흐름을 검증했다(`test_sanctioned_identity_blocks_resignup`).
- `security_kit.security_headers_middleware`는 `app`(FastAPI 인스턴스)을 순수 ASGI 콜러블로
  감싸버려 `app.main.app`의 타입이 바뀌는 부작용이 있어 배선하지 않음. 운영 반영 시 uvicorn
  실행 지점(`uvicorn.run(security_headers_middleware(app), ...)`)에서 감싸는 방식을 권장.
- 소셜 로그인 실제 클라이언트 시크릿/카카오 앱키는 비워둠(운영 배포 시 채움).

### 공유 계약 변경 필요 사항
- `app/models/__init__.py`, `app/dependencies/__init__.py`, `app/apis/v1/__init__.py`,
  `app/main.py`, `pyproject.toml`, `envs/example.*.env` 를 이 Task에서 직접 수정함
  (인증 도입 자체가 이 공유 파일들에 처음 내용을 채우는 작업이라 불가피).

### 완료 보고
- 브랜치명: (미생성 — 워크트리 작업 중)
