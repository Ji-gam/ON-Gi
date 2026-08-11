# Task Contract T-CAR-1 (돌봄 요청 생성·수락·거절)

### 참조
- 담당: 백엔드(`docs/SQUAD_MAP.md` §2, 접두어 `car_*`)
- 관련 REQ: REQ-F-CAR-01(요청 생성, 상보 시간대만 선택 가능), REQ-F-CAR-02(수락/거절 시 CONFIRMED
  전이+알림), REQ-F-MAT-07(수락 시 L1 부여+채팅 오픈 — 이 Task에서는 상태머신/채팅 본체가 아닌
  훅 지점만 마련. 실제 등급 판정은 T-TRS-2, 채팅은 T-COM-1 범위)
- 선행: T-SCH-1(`work_schedules`, 48슬롯 비트마스크), T-MAT-1(매칭 후보 조회) — 둘 다 dev 머지 완료

### 목표 (요구사항정의서 원문)
- REQ-F-CAR-01: "일시·시간·장소·대상 아동·특이사항을 입력해 요청을 생성한다. 상보 가능
  시간대만 선택 가능하도록 캘린더를 제한한다." 성공요건: "상보 시간이 아닌 구간은 선택 불가로
  비활성화된다."
- REQ-F-CAR-02: "제공자가 요청을 수락하면 세션이 확정되고 양측에 알림이 발송된다." 성공요건:
  "수락 시 세션 상태가 CONFIRMED로 전이된다."

### 완료 정의
- [x] `app/models/care_session.py`: `CareSession`(requester_id/provider_id FK, care_date,
      start_slot/end_slot(0~47 48슬롯 인덱스), status Enum(REQUESTED/CONFIRMED/REJECTED))
- [x] 생성 시 [start_slot,end_slot) 전 구간이 "제공자 가용(bit=1)+요청자 불가(bit=0)" 상보
      조건을 만족하지 않으면 400 (근무표 미등록 날짜는 풀가용으로 간주, T-MAT-1과 동일 규칙)
- [x] 수락 시 상태가 CONFIRMED로 전이. 알림 발송(T-NTFY 계열)은 미구현이라 범위 밖 —
      전이 지점에 `# TODO(T-CAR-1→T-TRS-2)`로 L1 훅 위치만 주석 표기(실제 등급 컬럼/이벤트는
      추가하지 않음)
- [x] 거절 시 상태가 REJECTED로 전이되며, 동일 두 사용자·날짜로 재요청(새 row 생성) 가능
- [x] 존재하지 않는 세션이거나 본인이 제공자가 아닌 세션 수락/거절 시 404, 이미 CONFIRMED/
      REJECTED인 세션 재처리 시 409
- [x] (공통) 새 테이블은 Alembic 마이그레이션 생성(`a1f3c9d0e2b6_care_session.py`) +
      `docs/dev/ERD.dbml` v1.4 동기화
- [x] (공통) 테스트를 TDD로 먼저 작성(`app/tests/car_apis/**`: 상보 아닌 구간 거절, 상보 구간
      성공, 수락→CONFIRMED+타인 수락 차단, 거절→REJECTED+재요청), `uv run pytest -v` 통과(24 passed)
- [x] (공통) `ruff check .` / `ruff format --check .` / `uv run mypy .` 통과

---

### 허용 경로
```
app/models/care_session.py
app/repositories/care_session_repository.py
app/services/care_session_service.py
app/dtos/care_session_dto.py
app/apis/v1/car_routers.py
app/apis/v1/__init__.py
app/core/db/migrations/versions/**  (신규 리비전 파일만 추가)
app/tests/car_apis/**
docs/dev/ERD.dbml
docs/tasks/T-CAR-1.md
docs/tasks/_active.json (등록/해제만)
```

### 금지 경로
- `auth_kit/**`, `security_kit/**`
- `app/core/utils/**`, `app/models/work_schedule.py` 등 기존 모델 (읽기 전용 재사용만,
  T-MAT-1이 `work_schedule_repository`를 그대로 읽기 재사용한 것과 동일 패턴)

### 의존하는 공유 계약 (읽기만)
- `app/repositories/work_schedule_repository.py` (`WorkScheduleRepository.get`) — 상보 시간대
  검증용
- `app/dependencies` — `get_current_user`

### 자율 판단 / 가정
- 시간 표현은 `start_slot`/`end_slot`(48슬롯 인덱스, work_schedule과 동일 단위)로 통일 — 별도
  datetime 컬럼 없음(단순화, 필요시 후속 Task에서 확장)
- 장소/특이사항(REQ-F-CAR-01 나머지 필드)은 이번 Task 스코프인 "생성·수락·거절 상태 전이"에
  직접 필요하지 않아 제외 — 후속 Task에서 확장
- 알림 발송(REQ-F-CAR-02 "양측에 알림")은 NTFY 도메인 미구현으로 범위 밖

### 반드시 멈춰야 하는 경우 (이 Task에 한정된 추가 조건)
- 신뢰 등급(L1) 실제 전이 로직 구현이 필요해 보이는 경우 (T-TRS-2 범위, 훅 주석만 남기고 멈춤)

---

### 완료 보고
- 완료 정의 체크리스트 결과: 전항목 완료(위 "완료 정의" [x] 참고)
- 가정(Assumptions): 위 "자율 판단 / 가정" 참고. 추가로 — 수락/거절은 요청받은 provider 본인만
  수행 가능하도록 제한(요구사항에 명시는 없으나 신뢰 경계상 당연한 제약, 타인이 수락 시도 시
  404로 응답해 세션 존재 자체를 노출하지 않음). 마이그레이션은 로컬 DB 미기동으로 autogenerate
  대신 기존 `work_schedule` 리비전과 동일 패턴으로 직접 작성(모델 컬럼과 1:1 대응 확인함).
- 공유 계약 변경 필요 사항 (있다면): 없음(`work_schedule_repository`는 읽기만, T-MAT-1과 동일
  재사용 패턴)
- 브랜치명: `feature/T-CAR-1-care-session`
