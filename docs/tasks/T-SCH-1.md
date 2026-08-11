# Task Contract T-SCH-1 (근무표 최소 스키마 - 48슬롯 비트마스크)

### 참조
- 담당: 백엔드(`docs/SQUAD_MAP.md` §1, 접두어 `sch_*`)
- 관련 REQ: REQ-F-SCH-01(근무 템플릿 선택), REQ-F-SCH-03(48슬롯 비트마스크 변환),
  REQ-F-SCH-06(자정 경계 근무 슬롯 규칙)
- 선행: T-ACC-1(dev 머지 완료, `auth_kit.models.User` 전제)
- 후속 소비자: T-MAT-1(REQ-F-MAT-01 상보 시간 계산이 이 도메인의 비트마스크를 입력값으로 씀)

### 목표 (요구사항정의서 원문)
- REQ-F-SCH-01: "3교대(주간 07–15/저녁 15–23/야간 23–07), 2교대, 주간 고정, 격일제 등 사전
  정의된 템플릿 중에서 선택해 등록한다." 성공요건: "템플릿 선택만으로 근무 유형이 저장된다."
- REQ-F-SCH-03: "등록된 근무 일정을 30분 단위 48칸의 돌봄 가능/불가 비트마스크로 변환해
  날짜별로 저장한다." 성공요건: "주간조 07–15 등록 시 해당 슬롯이 0으로 마스킹된다."
- REQ-F-SCH-06: "야간조 23–07처럼 자정을 넘기는 근무는 근무 시작일과 종료일 양쪽의 48슬롯에
  나누어 반영한다(귀속 규칙: 근무 시작일 기준)." 성공요건: "야간조 23–07 등록 시 당일 슬롯
  46–47과 익일 슬롯 0–13이 모두 불가로 마스킹된다."

### 완료 정의
- [x] `app/core/utils/schedule_slots.py`: SLOT_COUNT=48, `ShiftTemplate` StrEnum(DAY/EVENING/
      NIGHT/OFF), 템플릿→(당일마스크변경, 익일마스크변경) 순수 함수, 풀가용 마스크 상수
- [x] `app/models/work_schedule.py`: `WorkSchedule`(user_id FK, work_date, slot_bitmask
      BigInteger, shift_template, created_at/updated_at), UniqueConstraint(user_id, work_date)
- [x] `app/repositories/work_schedule_repository.py`, `app/services/work_schedule_service.py`:
      템플릿 등록(NIGHT는 당일+익일 두 행에 걸쳐 upsert), 기간 조회
- [x] `app/dtos/work_schedule_dto.py`: 요청/응답 스키마
- [x] `app/apis/v1/sch_routers.py`: `PUT /api/v1/sch/schedule`, `GET /api/v1/sch/schedule`
      (기간 조회), `app/apis/v1/__init__.py`에 등록
- [x] Alembic 마이그레이션 생성/적용(`work_schedules` 테이블), `docs/dev/ERD.dbml` v1.3 갱신
- [x] (공통) 테스트 작성(`app/tests/sch_apis/**`), `uv run pytest app/tests -v` 통과
- [x] (공통) `ruff check .` / `ruff format --check .` / `uv run mypy .` 통과

### 허용 경로
```
app/core/utils/schedule_slots.py
app/models/work_schedule.py
app/repositories/work_schedule_repository.py
app/services/work_schedule_service.py
app/dtos/work_schedule_dto.py
app/apis/v1/sch_routers.py
app/apis/v1/__init__.py
app/models/__init__.py
app/core/db/migrations/versions/**
docs/dev/ERD.dbml
app/tests/sch_apis/**
docs/tasks/T-SCH-1.md
docs/tasks/_active.json (등록/해제만)
```

### 금지 경로
- `auth_kit/**`, `security_kit/**` (공유 패키지)
- `app/models/guardian_profile.py`, `app/models/parenting_values.py` 등 T-ACC-2/3 산출물

### 자율 판단 / 가정 (Assumptions)
- **비트마스크 의미**: bit=1(가용/돌봄 가능), bit=0(근무 중/불가). slot idx는 00:00 시작
  30분 단위(idx0=00:00-00:30 ... idx47=23:30-24:00). 요구사항정의서에 비트값 방향 명시가
  없어, MAT-01 검증 기준("주간조×저녁조 조합에서 각 16슬롯 산출")과 정합하도록 이렇게 정의.
- **템플릿 범위 축소**: REQ-F-SCH-01이 언급한 "2교대·격일제" 등은 이번 스텝(MAT 하드필터+정렬
  MVP까지)에 필요한 최소 집합인 3교대(DAY/EVENING/NIGHT)+OFF만 우선 구현. 나머지 템플릿은
  후속 Task로 미룸(사용자 승인 - MAT 스코프를 "필수 하드필터+정렬"로 한정).
- **REQ-F-SCH-02(달력 UI 반복입력)/04(수면·회복 자동반영)/05(변경시 매칭 재계산 트리거)는
  범위 밖**: 02는 프론트엔드 화면, 04는 별도 규칙 엔진(요구사항정의서에 "규칙" 상세 없음),
  05는 MAT 도메인이 방금 생기는 참이라 재계산 훅 자체가 아직 없음. 셋 다 후속 Task.
- **일자별 1행 upsert**: NIGHT 템플릿 등록 시 당일 행(46-47 슬롯 불가로 AND)과 익일 행(0-13
  슬롯 불가로 AND)을 각각 get-or-create(없으면 풀가용 마스크로 시작)한 뒤 갱신한다. 같은
  날짜에 여러 템플릿을 겹쳐 등록하는 시나리오(예: 이미 EVENING인 날에 NIGHT 익일영향 추가)는
  비트 AND로 자연 병합되지만, 상충 검증(같은 시간대 중복 등록 경고)은 하지 않는다(MVP 범위 밖).

### 후속 필요 (범위 밖)
- REQ-F-SCH-01 나머지 템플릿(2교대/격일제) 추가
- REQ-F-SCH-02(달력 UI), 04(수면·회복 자동 반영), 05(변경 시 매칭 재계산 트리거) 연결

### 완료 보고
- 완료 정의 체크리스트: 전항목 완료(위 "완료 정의" [x] 참고)
- 가정: 위 "자율 판단 / 가정" 참고
- 공유 계약 변경 필요 사항: 없음
- 브랜치명: `feature/T-SCH-1-work-schedule`
