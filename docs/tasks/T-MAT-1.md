# Task Contract T-MAT-1 (매칭 후보 - 하드필터+종합점수 정렬)

### 참조
- 담당: 백엔드(`docs/SQUAD_MAP.md` §1, 접두어 `mat_*`)
- 관련 REQ: REQ-F-MAT-01(상보 시간 계산), REQ-F-MAT-02(거리 하드필터), REQ-F-MAT-03(태그
  하드필터), REQ-F-MAT-05(종합 점수/정렬), REQ-F-MAT-12(가치관·시간 2축 분리 제시)
- 선행: T-ACC-2(`guardian_profiles`/`guardian_tags`), T-ACC-3(`parenting_values_profiles`),
  T-SCH-1(`work_schedules`, 48슬롯 비트마스크) — 전부 dev 머지 전제(T-SCH-1은 PR #8 대기 중,
  이 브랜치는 `feature/T-SCH-1-work-schedule`에서 분기해 의존성을 미리 반영)
- AGENTS.md §6 "결정됨": 매칭 총점=가치관유사도35%+상보스코어35%+나머지30%(거리·개월수·신뢰점수)

### 목표 (요구사항정의서 원문)
- REQ-F-MAT-01: "두 사용자의 48슬롯 비트마스크에 AND 연산을 적용해 서로 맡아줄 수 있는 슬롯
  수와 구간을 산출한다." 성공요건: "주간조×저녁조 조합에서 각 16슬롯(8시간)이 산출된다."
- REQ-F-MAT-02: "H3 인덱스 기준 반경 1km(도보 약 10분) 이내의 사용자만 후보로 남긴다."
  성공요건: "1km를 벗어난 계정이 후보 목록에 나타나지 않는다."
- REQ-F-MAT-03: "필수 태그 10개(완화 불가 4종: 알레르기 대응·투약 관리·응급처치 이수·비흡연
  가정 / 선택 6종)를 Set Cover 방식으로 검사한다. 완화 불가 태그는 어떤 경우에도 무시되지
  않는다." 성공요건: "견과류 알레르기 아동은 해당 대응 불가 가정과 매칭되지 않는다."
- REQ-F-MAT-05: "가치관 유사도 35%, 상보 시간량 35%, 나머지 30%(거리·아동 개월 수 유사도·
  신뢰 점수)를 가중 합산해 후보를 정렬한다." 성공요건: "후보 목록이 총점 내림차순으로
  정렬되고, 가치관·시간 기여분이 각각 35%로 계산된다."
- REQ-F-MAT-12: "후보 상세에 가치관 유사도와 상보 스코어를 각각 표시." 성공요건: "두 점수가
  개별 수치로 표시되고, 총점이 같아도 두 축의 조합이 다르게 노출된다."

### 완료 정의
- [x] `app/core/utils/matching_weights.py`: 가중치 상수(VALUES=0.35/COMPLEMENTARY=0.35/
      DISTANCE=0.10/AGE=0.10/TRUST=0.10, 합=1.0)
- [x] `app/core/utils/guardian_tags.py`: `ALLERGY_RESPONSE`/`MEDICATION_MANAGEMENT` 태그
      코드 추가(완화불가 4종 중 아동 파생 2종)
- [x] `app/repositories/guardian_profile_repository.py`: 후보 조회용 `list_all_except(user_id)`
      추가
- [x] `app/services/matching_service.py`: 거리(H3→위경도 haversine, 1km 하드컷)+태그(Set
      Cover 서브셋 검사, 완화불가 태그 항상 포함) 하드필터 → 가치관유사도/상보스코어/거리
      /개월수유사도/신뢰점수(스텁) 가중합산 → 총점 내림차순 정렬
- [x] `app/dtos/matching_dto.py`, `app/apis/v1/mat_routers.py`: `GET /api/v1/mat/candidates`
      (본인 보호자 프로필 미등록 시 400)
- [x] `app/apis/v1/__init__.py`에 라우터 등록. DB 신규 테이블 없음(순수 계산) — 마이그레이션
      불필요, ERD.dbml 변경 없음
- [x] (공통) 테스트 작성(`app/tests/mat_apis/**`: 거리 하드필터, 완화불가 태그 필터, 종합점수
      정렬, 가치관/상보 점수 개별 노출), `uv run pytest app/tests -v` 통과
- [x] (공통) `ruff check .` / `ruff format --check .` / `uv run mypy .` 통과

### 허용 경로
```
app/core/utils/matching_weights.py
app/core/utils/guardian_tags.py
app/repositories/guardian_profile_repository.py
app/services/matching_service.py
app/dtos/matching_dto.py
app/apis/v1/mat_routers.py
app/apis/v1/__init__.py
app/tests/mat_apis/**
docs/tasks/T-MAT-1.md
docs/tasks/_active.json (등록/해제만)
```

