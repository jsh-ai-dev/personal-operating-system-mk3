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

## 사용자 배경

6년차 백엔드 개발자. Python/FastAPI/Vue/Nuxt/AI/Docker 등은 처음 접함.
설명은 주니어 수준으로 쉽고 친절하게. 당연한 것도 WHY 포함해서 설명.
