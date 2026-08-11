# Task Contract T-TRS-2 (신뢰 등급 상태머신 L1→L2→L3)

### 참조
- 담당: 백엔드(`docs/SQUAD_MAP.md` §2, 접두어 `trs_*`)
- 관련 REQ: REQ-F-TRS-01(상태머신), REQ-F-TRS-02(공동육아 일정 등록), REQ-F-TRS-03(공동육아
  횟수 설정), REQ-F-TRS-04(단독 위탁 해금)
- 선행: T-CAR-1(`care_sessions` 요청/수락 — L1 부여 트리거), T-TRS-1(`care_evaluations` —
  본 Task와 독립적인 신뢰 점수 축)
- 후속 연동: `care_session_service.accept()`의 `# TODO(T-CAR-1→T-TRS-2)` 훅 해소

### 목표 (요구사항정의서 원문)
- REQ-F-TRS-01: "L1(매칭)→L2(공동육아 진행)→L3(단독 위탁 해금)의 전이를 규칙 기반으로
  판정하며, 역방향 전이(신고 발생 시 강등)도 지원한다." 검증 기준: "조건 미충족 상태에서
  L3 기능 호출 시 서버가 거부한다."
- REQ-F-TRS-02: "키즈카페·공원 등 공개 장소를 선택해 만남 일정을 잡고, 양측이 완료 확인하면
  1회로 집계한다." 검증 기준: "완료 확인 3회 누적 시 L3 조건이 충족된다."
- REQ-F-TRS-03: "기본 3회를 사용자가 조정할 수 있게 하되, 하한선(1회)을 두어 무제한 완화를
  막는다." 검증 기준: "설정값 변경이 해금 판정 로직에 즉시 반영된다."
- REQ-F-TRS-04: "L3 도달 시에만 단독 돌봄 요청 생성 버튼이 활성화된다. 그 전에는 UI와 API
  양쪽에서 차단한다." 검증 기준: "L2 상태에서 단독 요청 API 직접 호출 시 403이 반환된다."
  (원문 그대로: 반드시 라우터 레벨 가드(FastAPI dependency)로 구현 — UI 차단만으로는 완료
  정의 미충족)

### 완료 정의
- [x] `app/models/trust_level.py`: `TrustLevel`(L1/L2/L3) + `TrustRelationship`(사용자 쌍
      단위, unique, level, joint_session_count) + `TrustLevelHistory`(변경 전/후, 변경자
      user_id nullable=시스템 자동, reason, 시각)
- [x] `app/models/joint_care_session.py`: `JointCareSession`(initiator/partner, place,
      scheduled_date, confirmed_by_initiator/partner, status: SCHEDULED/COMPLETED)
- [x] `app/models/trust_settings.py`: `TrustSettings`(user_id PK, required_joint_count 기본 3)
- [x] `care_session_service.accept()`: 수락 시 관계가 없으면 L1 관계를 생성(REQ-F-MAT-07,
      기존 TODO 해소)
- [x] `create_request`에 `is_solo` 플래그 추가(REQ-F-TRS-04). `is_solo=True`(단독 위탁) 요청은
      상대와 L3 관계가 아니면 403 — 일반 재요청(REQ-F-MAT-09)은 영향 없음(아래 "자율 판단"
      §1 참고) — 라우터 레벨(FastAPI dependency)에서도 동일 검사
- [x] 공동육아 일정 등록/완료 확인(REQ-F-TRS-02): 최초 일정 등록 시 L1→L2, 양측 확인 시
      `joint_session_count` 1 증가 및 `required_joint_count` 충족 시 L2→L3
- [x] 공동육아 필요 횟수 설정(REQ-F-TRS-03): 사용자별 설정, 최소값 1 강제, 변경 즉시 해금
      판정에 반영(관계의 필요 횟수 = 양측 설정값 중 큰 값, 아래 "자율 판단" §4 참고)
- [x] 역방향 전이(강등): 관리자(`is_admin`)만 사유를 남기고 등급을 한 단계 낮출 수 있음
      (REQ-F-CAR-07/신고 도메인 미구현이라 관리자 수동 강등으로 대체, 아래 "자율 판단" §5)
- [x] (공통) 새 테이블은 Alembic 마이그레이션 + `docs/dev/ERD.dbml` v1.7 동기화
- [x] (공통) 테스트를 TDD로 먼저 작성(`app/tests/trs_apis/**`: L1 자동 부여, L3 미달 시
      추가 요청 403, 공동육아 등록으로 L2 전이, N회 완료 확인 후 L3 전이, 필요 횟수 설정
      변경 즉시 반영, 관리자 강등+이력, 비관리자 강등 403), `uv run pytest -v` 통과
- [x] (공통) `ruff check .` / `ruff format --check .` / `uv run mypy .` 통과

---

