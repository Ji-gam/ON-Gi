# Task Contract T-ACC-3 (양육 가치관 진단)

### 참조
- 담당: 백엔드(`docs/SQUAD_MAP.md` §1, 접두어 `acc_*`)
- 관련 REQ: REQ-F-ACC-07(바움린드 8문항 진단), REQ-F-ACC-08(재진단, 매칭 재계산 트리거 부분만 — 매칭 자체는 MAT 범위),
  REQ-F-ACC-10(자유서술 LLM 보정)
- 선행: T-ACC-1(dev 머지 완료, `auth_kit.models.User` 전제)

### 목표 (요구사항정의서 원문)
- REQ-F-ACC-07: "바움린드 기반 8문항(온기 4·통제 4)에 5점 척도로 응답하면 2축 벡터를 산출해 저장한다."
  성공요건: "8문항 응답 후 온기·통제 좌표와 유형 라벨이 프로필에 표시된다."
- REQ-F-ACC-08: "프로필·태그·가치관 진단을 언제든 재수행할 수 있으며, 변경 시 매칭 점수 재계산을 트리거한다."
  (매칭 재계산 자체는 MAT 도메인 미구현 — 이 Task는 재진단이 가능하고 이력이 남는 것까지만 담당)
- REQ-F-ACC-10: "양육 경험을 자유 서술로 입력하면 LLM이 문장을 해석해 바움린드 8차원 벡터를 보정한다. ...
  서술 미입력 시 8문항 척도 결과만 사용한다." 성공요건: "자유 서술 입력 전후로 가치관 벡터 값이 달라지고
  변경 이력이 남는다."

### 완료 정의
- [x] `app/core/utils/baumrind_questions.py`: 온기 4문항+통제 4문항 텍스트(직접 작성, 아래 가정 참고),
      5점 척도, 4유형(권위있는/권위주의적/허용적/방임적) 분류 함수
- [x] `app/models/parenting_values.py`: `ParentingValuesProfile`(user_id FK 1:1, warmth_score,
      control_score, type_label, narrative) + `ParentingValuesHistory`(재진단/서술 이력, source 구분)
- [x] `app/services/parenting_values_service.py`: 설문 제출(생성/재진단 겸용 upsert) + 자유서술 제출(스텁)
- [x] `app/apis/v1/acc_routers.py`: `GET /acc/parenting-values/questions`,
      `POST /acc/parenting-values/questionnaire`, `POST /acc/parenting-values/narrative`,
      `GET /acc/parenting-values`
- [x] Alembic 마이그레이션 생성/적용(`18d4663fd949_parenting_values.py`, `ai_health_on` DB에 upgrade 확인),
      `docs/dev/ERD.dbml` v1.2 갱신(§6)
- [x] (공통) 테스트 작성(`app/tests/acc_apis/test_parenting_values_service.py`, 5건),
      `uv run pytest app/tests -v` 12/12 통과
- [x] (공통) `ruff check .` / `ruff format --check .` / `uv run mypy .` 통과

### 허용 경로
```
app/core/utils/baumrind_questions.py
app/models/parenting_values.py
app/repositories/parenting_values_repository.py
app/services/parenting_values_service.py
app/dtos/parenting_values_dto.py
app/apis/v1/acc_routers.py
app/models/__init__.py
app/core/db/migrations/versions/**
docs/dev/ERD.dbml
app/tests/acc_apis/**
docs/tasks/T-ACC-3.md
docs/tasks/_active.json (등록/해제만)
```

### 금지 경로
- `auth_kit/**`, `security_kit/**`, `ai_worker/**` (LLM 실연동은 이 Task 범위 밖 — 아래 가정 참고)

### 자율 판단 / 가정 (Assumptions)
- **8문항 실제 문구**: 요구사항정의서(v1/v1.1/v1.2) 어디에도 실제 질문 텍스트가 없다("최종 기획서"라는
  해커톤 예선 제출본을 참조하고 있으나 이 저장소엔 포함되어 있지 않음, 확인 완료). Baumrind 양육유형
  이론(온기=반응성, 통제=요구성)에 근거해 직접 작성했다(사용자 승인). 문항·척도 라벨은 향후 실제 설문
  검수 시 자유롭게 교체 가능하도록 `app/core/utils/baumrind_questions.py` 한 파일에 모아둔다.
- **유형 분류 임계값**: 5점 척도 중앙값(3.0) 기준으로 온기/통제 각각 고/저를 나누어 4유형(권위있는=고온기고통제,
  권위주의적=저온기고통제, 허용적=고온기저통제, 방임적=저온기저통제)으로 분류한다. 요구사항정의서에 임계값
  명시가 없어 이론상 표준 사분면 분류를 채택.
- **REQ-F-ACC-10 LLM 실연동은 스텁**: `openai` 패키지가 `app`(서버) 의존성 그룹엔 없고 top-level에만 있으며,
  `ai_worker` 스쿼드 쪽 게이트웨이/RAG 아키텍처가 아직 미구현이라(조사 완료), 이 Task에서 외부 API를
  직접 연동하지 않는다(AGENTS.md §6 "Task Contract에 없는 외부 API 연동" 반드시멈춤 회피, 사용자 승인).
  자유서술 텍스트는 저장하고 이력에 남기되, 실제 벡터 보정 로직은 `app/main.py`의 `send_email`/`send_sms`와
  동일한 TODO 스텁 패턴으로 남긴다 — 현재는 서술 제출 시점의 스코어를 그대로 재기록한다(값이 달라지지
  않음, REQ-F-ACC-10 성공요건 중 "벡터 값이 달라진다" 부분은 ai_worker 연동 후 충족 예정).
- REQ-F-ACC-08의 "매칭 점수 재계산 트리거"는 MAT 도메인이 없어 재진단 시 이력 테이블에 새 스냅샷을 남기는
  것까지만 하고, 실제 트리거/재계산은 훅 없이 후속 Task로 미룬다.

### 후속 필요 (범위 밖)
- ai_worker 게이트웨이 완성 후 REQ-F-ACC-10 실제 LLM 보정 로직 연결
- MAT 도메인에서 REQ-F-ACC-08 매칭 점수 재계산 트리거 연결

### 완료 보고
- 브랜치명: `feature/T-ACC-3-parenting-values`
