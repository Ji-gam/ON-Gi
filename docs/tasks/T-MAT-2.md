# Task Contract T-MAT-2 (추천 근거 문장 - 규칙 기반 폴백)

### 참조
- 담당: 백엔드(`docs/SQUAD_MAP.md` §1, 접두어 `mat_*`)
- 관련 REQ: REQ-F-MAT-06(추천 근거 문장 생성), REQ-NF-AVA-01(시연 무중단 - LLM 장애 시
  규칙 기반 대체 문구)
- 선행: T-MAT-1(`app/services/matching_service.py`의 `MatchCandidate`/`GET /mat/candidates`)
- NEXT_PLAN_v1.md §5-3 결정 방향: "규칙 기반을 기본값으로 두고 LLM을 옵션으로 얹는 구조"를
  그대로 따름 — 이 Task는 규칙 기반 폴백만 구현한다. LLM+RAG(ai_worker 연동)는 범위 밖.

### 목표 (요구사항정의서 원문)
- REQ-F-MAT-06: "LLM+RAG로 '1km 안 · 근무가 정확히 엇갈리고 · 알레르기 대응이 되며 ·
  양육관이 가깝다' 형태의 한국어 근거 문장을 후보별로 자동 생성한다." 성공요건: "후보 상세에
  2문장 이내의 근거가 표시되며 수치가 실제 계산값과 일치한다."
- REQ-NF-AVA-01(관련 부분): "외부 LLM API 장애 시 근거 문장을 규칙 기반 대체 문구로
  폴백한다."

### 완료 정의
- [x] `app/core/utils/recommendation_reason.py`: 순수 함수 `build_recommendation_reason()` —
      거리·상보스코어·가치관유사도·신뢰점수(이미 계산된 값)를 임계값으로 조합해 한 문장(마침표
      1개, "2문장 이내" 요건 충족)을 생성
- [x] `app/services/matching_service.py`: `MatchCandidate`에 `reason: str` 필드 추가,
      `find_candidates()`에서 후보별로 `build_recommendation_reason()` 호출
- [x] `app/dtos/matching_dto.py`, `app/apis/v1/mat_routers.py`: `CandidateResponse.reason`
      노출
- [x] `frontend/src/api/matchingTypes.ts`: `CandidateResponse`에 `reason`(및 기존에 누락돼
      있던 `average_rating`/`top_tags`) 동기화. 화면 렌더링(SCR-11/12 보강)은 T-FE-1 범위.
- [x] DB 신규 테이블 없음(순수 계산) — 마이그레이션 불필요, ERD.dbml 변경 없음
- [x] (공통) 테스트: `app/tests/mat_apis/test_recommendation_reason.py`(임계값별 문구 분기,
      수치 일치), `app/tests/mat_apis/test_matching_service.py`에 통합 어서션 추가.
      `uv run pytest app/tests/mat_apis -v` 통과
- [x] (공통) `uv run ruff check` / `ruff format` 통과(대상 파일)

### 허용 경로
```
app/core/utils/recommendation_reason.py
app/services/matching_service.py
app/dtos/matching_dto.py
app/apis/v1/mat_routers.py
app/tests/mat_apis/**
frontend/src/api/matchingTypes.ts
docs/tasks/T-MAT-2.md
docs/tasks/_active.json (등록/해제만)
```

### 금지 경로
- `auth_kit/**`, `security_kit/**`
- `app/models/**`, `app/core/db/migrations/**` (신규 테이블 없음)
- `ai_worker/**` (LLM 연동은 범위 밖 — 후속 Task)

### 자율 판단 / 가정 (Assumptions)
- **규칙 기반이 최종 산출물, LLM은 후속**: `ai_worker`는 아직 `health` 라우터뿐인 빈 껍데기이고
  백엔드→`ai_worker` HTTP 클라이언트 코드가 전혀 없다. NEXT_PLAN_v1.md §5-3이 권고한 대로
  "규칙 기반 폴백을 먼저 만들고 LLM은 그 뒤에 얹는다"는 순서를 따르되, 이번 Task는 규칙 기반
  문장 자체를 최종 응답으로 반환한다(REQ-NF-AVA-01의 "폴백 문구"와 동일 함수를 공용).
- **임계값**: 거리 300m 이하 "도보권"(그 외엔 실측 m 표기), 상보스코어·가치관유사도 0.5 이상,
  신뢰점수 0.6 이상을 "높음"으로 판단해 해당 절을 추가한다. 요구사항정의서에 수치 기준이
  명시되어 있지 않아 임의 정의(AGENTS.md §6 "결정됨" 대상 아님 — `matching_weights.py`의
  종합점수 가중치와는 별개로, 문장 조합 여부만 결정하는 표시용 임계값이므로 자유롭게 조정
  가능하다고 가정).
- **태그 충족 절은 항상 참**: `MatchingService.find_candidates()`가 완화불가 태그 하드필터를
  통과한 후보만 넘기므로, 살아남은 모든 후보는 이미 `tags_satisfied=True`다. 따라서
  `build_recommendation_reason()`은 `tags_satisfied` 기본값 True로 항상 해당 절을 포함한다.
  파라미터 자체는 남겨 두어 향후 선택 태그 매칭 여부 등으로 확장 가능하게 함.
- **문장 형식**: 요구사항 예시("1km 안 · 근무가 정확히 엇갈리고 · …")를 그대로 따라 절을
  " · "로 이어붙이고 마침표 1개로 끝낸다. 절이 최대 5개(거리+태그는 항상 포함, 상보/가치관/
  신뢰 3개는 조건부)까지 이어질 수 있으나 문장 자체는 1개이므로 "2문장 이내" 요건을 항상
  만족한다.

### 후속 필요 (범위 밖)
- LLM+RAG 연동(`ai_worker`) — 규칙 기반 문장을 장애 시 폴백으로 유지한 채 LLM 문장을 얹는
  구조. `NF-OPS-02`(월 비용 한도) 고려해 단발 LLM 호출 방식 검토 필요.
- REQ-NF-PER-01 후반부("근거 문장 생성은 비동기로 처리해 목록 표시를 지연시키지 않는다") —
  현재는 동기 계산(순수 함수, DB/외부 호출 없음)이라 지연 이슈가 없지만, LLM 연동 시
  비동기 파이프라인으로 재설계 필요.
- 프론트 화면 반영(SCR-11/12 후보 상세에 근거 문장 노출) — T-FE-1.

### 완료 보고
- 완료 정의 체크리스트: 전항목 완료(위 "완료 정의" [x] 참고)
- 가정: 위 "자율 판단 / 가정" 참고
- 공유 계약 변경 필요 사항: `CandidateResponse`에 `reason: str` 필드 추가(프론트 타입 동기화
  완료, 화면 렌더링은 T-FE-1에서)
- 브랜치명: (현재 작업 브랜치 `claude/t-pnt-2-progress-2beaee`에서 이어서 진행)
