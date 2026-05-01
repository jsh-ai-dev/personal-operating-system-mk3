# Personal Operating System mk3

FastAPI와 Nuxt 3 기반의 AI 서비스 레이어입니다.

벡터 검색(Qdrant)과 LLM을 결합해 자연어로 데이터를 검색하고 자동화 작업을 수행합니다.
[mk1 (Spring Boot)](https://github.com/jsh-ai-dev/personal-operating-system-mk1) ·
[mk2 (NestJS/Next.js)](https://github.com/jsh-ai-dev/personal-operating-system-mk2)와 함께 MSA 구조를 구성합니다.

## 기술 스택

| 영역 | 기술 |
|---|---|
| Backend | Python 3.11, FastAPI |
| Frontend | TypeScript, Nuxt 3, Vue 3 |
| Database | MongoDB |
| Vector Store | Qdrant |
| Infra | Docker, Docker Compose |

## 설계 방향

- **Clean Architecture**: domain / application / adapter 계층 분리
- **TDD**: 핵심 도메인 로직 단위 테스트 우선
- **REST API**: 명확한 엔드포인트 설계, HTTP 상태코드 준수
- **RAG 파이프라인**: 문서 저장 → 벡터 임베딩 → 유사도 검색 → LLM 생성

> RAG(Retrieval-Augmented Generation): LLM이 학습 데이터에 없는 내용을 답변할 수 있도록,
> 질문과 관련된 문서를 먼저 검색해 LLM에 함께 전달하는 방식입니다.

## 아키텍처

```
[Nuxt 3 UI]
     │
     ▼
[FastAPI Backend]
     ├── MongoDB   : 원본 문서 저장
     ├── Qdrant    : 벡터 임베딩 저장 및 유사도 검색
     └── LLM API   : 답변 생성 (OpenAI / 기타)

MSA 연동:
  mk1 (노트) ──┐
  mk2 (일정) ──┼──▶ mk3 AI Service
```

## 현재 구현 범위

- Docker Compose 인프라 구성 (MongoDB, Qdrant)
- FastAPI 백엔드 기본 구조 (Clean Architecture)
- Nuxt 3 프론트엔드 기본 구조 및 백엔드 연결

## 로컬 실행 포트

| 서비스 | 포트 |
|---|---|
| FastAPI | 8001 |
| Nuxt 3 | 3003 |
| MongoDB | 27017 |
| Qdrant HTTP | 6333 |
| Qdrant gRPC | 6334 |

## 실행 방법

### 인프라 실행 (MongoDB + Qdrant)

```bash
docker compose up -d
```

### 백엔드 실행

```bash
cd backend
cp .env.example .env   # 최초 1회
uvicorn app.main:app --reload --port 8001
```

### 프론트엔드 실행

```bash
cd frontend
npm install            # 최초 1회
npm run dev
```

## 환경변수

민감 정보는 `.env` 파일로 관리합니다 (Git에 포함되지 않습니다).

```bash
cp .env.example .env
# .env 파일을 열어 필요한 값 입력
```

주요 환경변수:

| 변수 | 설명 | 예시 |
|---|---|---|
| `MONGODB_URL` | MongoDB 접속 URL | `mongodb://localhost:27017` |
| `QDRANT_HOST` | Qdrant 호스트 | `localhost` |
| `QDRANT_PORT` | Qdrant 포트 | `6333` |
| `OPENAI_API_KEY` | LLM API 키 | `sk-...` |

## 로드맵

- [x] Docker Compose 인프라 구성 (MongoDB, Qdrant)
- [x] FastAPI 백엔드 기본 구조 (Clean Architecture)
- [x] Nuxt 3 UI 연동
- [ ] 문서 저장 API (MongoDB)
- [ ] 벡터 임베딩 및 Qdrant 인덱싱
- [ ] RAG 기반 자연어 검색 API
- [ ] mk1 / mk2 데이터 연동

## Kubernetes 배포

`mk3`도 `mk1`, `mk2`와 같은 방식으로 Kubernetes 배포 파일을 포함합니다.

- 기본 배포: `k8s/base` (MongoDB + Qdrant + mk3 API)
- AWS 오버레이: `k8s/overlays/aws` (외부 MongoDB/Qdrant + mk3 API)

자세한 적용 순서는 `k8s/README.md`를 참고하세요.
