# Personal Operating System mk3

**여러 AI 서비스의 대화를 한 곳에 수집·저장하고, 요약·퀴즈화하는 AI 통합 플랫폼입니다.**

[mk1 (Kotlin/Spring Boot)](https://github.com/jsh-ai-dev/personal-operating-system-mk1) ·
[mk2 (TypeScript/Next.js · NestJS)](https://github.com/jsh-ai-dev/personal-operating-system-mk2)
와 함께 3서비스 MSA 플랫폼을 구성합니다.

---

## 개요

OpenAI(ChatGPT), Google Gemini, Anthropic Claude에 직접 API를 호출하고, 대화 기록을 MongoDB에 저장합니다.
저장된 대화는 AI로 요약하거나 4지선다 퀴즈로 변환해 학습 자료로 활용할 수 있습니다.

구독형 서비스에서 이미 나눈 대화(JetBrains Codex, Claude, Gemini Takeout)도 파일 임포트로 한 곳에 가져올 수 있습니다.

---

## 기술 스택

| 영역 | 기술 |
|---|---|
| Backend | Python 3.11, FastAPI 0.136, Motor 3.7 (비동기 MongoDB 드라이버) |
| Frontend | TypeScript, Nuxt 3, Vue 3 |
| Database | MongoDB 7 |
| Vector Store | Qdrant 1.14 |
| LLM | OpenAI API, Google Gemini API, Anthropic Claude API |
| Auth | JWT (mk2 auth-service 연동) |
| Infra | Docker, Docker Compose, Kubernetes |

---

## 시스템 아키텍처

### MSA 전체 구성

```
브라우저
  │
  ▼
mk2 · Next.js (BFF, :3000)
  ├─ /api/auth/*    ──▶  auth-service (:3002)   JWT 발급·검증·로그아웃
  ├─ /api/backend/* ──▶  NestJS (:3001)          달력·목표 API
  ├─ /api/notes/*   ──▶  mk1 Spring (:8080)      노트·파일·검색 API
  └─ /api/mk3/*     ──▶  mk3 FastAPI (:8001)     AI 채팅·임포트 API  ◀ 이 프로젝트
                             │
                      ┌──────┴──────┐
                      MongoDB       Qdrant
```

### mk3 내부 구조 (Clean Architecture)

```
api/v1 (라우터)
    │  HTTP 요청·응답만 담당
    ▼
application (서비스)
    │  비즈니스 로직, LLM 호출, 비용 계산
    ▼
adapter (어댑터)
    ├─ mongodb/    MongoDB 저장소 구현체
    ├─ importer/   파일 파싱 로직
    └─ scraper/    웹 스크래핑 로직
    ▼
domain (도메인 모델)
    Conversation, Message — 순수 Python 객체, 프레임워크 의존 없음
```

인증은 FastAPI 의존성 주입으로 처리합니다. 모든 엔드포인트에서 `get_current_user`를 주입하면 mk2 auth-service에 토큰 검증 요청을 보내고, 검증된 `user_id`를 반환합니다.

---

## 주요 기능

### 1. 멀티 LLM 채팅 (SSE 스트리밍)

OpenAI · Gemini · Claude API를 직접 호출합니다. 응답은 SSE(Server-Sent Events)로 실시간 스트리밍하고, 토큰 수와 비용을 메시지·대화 단위로 MongoDB에 저장합니다.

```
POST /api/v1/chat/openai   → ChatGPT 스트리밍
POST /api/v1/chat/gemini   → Gemini 스트리밍
POST /api/v1/chat/claude   → Claude 스트리밍
```

**비용 추적** — 모델별 단가(USD/1M 토큰)를 상수로 관리하고, 응답 완료 시 토큰 수로 비용을 계산해 저장합니다. Gemini 무료 티어는 RPM·RPD 제한도 별도 관리합니다.

```python
OPENAI_PRICING = {
    "gpt-5-mini":  {"input": 0.25,  "output": 2.00},
    "gpt-5":       {"input": 1.25,  "output": 10.00},
    "gpt-5.4":     {"input": 2.50,  "output": 15.00},
}
CLAUDE_PRICING = {
    "claude-haiku-4-5":  {"input": 1.00,  "output": 5.00},
    "claude-sonnet-4-6": {"input": 3.00,  "output": 15.00},
    "claude-opus-4-7":   {"input": 5.00,  "output": 25.00},
}
```

### 2. 대화 임포트 (4종)

| 버튼 | 소스 | 방식 |
|---|---|---|
| Codex 가져오기 | JetBrains AI Assistant | `.events` 파일 파싱 (base64 인코딩 JSON) |
| Claude Code 가져오기 | Claude Code 로컬 트랜스크립트 | `.jsonl` 파일 파싱 |
| Claude 가져오기 | Claude.ai 데이터 내보내기 | `conversations.json` 파싱 |
| Gemini 가져오기 | Google Takeout | `내활동.json` 파싱 (날짜별 그룹핑) |

`source_id` 기반 중복 검사로 같은 대화를 두 번 임포트해도 안전합니다.

**JetBrains Codex `.events` 파싱 — base64 이중 인코딩 구조**

```
[파일명: xxxxxx.events]
AUI_EVENTS_V1|base64(JSON) 형식
  └─ JSON 배열 내 각 이벤트도 base64 인코딩
       └─ ChatSessionUserPromptEvent  : 사용자 메시지
          MarkdownBlockUpdatedEvent   : 어시스턴트 응답 (점진적 업데이트 → 마지막만 사용)
```

### 3. AI 대화 요약

저장된 대화를 OpenAI API로 요약합니다. 요약 결과와 사용된 모델·비용을 대화 도큐먼트에 함께 저장합니다.

```
POST /api/v1/chat/conversations/{id}/summary
```

`/summaries` 페이지에서 요약된 대화를 카드 형태로 모아볼 수 있습니다. 응답에 포함된 마크다운은 외부 라이브러리 없이 정규식으로 변환해 렌더링합니다.

### 4. AI 퀴즈 생성

대화 요약을 기반으로 4지선다 퀴즈를 생성합니다. 퀴즈 프롬프트는 "처음 배우는 기술 맥락"을 고려해 코드 생성보다 동작 원리·설계 의도 중심의 문제를 생성하도록 설계했습니다.

```
POST /api/v1/chat/conversations/{id}/quiz
```

`/quiz/[id]` 페이지에서 1문제씩 풀고, 선택 즉시 정답과 해설을 확인합니다. "정답 보기" 버튼으로 선택 없이 건너뛸 수도 있습니다.

### 5. 소스 타입 자동 분류

임포트된 대화는 `model` 값으로 소스를 자동 분류합니다.

| model 값 | 소스 | 타입 |
|---|---|---|
| `codex` | JetBrains AI Assistant | 코딩 |
| `claude-code` | Claude Code | 코딩 |
| `claude` | Claude.ai 내보내기 | 채팅 임포트 |
| `gemini` | Google Takeout | 채팅 임포트 |
| 구체적 모델명 (`gpt-5-mini` 등) | API 직접 호출 | API |

---

## API 엔드포인트

### 채팅

| 메서드 | 경로 | 설명 |
|---|---|---|
| `GET` | `/api/v1/chat/conversations` | 대화 목록 (필터·날짜 범위) |
| `POST` | `/api/v1/chat/openai` | ChatGPT 채팅 (SSE 스트리밍) |
| `POST` | `/api/v1/chat/gemini` | Gemini 채팅 (SSE 스트리밍) |
| `POST` | `/api/v1/chat/claude` | Claude 채팅 (SSE 스트리밍) |
| `GET` | `/api/v1/chat/conversations/{id}` | 대화 상세 |
| `GET` | `/api/v1/chat/conversations/{id}/messages` | 메시지 목록 |
| `PATCH` | `/api/v1/chat/conversations/{id}` | 대화 숨김 처리 |
| `PATCH` | `/api/v1/chat/messages/{id}` | 메시지 수정·숨김 처리 |
| `DELETE` | `/api/v1/chat/conversations/{id}` | 대화 삭제 |
| `DELETE` | `/api/v1/chat/messages/{id}` | 메시지 삭제 |
| `POST` | `/api/v1/chat/conversations/{id}/summary` | AI 요약 생성 |
| `POST` | `/api/v1/chat/conversations/{id}/quiz` | AI 퀴즈 생성 |

### 임포트

| 메서드 | 경로 | 설명 |
|---|---|---|
| `POST` | `/api/v1/import/jetbrains-codex` | JetBrains Codex `.events` 임포트 |
| `POST` | `/api/v1/import/claude-code` | Claude Code 트랜스크립트 임포트 |
| `POST` | `/api/v1/import/claude-export` | Claude 데이터 내보내기 임포트 |
| `POST` | `/api/v1/import/gemini-takeout` | Google Takeout 임포트 |

### 기타

| 메서드 | 경로 | 설명 |
|---|---|---|
| `GET` | `/api/v1/health` | 헬스 체크 |
| `GET/POST/PUT/DELETE` | `/api/v1/ai-services` | AI 서비스 설정 관리 |

---

## 도메인 모델

### Conversation

```python
@dataclass
class Conversation:
    id: str
    owner_id: str                    # 사용자 ID (JWT subject)
    provider: str                    # "openai" | "anthropic" | "google"
    model: str                       # "gpt-5-mini", "claude-sonnet-4-6" 등
    title: str
    message_count: int
    total_tokens_input: int
    total_tokens_output: int
    total_cost_usd: float
    summary: str | None              # AI 요약 결과
    quiz: list | None                # [{"question", "options", "answer", "explanation"}]
    source_id: str | None            # 임포트 출처 (중복 방지)
    is_hidden: bool = False
```

### Message

```python
@dataclass
class Message:
    id: str
    conversation_id: str
    role: str                        # "user" | "assistant"
    content: str
    model: str | None
    tokens_input: int | None
    tokens_output: int | None
    cost_usd: float | None
    is_hidden: bool = False
```

---

## 프로젝트 구조

```
personal-operating-system-mk3/
├─ backend/
│  └─ app/
│     ├─ domain/             # 도메인 모델 (프레임워크 의존 없음)
│     ├─ application/        # 비즈니스 로직
│     │  ├─ chat_service.py     LLM 호출·스트리밍·비용 계산
│     │  └─ import_service.py   파일 임포트 오케스트레이션
│     ├─ adapter/
│     │  ├─ mongodb/            MongoDB 저장소 구현체
│     │  ├─ importer/           각 서비스별 파일 파서
│     │  └─ scraper/            CDP 기반 웹 스크래퍼
│     ├─ api/v1/             # FastAPI 라우터
│     └─ core/               # 설정, JWT 검증, 의존성 주입
│
├─ frontend/
│  └─ app/
│     ├─ pages/
│     │  ├─ chat/               대화 목록·상세
│     │  ├─ summaries/          요약 모음
│     │  └─ quiz/               퀴즈 목록·풀기
│     ├─ composables/           API 호출·상태 관리
│     └─ components/            재사용 UI 컴포넌트
│
├─ k8s/
│  ├─ base/                  Kubernetes 기본 배포
│  └─ overlays/aws/          AWS 환경 오버레이 (외부 DB 연결)
│
├─ compose.yaml              FastAPI + MongoDB + Qdrant
└─ Dockerfile.api            멀티 스테이지 빌드
```

---

## 로컬 실행

### 사전 요구사항

- Docker Desktop
- Python 3.11+
- Node.js 20+

### 인프라 실행 (MongoDB + Qdrant)

```bash
docker compose up -d
```

### 백엔드 실행

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env        # 최초 1회, API 키 설정 필요
uvicorn app.main:app --reload --port 8001
```

### 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev
```

### 환경변수 주요 항목

| 변수 | 설명 |
|---|---|
| `MONGODB_URL` | MongoDB 접속 URL |
| `QDRANT_HOST` / `QDRANT_PORT` | Qdrant 접속 정보 |
| `AUTH_SERVICE_URL` | mk2 auth-service URL (JWT 검증용) |
| `OPENAI_API_KEY` | OpenAI API 키 |
| `GEMINI_API_KEY` | Google Gemini API 키 |
| `ANTHROPIC_API_KEY` | Anthropic Claude API 키 |

### 실행 포트

| 서비스 | 포트 |
|---|---|
| FastAPI | 8001 |
| Nuxt 3 | 3003 |
| MongoDB | 27017 |
| Qdrant HTTP | 6333 |
| Qdrant gRPC | 6334 |

---

## Kubernetes 배포

```
k8s/base/          FastAPI + MongoDB + Qdrant (기본 구성)
k8s/overlays/aws/  외부 MongoDB·Qdrant 사용 시 패치 (AWS 환경)
```

```bash
# 로컬 클러스터
kubectl apply -k k8s/base

# AWS
kubectl apply -k k8s/overlays/aws
```
