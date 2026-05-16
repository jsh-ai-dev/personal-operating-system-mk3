# Personal Operating System mk3

Python/FastAPI 기반의 AI 통합 백엔드로, 여러 LLM(ChatGPT·Claude·Gemini)을 한 곳에서 호출·저장·검색·학습 도구화하는 서비스입니다.

`mk3`은 Personal Operating System 시리즈에서 AI 도메인을 담당하며, `mk2`의 인증/BFF를 거쳐 `mk1` 노트 서비스와 함께 동일한 사용자 세션으로 묶여 동작합니다.

시리즈 저장소:

- [mk1 - Spring Boot 노트/검색/파일/AI 요약](https://github.com/jsh-ai-dev/personal-operating-system-mk1)
- [mk2 - Next.js/NestJS 통합 웹, 인증, 일정](https://github.com/jsh-ai-dev/personal-operating-system-mk2)
- [mk3 - 본 저장소, FastAPI AI 대화 저장, 임포트, 검색](https://github.com/jsh-ai-dev/personal-operating-system-mk3)

## 한눈에 보기

| 구분 | 내용 |
|---|---|
| 목적 | 여러 AI 서비스의 대화·구독·사용량을 통합 관리하고, 저장된 대화를 학습 자료로 가공 |
| 핵심 기능 | 멀티 LLM 채팅(SSE), 대화 임포트, Qdrant 의미 검색, AI 요약/퀴즈, 사용량 스크래퍼, 신문 분석 |
| 설계 | Clean Architecture (domain / application / adapter / api) — 도메인은 프레임워크 의존 없음 |
| 인증 | mk2 auth-service `/api/auth/me`에 토큰 검증을 위임, owner_id 기반 데이터 격리 |
| 운영 요소 | Docker Compose, Kubernetes base/AWS overlay, ECR + OIDC 빌드, k3s self-hosted runner 무중단 배포, S3 임포트 |

## 시스템 구조

```text
[Browser]
    │
    ▼
[mk2 Next.js BFF :3000]                       ─ 인증 쿠키 관리, JWT 프록시
    └─ /api/mk3/* ───────────────►  [mk3 FastAPI :8001]  ◀ 이 프로젝트
                                          │
                       ┌──────────────────┼──────────────────┐
                       ▼                  ▼                  ▼
                   MongoDB             Qdrant            External
                   (대화/메시지/        (대화 임베딩       ├─ OpenAI / Anthropic / Google API
                    뉴스/AI 서비스)      코사인 유사도)     ├─ mk2 auth-service (/api/auth/me)
                                                          ├─ Chrome CDP (사용량 스크래퍼)
                                                          └─ AWS S3 (임포트 파일 저장)
```

mk3에는 Nuxt 3 기반의 `mk3-web`도 포함되어 있지만, 실사용 메인 프론트는 mk2(React/Next.js)입니다. `mk3-web`은 Vue/Nuxt 학습과 기능 실험용 보조 UI로 유지합니다.

## 구현 기능

### 1. 멀티 LLM 채팅 (SSE 스트리밍)

OpenAI·Anthropic·Google API를 직접 호출하고 응답을 Server-Sent Events로 실시간 스트리밍합니다. 응답 완료 시 토큰 수와 비용을 메시지·대화 단위로 MongoDB에 누적 저장합니다.

- 3개 provider 모두 같은 `chat_<provider>_stream` 비동기 제너레이터 인터페이스로 통일
- provider별 role 매핑 차이 흡수 (Gemini는 `assistant`→`model`, Anthropic은 OpenAI와 동일)
- 마지막 청크의 `usage` 메타데이터로 input/output 토큰 추출 → 단가 테이블과 곱해 USD 비용 계산
- Gemini 무료 티어는 비용 대신 RPM/RPD/TPM rate limit으로 관리

```python
OPENAI_PRICING = {
    "gpt-5-nano": {"input": 0.05,  "output": 0.40},
    "gpt-5-mini": {"input": 0.25,  "output": 2.00},
    "gpt-5":      {"input": 1.25,  "output": 10.00},
}
CLAUDE_PRICING = {
    "claude-haiku-4-5":  {"input": 1.00, "output": 5.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-opus-4-7":   {"input": 5.00, "output": 25.00},
}
```

### 2. 대화 임포트 (5종 소스)

| 소스 | 포맷 | 파싱 특이사항 |
|---|---|---|
| ChatGPT export | `conversations.json` | 메시지 트리에서 활성 분기만 추출, citation 마커(U+E200~E201) 제거 |
| Claude.ai export | `conversations.json` | 사용자/어시스턴트 메시지 분리, 원본 `created_at` 보존 |
| Claude Code | `.jsonl` 트랜스크립트 | 라인별 JSON 파싱, 세션 ID = 파일명 |
| JetBrains Codex | `.events` 파일 | `AUI_EVENTS_V1\|base64(JSON)`, JSON 내부 이벤트도 다시 base64 — 이중 인코딩 |
| Google Takeout | `내활동.json` | 시간 인접한 Q/A를 KST 기준으로 그룹핑해 대화 단위 복원 |

- `source_id` 기반 중복 검사 — 같은 세션을 두 번 임포트해도 멱등 동작
- 임포트 직후 `SearchService`로 자동 임베딩 → 즉시 의미 검색 가능
- 파일은 로컬 `data/` 또는 S3 둘 다 지원, `S3_BUCKET` 설정 여부로 자동 분기

### 3. Qdrant 의미 검색

OpenAI `text-embedding-3-small`(1536차원)로 대화를 임베딩하고 Qdrant에 코사인 거리로 저장합니다.

- 요약이 있는 대화는 `title + summary`를, 없으면 메시지 원문을 문자 예산(3,000자) 내에서 이어 붙여 임베딩
- 임베딩 후 MongoDB에 `qdrant_id` 저장 → 전체 재인덱싱 시 이미 인덱싱된 대화는 건너뜀
- 검색 시 `owner_id` 필터로 다른 사용자 대화가 결과에 섞이지 않도록 격리
- Qdrant payload에 없는 필드(provider, summary 여부, 비용)는 MongoDB에서 `find_conversations_by_ids`로 한 번에 N+1 없이 보강
- 요약 생성 직후 기존 임베딩을 새 요약 기준으로 자동 교체

### 4. AI 요약 / 퀴즈 (학습 도구)

저장된 대화를 OpenAI 모델로 요약하고, 요약을 기반으로 4지선다 퀴즈를 생성합니다. "처음 배우는 기술을 나중에 다시 확인할 때 도움이 되는 형태"가 목표로, 프롬프트도 그 관점에서 설계했습니다.

- 요약: WHY/WHEN 중심의 개념 정리. 단순 코드 변환·반복 작업은 제외
- 퀴즈: 동작 원리·옵션·헷갈리는 지점 우선. 코드 생성 결과물은 제외
- AI가 자주 붙이는 `"A. 보기"`, `"①"` 접두사를 정규식으로 후처리해 깔끔한 보기로 정규화
- 숨김 처리한 메시지는 요약/퀴즈 입력에서도 제외

### 5. AI 서비스 사용량 스크래퍼 (5종)

ChatGPT/Claude/Codex/Gemini/Cursor의 구독 플랜·결제일·세션 사용량을 자동으로 읽어와 DB의 AI 서비스 레코드에 반영합니다.

Claude.ai의 Cloudflare 봇 탐지를 우회하기 위해 일반 headless Playwright 대신 **CDP(Chrome DevTools Protocol)** 로 사용자 Chrome 세션을 재사용합니다.

- `--remote-debugging-port=9222`로 띄운 실제 Chrome에 Playwright가 attach
- Chrome 창은 Windows API(`SetWindowPos -32000,-32000` + `WS_EX_TOOLWINDOW`)로 화면 밖으로 이동 — `SW_HIDE`는 렌더러를 절전 모드로 빠뜨려 페이지 inner_text 호출이 타임아웃 나기 때문
- usage 페이지만 `wait_until='networkidle'` 사용 — SPA가 페이지 로드 후 별도 API로 사용량 데이터를 가져오는 구조
- 첫 실행 ~5초 비용 절감을 위해 page만 close하고 Chrome 프로세스는 유지
- 5개 서비스가 같은 Chrome 인스턴스를 공유하므로 대시보드 새로고침은 순차 실행

### 6. AI 신문 스크랩 + 분석

네이버 뉴스 신문지면(1~5면)을 날짜별로 수집하고, 면접 준비용으로 GPT가 핵심 기업·태그·요약·예상 질문을 추출합니다.

- 스크랩은 `requests + BeautifulSoup` (네이버 SSR이라 Playwright 불필요)
- 분석은 사용자가 모델(`gpt-5-nano`/`mini`/`5`)을 선택해 트리거 — 토큰 한도 초과 시 명시적 RuntimeError로 잘림 방지
- 기업/태그 자동 추출 결과를 별도 필드로 분리해 전체 기간 필터 조회 가능

### 7. 인증과 데이터 격리

- 모든 라우터에 `Depends(get_current_user)` 주입
- `Authorization: Bearer <JWT>` 우선, 없으면 `pos_session` 쿠키 fallback — mk2 BFF 경유 호출과 직접 호출을 동시 지원
- 토큰 검증은 mk2 auth-service `/api/auth/me`에 위임 (단일 인증 서버 원칙)
- 모든 MongoDB/Qdrant 쿼리에 `owner_id` 조건 필수 — 다른 사용자 데이터 누출 방지

## 저장소 구조

```text
personal-operating-system-mk3/
├─ backend/app/
│  ├─ domain/                      # Conversation, Message, Article, AIService (프레임워크 의존 X)
│  ├─ application/
│  │  ├─ chat_service.py           # SSE 스트리밍, 비용 계산, 요약/퀴즈 생성
│  │  ├─ import_service.py         # 5종 임포트 오케스트레이션, S3 fallback
│  │  ├─ search_service.py         # 임베딩 + Qdrant 검색
│  │  ├─ news_service.py           # 신문 스크랩 + AI 분석
│  │  └─ ai_service_service.py     # AI 서비스 CRUD
│  ├─ adapter/
│  │  ├─ mongodb/                  # ConversationRepository, ArticleRepository 등
│  │  ├─ qdrant/                   # VectorRepository (1536차원 코사인)
│  │  ├─ importer/                 # chatgpt/claude/claude_code/codex/gemini 파서
│  │  └─ scraper/                  # CDP 기반 5종 + 네이버 뉴스 스크래퍼
│  ├─ api/v1/                      # health/chat/import/search/news/ai-services/scraper
│  └─ core/                        # config, auth, dependencies, s3
│
├─ frontend/app/                   # Nuxt 3 보조 UI
│  ├─ pages/                       # 대시보드 / chat / summaries / search / news / quiz
│  ├─ composables/                 # useChat, useSearch, useAiServices, useNews, useApi
│  └─ components/
│
├─ k8s/
│  ├─ base/                        # Namespace, ConfigMap, Secret, MongoDB, Qdrant, API, Web, Ingress
│  └─ overlays/aws/                # 외부 MongoDB/Qdrant, ECR 이미지 매핑, AWS 도메인 패치
│
├─ .github/workflows/ecr-push.yml  # ECR matrix 빌드 → self-hosted runner에서 k3s rollout restart
├─ compose.yaml                    # api + web + mongodb + qdrant (로컬 학습용)
├─ compose.data-box.yaml           # MongoDB + Qdrant만 분리 운영 (AWS data-box)
├─ Dockerfile.api / Dockerfile.web
└─ dev.ps1                         # 로컬 일괄 기동 스크립트
```

## API 요약

### 채팅

| Method | Endpoint | 설명 |
|---|---|---|
| `POST` | `/api/v1/chat/openai` | ChatGPT 채팅 (SSE) |
| `POST` | `/api/v1/chat/gemini` | Gemini 채팅 (SSE) |
| `POST` | `/api/v1/chat/claude` | Claude 채팅 (SSE) |
| `GET`  | `/api/v1/chat/{provider}/models` | provider별 모델 목록과 단가/제한 |
| `GET`  | `/api/v1/chat/conversations` | 대화 목록 (`include_hidden` 옵션) |
| `GET`  | `/api/v1/chat/conversations/{id}` | 대화 상세 |
| `GET`  | `/api/v1/chat/conversations/{id}/messages` | 메시지 목록 |
| `PATCH`/`DELETE` | `/api/v1/chat/conversations/{id}` | 숨김 토글, 삭제 |
| `PATCH`/`DELETE` | `/api/v1/chat/messages/{id}` | 메시지 수정·숨김·삭제 |
| `POST`/`DELETE` | `/api/v1/chat/conversations/{id}/summary` | AI 요약 생성/삭제 |
| `POST`/`DELETE` | `/api/v1/chat/conversations/{id}/quiz` | AI 퀴즈 생성/삭제 |

### 임포트 / 검색 / 뉴스 / 사용량

| Method | Endpoint | 설명 |
|---|---|---|
| `POST` | `/api/v1/import/{chatgpt-export\|claude-export\|claude-code\|jetbrains-codex\|gemini-takeout}` | 소스별 임포트 트리거 |
| `POST` | `/api/v1/import/upload/{service}` | S3로 임포트 파일 업로드 |
| `GET`  | `/api/v1/import/history` | 서비스별 마지막 임포트 시각/건수 |
| `GET`  | `/api/v1/search?q=...` | Qdrant 의미 검색 |
| `POST` | `/api/v1/search/index` | 전체 대화 재인덱싱 |
| `GET`/`POST` | `/api/v1/news`, `/api/v1/news/scrape` | 신문 기사 조회·날짜별 스크랩 |
| `POST` | `/api/v1/news/{id}/analyze` | 기사 AI 분석 (모델 선택) |
| `POST` | `/api/v1/scraper/{claude\|chatgpt\|codex\|gemini\|cursor}` | AI 서비스 사용량 스크래핑 |
| `GET`/`POST`/`PUT`/`DELETE` | `/api/v1/ai-services` | AI 구독 서비스 CRUD |

## 기술 스택

| 영역 | 기술 |
|---|---|
| Language | Python 3.11 |
| Backend | FastAPI 0.136, Pydantic v2, uvicorn |
| Persistence | MongoDB 7 (Motor 3.7 비동기 드라이버), Qdrant 1.14 (`AsyncQdrantClient`) |
| LLM SDK | `openai`, `anthropic`, `google-genai` |
| Scraping | Playwright (CDP), BeautifulSoup, requests |
| Auth | mk2 auth-service JWT 위임 검증, `pos_session` 쿠키 fallback |
| Storage | AWS S3 (boto3, `run_in_executor`로 비동기화) |
| Frontend | TypeScript, Nuxt 3 (Vue 3) |
| Infra | Docker Compose, Kubernetes, Kustomize, GitHub Actions OIDC, AWS ECR, k3s |

## 로컬 실행

### 1. 환경 파일 준비

```powershell
Copy-Item backend\.env.example backend\.env
```

주요 환경변수:

```text
MONGODB_URL=mongodb://pos:pos@localhost:27017
MONGODB_DB=pos_mk3
QDRANT_HOST=localhost
QDRANT_PORT=6333

OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=

AUTH_SERVICE_URL=http://127.0.0.1:3002    # mk2 auth-service
S3_BUCKET=                                # 비워두면 로컬 data/ 사용
```

### 2. Docker Compose로 전체 기동

```powershell
docker compose up -d --build
```

- mk3-api (FastAPI): `http://localhost:8001`
- mk3-web (Nuxt 3): `http://localhost:3003`
- MongoDB: `localhost:27017`
- Qdrant: HTTP `localhost:6333`, gRPC `localhost:6334`

### 3. 백엔드만 로컬 실행

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

### 4. 프론트엔드만 로컬 실행

```powershell
cd frontend
npm install
npm run dev
```

### 5. 일괄 기동

```powershell
.\dev.ps1
```

`dev.ps1`은 인프라(MongoDB/Qdrant)를 Docker Compose로 올리고 readiness를 확인한 뒤 백엔드/프론트를 함께 실행합니다.

## 배포와 운영 구성

- **`Dockerfile.api`** / **`Dockerfile.web`**: 멀티 스테이지 빌드, FastAPI(uvicorn)와 Nuxt(node) 분리 이미지
- **`compose.yaml`**: api + web + MongoDB + Qdrant 단일 로컬 스택
- **`compose.data-box.yaml`**: 운영 환경에서 MongoDB/Qdrant만 별도 EC2(data-box)로 분리해 띄울 때 사용. 비밀번호 필수 환경변수(`:?`) 강제
- **`k8s/base`**: Namespace, ConfigMap, Secret, MongoDB, Qdrant, API, Web, Ingress
- **`k8s/overlays/aws`**: 외부 MongoDB/Qdrant 연결 전제, ECR 이미지 매핑, AWS 도메인용 ingress 패치
- **`.github/workflows/ecr-push.yml`**: OIDC(`AWS_ROLE_TO_ASSUME`)로 AWS 자격 증명 발급 → matrix로 api/web 동시 빌드 → ECR push → self-hosted runner에서 `kubectl rollout restart`로 무중단 배포

## 설계 메모

- **Clean Architecture 4계층**: `api → application → adapter → domain`. 도메인은 `dataclass`만으로 정의해 FastAPI·Motor·Qdrant에 의존하지 않습니다. 단위 테스트와 인프라 교체(예: Qdrant → pgvector)가 용이합니다.
- **의존성 주입**: 인증·DB·외부 서비스는 모두 FastAPI `Depends`로 주입. 라우터 함수 시그니처만 봐도 어떤 외부 자원을 쓰는지 명확합니다.
- **소유권 격리**: 인증 사용자 ID는 모든 쿼리에 명시적으로 전달합니다. `find_by_id(id, owner_id)` 패턴으로 다른 사용자 리소스가 ID 추측만으로 노출되지 않도록 했습니다.
- **임포트의 멱등성**: `source_id` 기반 중복 검사로 같은 export 파일을 여러 번 임포트해도 안전합니다.
- **부가 작업 비격리**: 임포트나 요약 생성 시 부가적인 임베딩 호출이 실패해도 본 작업 응답을 막지 않도록 `try/except + warning` 로깅 처리. 사후 재인덱싱(`/search/index`)으로 복구 가능합니다.
- **AI 비용 가시화**: 모든 LLM 호출(채팅·요약·퀴즈·임베딩·뉴스 분석)에 단가 테이블 적용. 메시지/대화/기사 단위로 비용을 저장해 어떤 기능이 얼마를 썼는지 추적합니다.

## 관련 문서

- `k8s/README.md` — Kubernetes base/AWS overlay 적용 절차
- `CLAUDE.md` — 로컬 AI 에이전트 작업 가이드 (코드 컨벤션, 한국어 주석 규칙)
