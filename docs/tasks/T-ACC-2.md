# Task Contract T-ACC-2 (보호자 프로필 등록)

### 참조
- 담당: 백엔드(`docs/SQUAD_MAP.md` §1, 접두어 `acc_*`)
- 관련 REQ: REQ-F-ACC-04, REQ-NF-SEC-05(정확좌표 대신 H3 인덱스만 저장)
- 선행: T-ACC-1(`docs/tasks/T-ACC-1.md`, dev 머지 완료) — `auth_kit.models.User`, `app/models/children.py` 전제

### 목표 (요구사항정의서 원문)
- REQ-F-ACC-04: "거주지(H3 셀로 변환 저장), 직군, 근무 형태, 가구 구성, 보유 태그(응급처치 이수·비흡연·
  차량 보유 등)를 등록한다." 성공요건: "입력한 주소가 좌표가 아닌 H3 인덱스로 저장된다."
- MAT 도메인(REQ-F-MAT-02/03)의 하드필터 입력값이 되므로 스키마는 이번에 확정하되, 매칭 로직 자체는
  범위 밖(T-MAT-*에서 소비).

### 완료 정의
- [x] `app/models/guardian_profile.py`: `GuardianProfile`(user_id FK 1:1, residence_h3, job_category,
      work_type, household_composition) + `GuardianTag`(user_id FK, tag_code) 다대다 신설
- [x] `app/repositories/guardian_profile_repository.py`, `app/services/guardian_profile_service.py`:
      H3 인덱스 형식 검증(h3 패키지), upsert(최초 등록/수정 겸용)
- [x] `app/dtos/guardian_profile_dto.py`: 요청/응답 스키마, enum 값 정의
- [x] `app/apis/v1/acc_routers.py`에 `PUT/GET /api/v1/acc/guardian-profile` 추가
- [x] Alembic 마이그레이션 생성/적용(`9d344b799f53_guardian_profile.py`, `ai_health_on` DB에 upgrade 확인),
      `docs/dev/ERD.dbml` v1.1 갱신(§6)
- [x] (공통) 테스트 작성(`app/tests/acc_apis/test_guardian_profile_service.py`, 4건),
      `uv run pytest app/tests -v` 7/7 통과
- [x] (공통) `ruff check .` / `ruff format --check .` 통과

### 허용 경로
```
app/models/guardian_profile.py
app/repositories/guardian_profile_repository.py
app/services/guardian_profile_service.py
app/dtos/guardian_profile_dto.py
app/apis/v1/acc_routers.py
app/models/__init__.py
app/core/db/migrations/versions/**
docs/dev/ERD.dbml
app/tests/acc_apis/**
pyproject.toml (h3 의존성 추가만)
docs/tasks/T-ACC-2.md
docs/tasks/_active.json (등록/해제만)
```

### 금지 경로
- `auth_kit/**`, `security_kit/**` (공유 패키지, User 모델에 컬럼 직접 추가하지 않음 — 대신
  `guardian_profiles` 신규 테이블로 분리)
- `app/models/children.py`, `app/services/child_service.py` 등 T-ACC-1 산출물

### 자율 판단 / 가정 (Assumptions)
- **직군/근무형태/가구구성/보유태그 세부 enum 값**: 요구사항정의서(v1/v1.1/v1.2)에 예시(응급처치 이수·
  비흡연·차량 보유)만 있고 전체 목록은 미정. `job_category`/`work_type`/`household_composition`은
  최소 실사용 가능한 값으로 우선 정의하고(StrEnum), `docs/tasks/_active.json` 및 이 문서에 "확정 아님,
  MAT 설계 시 재검토" 명시.
- **보유 태그**: MAT-03의 "필수 태그 10개(완화불가 4종 포함)" 중 완화불가 4종 중 "알레르기 대응·투약
  관리"는 Child 쪽 데이터에서 파생되고, "응급처치 이수·비흡연 가정"은 User(보호자) 소유 태그다. 선택
  6종은 미정이므로 고정 Enum 대신 `guardian_tags(user_id, tag_code)` 확장 가능 테이블로 저장한다
  (사용자 승인, `docs/tasks/T-ACC-2.md`가 SSOT).
- User 모델 확장 대신 신규 테이블 `guardian_profiles`로 분리(사용자 승인) — auth_kit(공유 패키지) 비수정.
- H3 변환/검증에 `h3` PyPI 패키지를 `app` 의존성 그룹에 신규 추가(사용자 승인). 클라이언트가 위경도가
  아닌 H3 문자열을 그대로 보내는 것을 전제로 하되, 서버에서 `h3.is_valid_cell`로 형식을 검증한다.
- resolution(H3 해상도)은 REQ-F-MAT-02 "반경 1km"와의 정합을 위해 9(≈150m 셀 한 변)로 가정.

### 공유 계약 변경 필요 사항
- 없음 (User는 변경하지 않고 신규 테이블로 분리)

### 완료 보고
- 브랜치명: `feature/T-ACC-2-guardian-profile`