### 허용 경로
```
app/models/trust_level.py            (신규)
app/models/joint_care_session.py     (신규)
app/models/trust_settings.py         (신규)
app/repositories/trust_relationship_repository.py   (신규)
app/repositories/joint_care_session_repository.py    (신규)
app/repositories/trust_settings_repository.py         (신규)
app/services/trust_level_service.py    (신규)
app/services/care_session_service.py   (L1 부여 훅 + L3 게이트 추가)
app/dtos/trust_level_dto.py            (신규)
app/dtos/care_session_dto.py           (게이트 오류 문서화만, 필드 변경 없음)
app/apis/v1/trs_routers.py             (신규 엔드포인트 추가)
app/apis/v1/car_routers.py             (라우터 레벨 가드 의존성 추가)
app/core/db/migrations/versions/**     (신규 리비전 파일만 추가)
app/tests/trs_apis/**                  (신규)
app/tests/car_apis/**                  (L3 게이트 회귀 확인)
docs/dev/ERD.dbml
docs/tasks/T-TRS-2.md
docs/tasks/_active.json (등록/해제만)
```

### 금지 경로
- `auth_kit/**`, `security_kit/**`
- `app/models/care_session.py`, `app/models/care_evaluation.py` (읽기 전용 재사용만)

### 의존하는 공유 계약 (읽기만)
- `app/repositories/care_session_repository.py` — 관계 최초 생성 판단(과거 세션 존재 여부)
- `app/dependencies` — `get_current_user`

### 자율 판단 / 가정
1. **"단독 요청 API"를 별도 플래그로 식별**: REQ-F-MAT-09("완료 이력 있는 상대는 후보 탐색 없이
   곧바로 재요청 가능")가 T-TRS-1 테스트에서 이미 L1 상태의 재요청을 검증하고 있어, `/car/
   requests` 전체를 L3로 게이트하면 기존에 통과하던 시나리오가 깨진다. 따라서 `CareRequestCreate`
   에 `is_solo: bool = False`를 추가해, `is_solo=True`로 명시한 요청만 REQ-F-TRS-04 게이트
   (상대와 L3 관계 필요)를 적용하고, 일반 재요청은 등급과 무관하게 항상 허용한다.
2. **공동육아(JointCareSession)는 `care_sessions`와 별개 모델**: REQ-F-TRS-02는 GPS
   체크인/체크아웃이 아니라 "장소 선택 + 양측 완료 확인"만 요구해 더 가벼운 구조라
   `care_sessions`를 재사용하지 않고 신규 테이블로 분리했다.
3. **L1→L2 전이 시점**: "공동육아 진행 중"이라는 문구를 최초 일정 등록 시점으로 해석해,
   일정을 1건이라도 등록하면 즉시 L2로 전이시켰다(완료 여부와 무관).
4. **필요 횟수의 관계 단위 적용**: REQ-F-TRS-03이 "사용자가 조정"이라고만 명시해 개인별
   설정으로 모델링했다. 관계(두 사용자) 단위로 해금을 판정해야 하므로, 두 사용자의 설정값
   중 더 큰 값을 그 관계의 필요 횟수로 사용한다(한쪽이 임의로 기준을 낮춰 상대의 신뢰 요건을
   무력화하지 못하도록).
5. **역방향 전이(강등)**: REQ-F-TRS-01이 "신고 발생 시 강등"이라고 명시하지만 신고/제재
   도메인이 아직 구현되지 않아, 이번 Task에서는 운영자(`is_admin`)가 사유를 남기고 수동으로
   한 단계 강등하는 API만 제공한다(T-TRS-1의 가중치 변경 이력 패턴과 동일하게 이력 테이블에
   기록). 신고 도메인 완성 후 자동 강등으로 대체 필요(`# TODO`로 표시).
6. **강등 하한선**: L1 아래로는 내려가지 않는다(관계 자체가 해제되는 것은 범위 밖).

### 반드시 멈춰야 하는 경우
- 신고/제재(COM 또는 ADM 도메인) 자동 강등 연동이 필요해 보이는 경우 (범위 밖, 별도 Task)
- Pod 단위 신뢰 등급 집계(REQ-F-TRS-09)가 필요해 보이는 경우 (범위 밖)

---

### 완료 보고
- 완료 정의 체크리스트 결과: 전항목 완료(위 "완료 정의" [x] 참고), `uv run pytest -v` 49
  passed(회귀 없음), `ruff check`/`ruff format --check`/`uv run mypy .` 모두 통과
- 가정(Assumptions): 위 "자율 판단 / 가정" 참고
- 공유 계약 변경 필요 사항: `app/dtos/care_session_dto.py`의 `CareRequestCreate`에 `is_solo`
  필드 추가(기본 False, 기존 클라이언트 호환), `app/apis/v1/car_routers.py`의
  `/car/requests`에 라우터 레벨 가드 의존성 추가 — 두 파일 모두 T-CAR-1 소유였으나 단일
  백엔드 담당자 체제(SQUAD_MAP v3.0)라 별도 조율 불필요, 기록으로만 남김
- 브랜치명: `feature/T-TRS-2-trust-level-fsm`
