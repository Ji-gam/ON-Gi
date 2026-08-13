# AGENTS.md — 품앗이온(ON) 단일 진입점

v4.0 · 이력: `git log AGENTS.md`. 모든 에이전트 매 세션 필독. `CLAUDE.md`/`.antigravity/rules/AGENTS.md`=리다이렉트. 불확실하면 추측 금지, 확인. 이 문서는 정책+라우팅만 — 각 항목의 상세 규칙은 아래 대상 문서에만 존재(중복 서술 금지).

> v4.0 배경: 이 레포는 원래 다른 프로젝트(ReMedi)용 스켈레톤이었다. v4.0부터 실제 서비스인
> "품앗이온(ON)"(교대근무자 상호돌봄 매칭, 팀 온기, 2026 K-디지털 트레이닝 해커톤 5주 MVP)
> 기준으로 재작성했다. 배경/전환 경위: `docs/decision_log/2026-08-10.md`.

0. 절대원칙
- Task Contract(`docs/tasks/T-XXX-N.md`) "허용 경로" 밖 파일 금지(존재확인 외 열람도 금지)
- 확인질문 최소화 — §6표+Task Contract로 진행, 부족분은 가정 후 완료보고에 Assumptions로 기록. T-ID없음/여러도메인처럼 모호하면 임의진행 대신 가정을 먼저 설명. 사용자가 피하라고 한 접근은 같은 대화 내 재시도 안 함
- 중단은 §6표 "반드시멈춤" 항목일 때만. 그 외(변수명/함수분리/에러문구)는 자체결정. `STOP` 입력시 즉시중단(§4)
- 공유구역([공유]표시, §1) Task Contract 미허용시 수정 금지 — 완료보고에 "공유파일 변경 필요"만 기록
- 시작시 `docs/tasks/_active.json`에 Task ID+브랜치명 등록, 종료시 해제

1. 디렉토리=소유권 (전체 구조/파일역할: `docs/CODING_RULES.md` §2/§3)

```
app/            apis/v1/ dtos/ services/ repositories/ models/ tests/
                dependencies/ core/ [공유]
ai_worker/      매칭 근거문장 생성(LLM+RAG, REQ-F-MAT-06), 분쟁 B단계 챗봇(REQ-F-CAR-08/10)
                | core/[공유]
frontend/src/   pages/ hooks/ [화면소유]
                api/ components/ routes/ store/ types/ [공유]
envs/ infra/ scripts/ [공유]
docs/plan/      요구사항정의서(REQ-*)/화면설계서(SCR-*)/기능목록표(FN-*) [수정금지, §7]
docs/tasks/     Task Contract(도메인당1)+_active.json(claim)
```
폴더 아닌 파일명 접두어로 도메인 구분(소유자 표: `docs/SQUAD_MAP.md`). 도메인 코드는
요구사항정의서 §1.5 체계를 그대로 쓴다 — 새 코드 만들지 않음:
`ACC`(계정·프로필·아동) `SCH`(근무표·시간) `MAT`(매칭) `TRS`(신뢰·평판) `CAR`(돌봄세션)
`PNT`(포인트) `COM`(커뮤니케이션) `ADM`(운영). 1에이전트=백엔드파일1/프론트화면폴더1/
AI태스크파일1개 소유. 배정 전 `_active.json` 확인, 클레임중이면 진행금지+보고. 신규 Task
Contract는 `docs/tasks/TASK_CONTRACT_TEMPLATE.md` 복사.

