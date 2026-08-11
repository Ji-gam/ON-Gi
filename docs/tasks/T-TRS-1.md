# Task Contract T-TRS-1 (상호 평가 + 신뢰 점수 산식, MAT 스텁 교체)

### 참조
- 담당: 백엔드(`docs/SQUAD_MAP.md` §2, 접두어 `trs_*`)
- 관련 REQ: REQ-F-TRS-05(태그 상호 평가), REQ-F-TRS-06(신뢰 점수 산출), REQ-F-TRS-07(후기·별점
  열람), REQ-F-TRS-08(신뢰 점수 산식 명세+가중치 이력)
- 선행: T-CAR-2(`care_sessions.checkout_at`/`care_logs` — 평가는 세션 종료 후에만 가능, 일지
  작성률이 산식 입력값)
- 후속 연동: T-MAT-1이 남긴 숙제("TRS 완성 후 신뢰점수 스텁 교체") 해소 —
  `app/services/matching_service.py`의 `STUB_TRUST_SCORE`(0.5 고정값)를 이 Task의 실제 계산으로
  교체

### 목표 (요구사항정의서 원문)
- REQ-F-TRS-05: "돌봄 종료 후 양측이 별점과 태그(시간 준수·소통 원활·안전 배려 등)로 평가한다.
  평가 미제출 시 다음 요청 생성을 제한한다." 성공요건: "평가 제출 후 상대 프로필의 태그 분포가
  갱신된다."
- REQ-F-TRS-06: "완료 횟수, 별점, 태그 가중치, 노쇼 이력을 반영해 신뢰 점수를 산출하고 매칭
  총점에 반영한다." 성공요건: "노쇼 기록 후 신뢰 점수가 하락하고 후보 순위가 내려간다."(노쇼
  이력 자체는 REQ-F-CAR-07 미구현 — 이번 Task는 산식에 항을 마련하고 스텁값 사용, 아래 가정 참고)
- REQ-F-TRS-07: "매칭 후보 상세에서 상대의 별점 평균과 최근 후기 태그를 열람할 수 있다. 후기
  본문은 익명 처리한다." 성공요건: "후보 상세에서 별점과 태그 상위 3개가 표시된다."
- REQ-F-TRS-08: "1단계 신뢰 점수는 (w1×별점)+(w2×이행 확인 응답률)+(w3×(1−노쇼율))+
  (w4×돌봄 일지 작성률)의 가중합으로 산출한다. 가중치는 설정으로 관리하고 변경 시 변경자·
  시각·이전 값을 이력으로 남긴다." 성공요건: "가중치 변경 후 신뢰 점수가 재계산되고 변경 이력
  1건이 기록된다."

### 완료 정의
- [x] `app/models/care_evaluation.py`: `CareEvaluation`(session_id/evaluator_id/evaluatee_id,
      rating 1~5, unique(session_id, evaluator_id)) + `CareEvaluationTag`(evaluation_id, tag_code)
- [x] 평가 제출: 세션이 `checkout_at` 있어야(돌봄 종료) 가능, evaluator는 세션의 requester/
      provider 본인만, 세션당 1회만(중복 제출 409)
- [x] 완료(체크아웃된) 세션에 평가를 제출하지 않은 사용자는 새 요청 생성(`create_request`)과
      수락(`accept`) 모두 400으로 차단(REQ-F-TRS-05 "다음 요청 생성 제한")
- [x] `app/models/trust_weights.py`: `TrustWeights`(싱글턴, w1~w4)+`TrustWeightHistory`(변경자·
      시각·이전 값). 가중치 합이 1.0(허용오차)이 아니면 변경 거부, 운영자(`is_admin`)만 변경 가능
- [x] 신뢰 점수 산식(REQ-F-TRS-08 그대로): `w1×별점정규화 + w2×이행확인응답률 + w3×(1−노쇼율)
      + w4×일지작성률`. 일지작성률만 이번 Task 데이터(T-CAR-2)로 실계산, 나머지는 아래 "가정"
      참고
- [x] `matching_service.py`의 `STUB_TRUST_SCORE` 고정값 사용을 실제 `TrustScoreService.
      calculate_score` 호출로 교체, `CandidateResponse`에 `average_rating`/`top_tags`(상위 3,
      REQ-F-TRS-07) 추가
- [x] (공통) 새 테이블은 Alembic 마이그레이션(`c2d5e9f7a1b4_trust_evaluation.py`) +
      `docs/dev/ERD.dbml` v1.6 동기화(`TrustWeights` 기본값은 서비스 레이어 지연 생성으로 대체,
      아래 가정 참고)
- [x] (공통) 테스트를 TDD로 먼저 작성(`app/tests/trs_apis/**`: 미종료 세션 평가 거부, 중복 평가
      거부, 평가 미제출 시 create_request/accept 차단, 가중치 합 검증+변경 이력 기록, 신뢰
      점수 산식 계산), `uv run pytest -v` 통과(40 passed, MAT 회귀 없음)
