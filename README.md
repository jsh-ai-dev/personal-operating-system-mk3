# Personal Operating System mk3

`mk3`는 Personal Operating System의 AI 데이터 백엔드입니다. 여러 LLM 서비스의 대화 export를 가져와 MongoDB에 저장하고, Qdrant 벡터 검색, AI 요약/퀴즈, SSE 채팅, AI 뉴스 분석, 구독 서비스 사용량 스크래핑을 제공합니다.

실사용 메인 화면은 `mk2`의 Next.js 앱입니다. `mk3`는 FastAPI API를 제공하고, 포함된 Nuxt 앱은 보조 UI와 기능 실험용으로 유지됩니다.

## 시스템 구조

```text
mk2 Next.js BFF :3000
  └─ /api/mk3/*  ->  mk3 FastAPI :8001

mk3 FastAPI
  ├─ MongoDB      # 대화, 메시지, 기사, AI 서비스, import history
  ├─ Qdrant       # 대화 임베딩 벡터 검색
  ├─ Kafka        # import 이후 재색인, 뉴스 스크랩/분석 비동기 작업
  ├─ External AI  # OpenAI, Anthropic, Google Gemini
  ├─ Chrome CDP   # ChatGPT, Codex, Claude, Gemini, Cursor 사용량 스크래핑
  └─ S3 optional  # export 파일 업로드/import 저장소
```

인증은 직접 JWT를 해석하지 않고 mk2 auth-service의 `/api/auth/me`에 위임합니다. 모든 주요 쿼리는 `owner_id`를 조건으로 사용해 사용자별 데이터를 분리합니다.

## 기능

### LLM 채팅

- OpenAI, Gemini, Claude API를 SSE로 스트리밍
- 대화와 메시지 저장, 숨김 처리, 수정, 삭제
- assistant 메시지별 모델, 토큰, 예상 비용 저장
- provider별 모델 목록과 가격/제한 정보 제공

### 대화 import

지원 소스:

| 소스 | 입력 |
|---|---|
| ChatGPT export | `conversations.json` |
| Claude.ai export | `conversations.json` |
| Claude Code | `.jsonl` transcript 디렉터리 |
| JetBrains Codex | `.events` 파일 |
| Gemini Takeout | Google Takeout JSON |

`source_id` 기반으로 중복 import를 건너뛰며, import 직후 OpenAI API key가 있으면 Qdrant 임베딩까지 진행합니다. Kafka가 켜져 있으면 `mk3.conversation.index-requested.v1` 이벤트로 index worker가 처리하고, 꺼져 있으면 요청 흐름에서 직접 처리합니다.

### 검색, 요약, 퀴즈

- OpenAI `text-embedding-3-small`로 대화 임베딩
- Qdrant cosine 검색과 MongoDB 상세 정보 병합
- 저장된 대화를 OpenAI 모델로 요약
- 요약 기반 4지선다 퀴즈 생성/풀이
- 임베딩, 요약, 퀴즈 비용 추적

### AI 뉴스

- 네이버 뉴스 날짜별 스크랩
- 기업/태그 자동 추출
- 기사별 AI 분석, 예상 질문/답변 생성
- Kafka 기반 스크랩/분석 작업과 BackgroundTask fallback

### AI 서비스 Dashboard

- ChatGPT, Codex, Claude, Claude Code, Gemini, Cursor 등 구독 서비스 CRUD
- 월 비용, 결제일, 사용량, 청구 URL, 메모 관리
- 실제 Chrome 세션에 CDP로 붙어 사용량/결제 정보를 스크래핑
- ChatGPT/Codex, Claude/Claude Code처럼 같은 구독을 공유하는 서비스의 비용 중복 집계 방지

## 저장소 구조

```text
personal-operating-system-mk3/
├─ backend/app/
│  ├─ api/v1/                  # health, chat, import, search, news, scraper, ai-services
│  ├─ application/             # chat/search/import/news/ai-service 유스케이스
│  ├─ adapter/
│  │  ├─ importer/             # chatgpt, claude, claude-code, codex, gemini parser
│  │  ├─ mongodb/              # repository 구현
│  │  ├─ qdrant/               # vector repository
│  │  └─ scraper/              # CDP/requests 기반 scraper
│  ├─ core/                    # config, auth, dependency, S3
│  ├─ domain/                  # Conversation, Message, Article, AIService
│  └─ workers/                 # Kafka index/news worker
├─ frontend/app/               # Nuxt 3 보조 UI
├─ k8s/                        # Kubernetes base/AWS overlay
├─ compose.yaml                # api, web, workers, MongoDB, Qdrant, Kafka
├─ compose.data-box.yaml       # MongoDB/Qdrant/Kafka 분리 운영용
└─ dev.ps1                     # 로컬 통합 실행 스크립트
```

## 주요 API

