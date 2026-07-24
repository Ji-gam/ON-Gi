# ON-Gi

레이어 우선 구조(Router → Service → Repository)의 FastAPI 백엔드 + Vite/React 프론트엔드 + AI 워커로 구성된 프로젝트 기본 템플릿.

## 구조

```
app/            FastAPI 백엔드
  apis/v1/      라우터 (도메인별 등록: app/apis/v1/__init__.py)
  dtos/         요청/응답 스키마
  services/     비즈니스 로직
  repositories/ DB 접근
  models/       SQLAlchemy 모델 (Base: app/models/base.py)
  dependencies/ FastAPI 의존성
  core/         config / db / jwt / utils / validators (공유)
  tests/        pytest
ai_worker/      RAG·백그라운드 워커 (FastAPI)
frontend/src/   pages/ hooks/ (화면) · api/ components/ routes/ store/ types/ (공유)
docs/           규칙/기여 문서 (아래 참고)
infra/ envs/ scripts/  배포·환경·CI
```

## 시작하기

백엔드:

```bash
uv sync --group app --group dev
uv run uvicorn app.main:app --reload
```

프론트엔드:

```bash
cd frontend && npm install && npm run dev
```

## 문서

- `AGENTS.md` — 에이전트/기여자 단일 진입점(정책+라우팅)
- `docs/CONTRIBUTING.md` — 구조/브랜치/PR/TDD 순서/로컬 실행/검증
- `docs/CODING_RULES.md` — 계층/폴더/네이밍/API·DB 포맷/프론트 규칙
- `docs/SQUAD_MAP.md` — 스쿼드/소유자
- `docs/FRONTEND_UI_GUIDE.md` — 디자인 시스템(Tailwind + shadcn)
- `docs/TROUBLESHOOTING.md` — 로컬 실행 에러

> 이 저장소는 도메인 로직을 뺀 뼈대(스켈레톤)만 담고 있습니다. 실제 기능은 각 계층
> 폴더에 도메인별로 추가하세요.