- [x] (공통) `ruff check .` / `ruff format --check .` / `uv run mypy .` 통과

---

### 허용 경로
```
app/models/care_evaluation.py     (신규)
app/models/trust_weights.py       (신규)
app/repositories/care_evaluation_repository.py   (신규)
app/repositories/trust_weight_repository.py      (신규)
app/services/trust_evaluation_service.py   (신규)
app/services/trust_score_service.py         (신규)
app/services/care_session_service.py   (평가 미제출 게이트 추가)
app/services/matching_service.py         (STUB_TRUST_SCORE 교체, 평판 필드 추가)
app/dtos/trust_dto.py            (신규)
app/dtos/matching_dto.py         (average_rating/top_tags 필드 추가)
app/core/utils/matching_weights.py   (STUB_TRUST_SCORE 상수 제거)
app/apis/v1/trs_routers.py       (신규)
app/apis/v1/__init__.py
app/core/db/migrations/versions/**  (신규 리비전 파일만 추가)
app/tests/trs_apis/**            (신규)
app/tests/mat_apis/**             (STUB 제거에 따른 회귀 확인)
docs/dev/ERD.dbml
docs/tasks/T-TRS-1.md
docs/tasks/_active.json (등록/해제만)
```

### 금지 경로
- `auth_kit/**`, `security_kit/**`
- `app/models/care_session.py`, `app/models/care_log.py` (읽기 전용 재사용만)

### 의존하는 공유 계약 (읽기만)
- `app/repositories/care_session_repository.py`, `app/repositories/care_log_repository.py` —
  일지 작성률 계산용
- `app/dependencies` — `get_current_user`

### 자율 판단 / 가정
- **이행 확인 응답률(w2)**: REQ-F-TRS-02(공동육아 일정 완료 확인)가 아직 구현되지 않아 데이터가
  없음 — 도메인 미구현으로 인한 결측은 "문제 없음"으로 간주해 1.0(만점) 스텁 사용
  (`# TODO(T-TRS-1→T-TRS-2)`), MAT-1이 신뢰점수 전체를 0.5로 스텁한 것과 동일한 태도
- **노쇼율(w3 항의 1−노쇼율)**: REQ-F-CAR-07(취소·노쇼 처리)이 아직 구현되지 않아 0.0(노쇼
  없음) 스텁 사용(`# TODO(T-TRS-1→T-CAR-3 혹은 후속)`)
- **별점 정규화**: 평가가 하나도 없는 사용자는 신규 가입자 페널티를 주지 않기 위해 중립값
  0.5(별점 3점 상당) 사용. 있으면 `(평균-1)/4`로 0~1 정규화
- **일지 작성률**: provider로 참여해 체크아웃 완료된 세션 중 일지가 작성된 비율. 체크아웃
  완료 세션이 없으면(신규 제공자) 중립값 1.0 — 이력이 없다고 페널티를 주지 않음
- **기본 가중치**: 요구사항정의서에 초기값 명시 없어 w1=0.4/w2=0.2/w3=0.2/w4=0.2(합 1.0)로
  가정, 마이그레이션에서 시드
- **평가 미제출 게이트**: "다음 요청 생성 제한"을 create_request(요청자)뿐 아니라 accept
  (제공자가 새로 확정하는 행위)에도 동일 적용 — 두 액션 모두 새로운 세션 커밋이라 판단(사용자
  승인 필요 시 조정)
- **태그 분포/후기 열람(REQ-F-TRS-07)**: 익명 처리는 "후기 본문"이 없는 태그+별점 구조라 별도
  마스킹 불필요(사용자 식별 정보를 원천적으로 반환하지 않음)

### 반드시 멈춰야 하는 경우
- Pod/앙상블 학습 데이터 적재(REQ-F-TRS-09/10)가 필요해 보이는 경우 (범위 밖, 별도 Task)

---

### 완료 보고
- 완료 정의 체크리스트 결과: 전항목 완료(위 "완료 정의" [x] 참고)
- 가정(Assumptions): 위 "자율 판단 / 가정" 참고. 추가로 — `TrustWeights` 기본값은 마이그레이션
  시드 대신 `TrustWeightRepository.get_or_create`에서 최초 조회 시 지연 생성(두 곳에 기본값이
  분산되는 것을 피하기 위함). 평가 미제출 게이트는 400으로 통일(요청 생성/수락 모두 "아직
  진행 전" 상태이므로 409 대신 400이 적절하다고 판단).
- 공유 계약 변경 필요 사항 (있다면): 없음. 다만 `matching_service.py`/`matching_weights.py`(MAT
  소유 파일)를 수정했음 — 단일 백엔드 담당자 체제(SQUAD_MAP v3.0)라 별도 조율 불필요하나 기록
  으로 남김
- 브랜치명: `feature/T-TRS-1-trust-evaluation`