| 영역 | Endpoint | 설명 |
|---|---|---|
| Health | `GET /api/v1/health` | API, MongoDB, Qdrant 상태 |
| Chat | `POST /api/v1/chat/openai`, `/gemini`, `/claude` | SSE 채팅 |
| Chat | `GET /api/v1/chat/conversations`, `GET /api/v1/chat/conversations/{id}/messages` | 대화/메시지 조회 |
| Chat | `PATCH/DELETE /api/v1/chat/conversations/{id}`, `PATCH/DELETE /api/v1/chat/messages/{id}` | 숨김, 수정, 삭제 |
| Summary/Quiz | `POST/DELETE /api/v1/chat/conversations/{id}/summary`, `/quiz` | 요약/퀴즈 생성과 삭제 |
| Import | `POST /api/v1/import/{source}` | export import 실행 |
| Import | `POST /api/v1/import/upload/{source}` | S3 import 파일 업로드 |
| Import | `GET /api/v1/import/history`, `GET/DELETE /api/v1/import/uploads/{source}` | import 이력과 업로드 관리 |
| Search | `GET /api/v1/search?q=...`, `POST /api/v1/search/index` | 벡터 검색과 전체 재색인 |
| News | `POST /api/v1/news/scrape`, `GET /api/v1/news`, `POST /api/v1/news/{id}/analyze` | 뉴스 수집/조회/분석 |
| Scraper | `POST /api/v1/scraper/{claude|chatgpt|codex|gemini|cursor}` | 구독 사용량 동기화 |
| AI Services | `GET/POST/PUT/DELETE /api/v1/ai-services` | 구독 서비스 CRUD |

## 기술 스택

| 영역 | 기술 |
|---|---|
| Backend | Python 3.11, FastAPI, Pydantic v2, uvicorn |
| Persistence | MongoDB 7, Motor |
| Vector Search | Qdrant 1.14, OpenAI embeddings |
| LLM SDK | openai, anthropic, google-genai |
| Async jobs | Kafka, aiokafka |
| Scraping | Playwright CDP, BeautifulSoup, requests |
| Storage | AWS S3 optional, local `data/` fallback |
| Frontend | Nuxt 3, Vue 3 |
| Infra | Docker Compose, Kubernetes, Kustomize, GitHub Actions OIDC, AWS ECR, k3s |

## 로컬 실행

### 1. 환경 파일 준비

```powershell
Copy-Item backend\.env.example backend\.env
```

주요 값:

```text
MONGODB_URL=mongodb://pos:pos@localhost:27017
MONGODB_DB=pos_mk3
QDRANT_HOST=localhost
QDRANT_PORT=6333
AUTH_SERVICE_URL=http://127.0.0.1:3002

OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=

KAFKA_ENABLED=false
S3_BUCKET=
```

`AUTH_SERVICE_URL`은 mk2 auth-service 주소입니다. mk2 BFF를 통하지 않고 mk3 API를 직접 호출할 때도 Bearer JWT 또는 `pos_session` 쿠키가 필요합니다.
백엔드를 직접 실행할 때는 `KAFKA_ENABLED=false`로 시작할 수 있고, `compose.yaml`과 `dev.ps1`은 Kafka와 worker까지 쓰도록 이 값을 실행 환경에서 `true`로 덮어씁니다.

### 2. Docker Compose로 전체 실행

```powershell
docker compose up -d --build
```

인증이 필요한 대부분의 API는 mk2 auth-service(`:3002`)가 떠 있어야 동작합니다. `/api/v1/health`는 인증 없이 MongoDB와 Qdrant 연결 상태를 확인할 수 있습니다.

기본 포트:

- FastAPI: `http://localhost:8001`
- Nuxt 보조 UI: `http://localhost:3003`
- MongoDB: `localhost:27017`
- Qdrant HTTP: `localhost:6333`
- Kafka external: `localhost:9092`

### 3. 개발용 통합 실행

```powershell
.\dev.ps1
```

스크립트는 MongoDB, Qdrant, Kafka를 올리고 Kafka topic을 만든 뒤 FastAPI, index worker, news worker, Nuxt dev server를 job으로 실행합니다.

### 4. 백엔드만 직접 실행

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

### 5. Nuxt 보조 UI만 실행

```powershell
cd frontend
npm install
npm run dev
```

## 테스트

```powershell
cd backend
pytest
```

테스트는 import parser, S3 import 경로, ChatGPT/Claude/Codex 구독일 계산, scraper 보조 파서, billing day 변환 등을 검증합니다.

## 배포 구성

- `Dockerfile.api`, `Dockerfile.web`: FastAPI와 Nuxt 이미지 분리
- `compose.yaml`: api, web, index-worker, news-worker, MongoDB, Qdrant, Kafka 로컬 스택
- `compose.data-box.yaml`: MongoDB/Qdrant/Kafka를 별도 data-box로 운영할 때 사용
- `k8s/base`: Namespace, ConfigMap, Secret 예시, MongoDB, Qdrant, API, Web, Ingress
- `k8s/overlays/aws`: 외부 데이터 서비스, ECR 이미지, API/Web/worker 배포 패치
- `.github/workflows/ecr-push.yml`: 수동 실행으로 api/web 이미지를 ECR에 push하고 self-hosted runner에서 k3s rollout restart
