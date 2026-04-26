# CLAUDE.md — personal-operating-system-mk3

Claude는 이 프로젝트(mk3) 전담이다.

---

## 프로젝트 개요

MSA 기반 AI 서비스 플랫폼. Clean Code + Clean Architecture + OOP + REST API 지향.
이력서용 사이드 프로젝트이므로 실무 수준 코드 품질 유지. GitHub 공개 저장소처럼 관리.

**기술 스택**
- Backend: Python + FastAPI + MongoDB + Qdrant
- Frontend: TypeScript + Nuxt 3 (Vue.js)
- 실행환경: Docker (compose.yaml)
- IDE: PyCharm

---

## 프로젝트 구조

```
backend/app/
  domain/          # 도메인 모델 (순수 Python 객체)
  application/     # 비즈니스 로직 (서비스 레이어)
  adapter/
    mongodb/       # MongoDB 저장소 구현체
    qdrant/        # Qdrant 벡터 저장소 구현체
    scraper/       # AI 서비스 사용량 스크래퍼
  api/v1/          # FastAPI 라우터 (엔드포인트)
  core/            # 설정, 의존성 주입

frontend/app/
  pages/           # Nuxt 페이지 (라우팅 자동 생성)
  components/      # 재사용 Vue 컴포넌트
  composables/     # Vue 컴포저블 (상태/로직 분리)
```

---

## 주석 규칙 (필수)

모든 소스 파일에 **한국어 주석** 작성. 처음 접하는 기술이 많으므로 WHAT보다 WHY 위주로 설명.

**파일 상단 헤더** — 모든 파일에 반드시 포함:
```python
# backend 예시
# [파일 역할 한 줄 설명]
# [왜 이 레이어에 있는지, 어떤 책임을 지는지]
```
```typescript
// frontend 예시
// [파일 역할 한 줄 설명]
// [왜 이 파일이 필요한지, 어떤 책임을 지는지]
```

**인라인 주석** — 개념이 낯설거나 이유가 비자명한 코드에만 작성. 단순 반복 설명 금지.

---

## 작업 후 보고 형식 (필수)

작업 완료 후 반드시 수정/생성 파일 목록 출력:
- 학습 관점에서 중요한 파일에 ⭐ 표시
- 파일별 한 줄 역할 설명
- 경로는 프로젝트 루트 이후만 표시 (`backend/app/main.py` 형식)

---

## 커밋 규칙

- 커밋 전 파일 리스트 등 사용자가 확인하고 싶은 것이 있으면 **먼저 보여주고 커밋**
- `.env` 등 민감 정보 파일 커밋 금지
- 개인 대화 내용을 README 등 공개 문서에 노출 금지

---

## 파일 작업 방식

- 사용자가 파일을 직접 생성/수정하지 않음. Claude가 알아서 적절한 위치에 생성/수정
- 포트 충돌 등 프로젝트 간 연동 사항은 mk1/mk2 참고해서 판단

---

## 코드 품질 기준

- 실무 수준 지향. 맛보기 수준 코드 금지
- 불필요한 오버엔지니어링 금지
- 의미 없는 보일러플레이트 금지

---

## Claude Scraper 특이사항

`backend/app/adapter/scraper/claude_scraper.py` 수정 시 반드시 숙지:

- **CDP 방식 사용 이유**: Claude.ai는 Cloudflare 봇 탐지로 일반 headless Playwright 차단됨. `--remote-debugging-port=9222`로 뜬 실제 Chrome 세션에 CDP로 붙는 방식 사용
- **SW_HIDE 금지**: Chrome 렌더러 절전 모드 전환으로 타임아웃 발생. 대신 `SetWindowPos`로 화면 밖 이동
- **usage 페이지만 networkidle 사용**: SPA가 페이지 로드 후 별도 API로 데이터를 불러오기 때문
- **Chrome 프로세스 유지**: 첫 실행 비용 ~5초. `page.close()`만 하고 프로세스는 유지
- **Chrome 프로필**: `C:\temp\chrome-debug` — 여기서 claude.ai 로그인 되어 있어야 동작

---

## 진행 중인 작업: AI Chat 기능

### 개요
여러 AI 서비스의 요청/응답을 한 곳에 저장하고, 이후 요약/검색/퀴즈화하는 기능.
오늘은 데이터 수집(Method A/B) 구현이 목표. 나중에 Qdrant 기반 의미 검색, 요약, 퀴즈 추가 예정.

### 대상 서비스
ChatGPT(OpenAI), Gemini(Google), Claude(Anthropic) 계열

### Method A — API 프록시 방식
- 이 앱이 각 AI API를 직접 호출하는 프록시 역할
- 요청/응답 + 토큰/비용을 MongoDB에 저장
- **ChatGPT A 방식 구현 완료** (마지막 커밋: SSE 스트리밍 채팅 + 비용 계산)

### Method B — 구독 서비스 데이터 수집 방식
- 일반 사용자(API 아닌 구독형)의 기존 대화 내역 수집
- 완벽 동작보다 "어디까지 가능한가" 탐색이 목적
- **ChatGPT B 방식 구현 예정 (현재 작업)**
- 구현 순서: CDP 인터셉트 PoC → 공식 Export(JSON) 임포트 → 브라우저 확장 고려
  - CDP: `api.openai.com/backend-api/conversation/{id}` 응답 인터셉트
  - Export: ChatGPT Settings → Export Data → JSON 파일 임포트

### 이후 비용 절감 기능 (A 방식 추가 예정)
- Semantic Cache (Qdrant 유사도 검색으로 캐시 응답)
- Prompt Caching (Claude cache_control / GPT prefix caching)
- 모델 라우팅 (질문 복잡도에 따라 저렴한 모델 선택)
- 컨텍스트 압축 (히스토리 요약 후 전송)

---

## 사용자 배경

6년차 백엔드 개발자. Python/FastAPI/Vue/Nuxt/AI/Docker 등은 처음 접함.
설명은 주니어 수준으로 쉽고 친절하게. 당연한 것도 WHY 포함해서 설명.