2. 스택
백엔드 FastAPI, DB MySQL, 프론트 React(+Vite), 인프라 AWS(요구사항정의서 §"제약사항 및
가정" — 기술 제약, 재질문 금지). 상세는 `pyproject.toml`/`frontend/package.json`. 코드
컨벤션은 `docs/CODING_RULES.md`.

3. User↔Child
전체 규칙: `docs/CODING_RULES.md` §2-1. 요지만: User(보호자, 로그인 계정)가 Child(아동,
로그인 계정 없음)를 `user_id` FK로 직접 소유한다(REQ-F-ACC-04~06) — ReMedi 템플릿의
User/Profile(`profile_id` 기준) 분리는 이 서비스에 없다(가족 대리 프로필 확장 요구 없음).
아동 알레르기·지병·투약 등 민감정보는 컬럼단위 암호화, 신규 도메인테이블에서 아동 관련
FK가 필요하면 `child_id`를 쓴다.

4. Drill-Me/STOP
트리거(하나라도): 새 화면/컴포넌트/플로우 요청, 텍스트 화면스펙(진입점/컴포넌트/로딩·빈·에러상태/인터랙션→API/T-ID) 없음, 기존 스펙 범위 초과.
생략: 스펙 안에서만 구현, 순수 버그수정/내부 리팩토링.
질문세트(답 없는 것만 콕 집어 되물음, 코드 먼저 안 씀): 진입점(탭/화면) / 구성 컴포넌트+필수·선택 / 로딩·빈·에러 상태 표시 / 인터랙션→API 매핑 / T-ID(요구사항정의서/화면설계서/기능목록표 대조) / (해당시) 아동(child_id) 대상 여부.
판단기준: "이 요구사항만으로 두 사람이 다른 화면을 만들 수 있는가"→그렇다면 미완료. 답 다 있으면 "이렇게 이해했다" 요약확인만. 끝나면 짧은 텍스트스펙 동의받고 코드 작성.
STOP: 메시지 어디든 `STOP`→ 작성중이면 즉시멈춤 / 이해내용 요약 / 미답 문항만 재확인 / 답 받기 전 재산출 안 함. 취소 아님, 재확인모드 전환.

5. 브랜치/커밋/PR/구현순서/로컬실행/검증
전부 `docs/CONTRIBUTING.md`. 에이전트는 PR 생성+CI확인까지가 범위, 직접 머지 안 함. 에러 발생시 `docs/TROUBLESHOOTING.md`.

6. 결정됨/반드시멈춤
결정됨(재확인불필요, 각주=근거/상세위치 — 전부 요구사항정의서 v1.2 확정본 기준): 이메일·소셜+휴대폰 본인확인 1회, JWT 세션(REQ-F-ACC-01) · 위치정보는 정확 좌표 대신 H3 인덱스만 저장(REQ-NF-SEC-05) · 아동 민감정보 AES-256 컬럼단위 암호화(REQ-NF-SEC-01) · 매칭 총점=가치관유사도35%+상보스코어35%+나머지30%(거리·개월수·신뢰점수), 가중치는 설정값화+변경이력 필수(REQ-F-MAT-05) · 완화불가 4종 태그(알레르기대응·투약관리·응급처치이수·비흡연가정)는 어떤 경우에도 완화 안 됨(REQ-F-MAT-03) · 신뢰등급 L1→L2→L3 상태머신+역방향(강등) 전이 지원(REQ-F-TRS-01) · 단독위탁은 L3에서만, UI+API 양쪽 차단(REQ-F-TRS-04) · 분쟁 A(당사자)/B(챗봇 쟁점정리)/C(운영자) 3단계, 확정판정권한은 C에만(REQ-F-CAR-08) · 포인트는 복식부기 원장, 거래별 차변·대변 합 항상 0(REQ-F-PNT-01) · 반경확장구독(월1,990원)·현금보증금·PG연동은 MVP 실결제 없음, 전환의사만 이벤트로 기록(REQ-F-MAT-10/PNT-05/06) · 근무표 OCR·에스크로·Pod UI·신뢰점수 앙상블 학습·서버리스전환은 P1(요구사항정의서 §1.2 제외범위) · 월 서버비용 5만원 이하(REQ-NF-OPS-01) · 주민등록번호 수집 금지(REQ-NF-LAW-03) · 만14세미만 아동정보 처리시 법정대리인 동의 필수(REQ-NF-LAW-01) · 무상태 API설계(REQ-NF-SCA-01) · 비밀번호는 단방향 해시 저장(REQ-NF-SEC-03)
반드시멈춤: 공유구역/DB공통스키마 직접수정 필요 · Task Contract에 없는 외부API/서비스연동 · 요구사항정의서 충족에 허용경로 밖 수정 불가피 · 개인정보/보안 비가역작업(암호화방식,아동 민감정보 로직,영구삭제) · 완화불가 4종 태그를 완화하려는 시도 · 매칭 가중치(35/35/30) 또는 분쟁 C단계 판정권한 변경이 필요해보임 · 두 REQ 요구사항 모순 · DB스키마/ORM/인증방식 등 되돌리기 힘든 결정 · T-ID없거나 여러도메인 걸친 모호한 요청 · 타스쿼드 소유파일(SQUAD_MAP.md) 수정 필요할듯 · 이미 정해진 것 다르게 재해석해야 할듯
표 밖은 위 원칙+Task Contract+합리적 가정으로 진행.

7. 범위경계
- T-ID/기능 무관 파일 수정 금지
- `docs/plan/`(요구사항정의서/화면설계서/기능목록표)는 명시요청 없이 수정 금지
- `.env`/API키/시크릿 코드·커밋·PR에 하드코딩 금지 — `envs/example.*.env`엔 키 이름만
- 실코드가 `CODING_RULES.md`/`decision_log`와 다르면 팀합의 없는 개인작업 가능성 — 그대로 안 따르고 재작업 필요여부 확인

8. 완료 자가검증
Task Contract "완료정의" 체크 후 `docs/tasks/T-XXX-N.md` 완료보고에 기록. 실패항목은 PR 열기 전 자체수정. 확인: 테스트포함 / 요구사항정의서 「검증 기준」 충족 / `ruff`·`pytest`·`tsc`·`lint` 통과 / 변경범위 T-ID 한정(`git diff --stat`) / 새 엔드포인트 summary·description·responses·Field(description=...) / DB변경시 Alembic+ERD 동기화 / 커밋·브랜치명 규칙 준수(CONTRIBUTING§3,§8). 검증커맨드: `docs/CONTRIBUTING.md` §7.

9. 문서지도
`docs/CONTRIBUTING.md`(구조/브랜치/이슈·PR/TDD순서/로컬실행/검증) · `docs/CODING_RULES.md`(계층/폴더/네이밍/API·DB포맷/프론트규칙/TDD품질기준/ERD/Swagger) · `docs/TROUBLESHOOTING.md`(로컬실행 에러) · `docs/SQUAD_MAP.md`(스쿼드/소유자, 유일출처) · `docs/FRONTEND_UI_GUIDE.md`(디자인시스템/Tailwind+shadcn) · `docs/decision_log/`(배경/미결) · `docs/plan/`(요구사항정의서, 수정금지 — 화면설계서·기능목록표 확보되면 같은 위치에 추가) · `docs/dev/`(ERD.dbml/api_spec/sample_code, 아직 미생성) · `docs/tasks/`(Task Contract/`_active.json`)