### 금지 경로
- `auth_kit/**`, `security_kit/**`
- `app/models/**`, `app/core/db/migrations/**` (이 Task는 신규 테이블 없이 기존 T-ACC-2/3/
  T-SCH-1 데이터를 읽기만 함)

### 자율 판단 / 가정 (Assumptions)
- **거리 계산**: H3 셀을 `h3.cell_to_latlng`으로 위경도 변환 후 haversine 공식(표준 math만
  사용)으로 실거리(m)를 구해 1000m 이내만 통과시킨다. `h3.grid_disk` 링 근사 대신 정확한
  거리 계산을 택함(과대/과소 필터링 방지).
- **Set Cover 태그 필터 = 단방향 서브셋 검사**: "요청자의 아동이 필요로 하는 태그(완화불가
  중 아동 파생분: 알레르기 대응/투약 관리는 `ChildSensitiveInfo` 유무로 트리거) ⊆ 후보의
  보유 태그"만 검사한다. 완화불가 4종 중 응급처치이수·비흡연가정은 아동 상태와 무관하게
  항상 필요하다고 가정(안전 기준선). 양방향(후보 쪽 아동 요구도 요청자가 충족하는지) 검사는
  범위 밖 — 매칭 요청은 "돌봄을 맡길 후보를 찾는" 단방향 탐색으로 우선 구현(사용자 승인,
  MAT 스코프를 "필수 하드필터+정렬"로 한정).
- **선택 6종 태그**: `docs/tasks/T-ACC-2.md`에서 이미 미확정으로 문서화됨 — 하드필터는 완화불가
  4종만 강제하고, 선택 태그는 이번 Task의 정렬 스코어에 반영하지 않는다(후속 Task).
- **가치관 유사도**: `parenting_values_profiles`의 (warmth, control) 좌표 간 유클리드 거리를
  최대 가능 거리(각 축 1~5점 범위이므로 √(4²+4²)≈5.657)로 정규화해 `1 - 정규화거리`로 계산.
  둘 중 하나라도 진단 미완료면 해당 후보는 목록에서 제외(온보딩 미완료로 간주).
- **상보 스코어**: `for_date`(기본값 오늘) 하루치 두 사용자의 48슬롯 비트마스크로
  `complementary_slot_counts`(T-SCH-1)를 계산해 (양방향 합)/48로 정규화. 근무표 미등록
  날짜는 풀가용(48슬롯 모두 1)으로 간주.
- **개월 수 유사도**: 두 사용자의 아동 개월수 평균 간 차이를 24개월로 정규화해
  `1 - min(차이/24, 1)`로 계산. 아동이 없는 사용자는 유사도 0으로 처리(아동 매칭 맥락상
  자연스러운 페널티, 요구사항정의서에 산식 명시 없어 임의 정의).
- **신뢰 점수는 스텁**: TRS 도메인(REQ-F-TRS-01 신뢰등급 상태머신)이 아직 구현되지 않아
  모든 후보에 동일 기본값(0.5, 중간값)을 사용한다. TRS 도메인 완성 후 실제 점수로 교체
  예정(후속 Task, AGENTS.md §6 "Task Contract에 없는 외부 API/서비스 연동"과 무관 — 내부
  미구현 도메인 스텁이라 반드시멈춤 트리거 아님).
- **가중치 설정파일화+변경이력(REQ-F-MAT-05 후반부)은 범위 밖**: 이번 Task는 하드코딩된
  상수로 시작하고, 운영자 설정 UI+변경 이력 감사로그는 ADM 도메인 후속 Task로 미룸(사용자
  승인, T-ACC-3의 LLM 스텁과 동일한 패턴).
- **차단 대상 제외**: 후보 목록 조회 시 `is_active=False` 또는 `is_sanctioned=True`인 계정은
  안전상 자연스럽게 제외한다(이미 `auth_kit.models.User`에 존재하는 컬럼 재사용, 별도
  요구사항 근거는 없으나 저비용 안전장치로 판단).

### 후속 필요 (범위 밖)
- REQ-F-MAT-04(가치관 유사도 세부 산식, 이 문서에서는 유클리드 근사로 우선 구현) 정식 검수
- REQ-F-MAT-06(LLM 근거문장), 07(요청/수락→L1), 08(후보없음 완화 제안), 09(재매칭 단골),
  10(반경확장 구독 이벤트), 11(대기등록 알림), 13(근무표 변경 알림)
- TRS 도메인 완성 후 신뢰점수 스텁 교체
- 태그 Set Cover 양방향 검사, 선택 6종 태그 스코어 반영
- 가중치 설정파일화 + 변경 이력(ADM 도메인)

### 완료 보고
- 완료 정의 체크리스트: 전항목 완료(위 "완료 정의" [x] 참고)
- 가정: 위 "자율 판단 / 가정" 참고
- 공유 계약 변경 필요 사항: 없음
- 브랜치명: `feature/T-MAT-1-candidate-matching`
