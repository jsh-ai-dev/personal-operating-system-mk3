# [도메인 모델] AI 서비스(ChatGPT, Claude 등) 구독 정보를 나타내는 핵심 데이터 구조
# Clean Architecture에서 가장 안쪽 레이어 — DB나 프레임워크에 의존하지 않는 순수한 데이터 클래스

from dataclasses import dataclass


@dataclass
class AIService:
    id: str
    name: str                     # 서비스명 (예: ChatGPT, Claude)
    plan_name: str | None         # 플랜명 (예: Plus, Pro, Max) — 스크래핑으로 채워질 수 있어 선택
    monthly_cost: float | None    # 월 구독료 — 선택
    currency: str                 # 통화 (USD, KRW)
    billing_day: int | None       # 매월 결제일 (1~31) — 선택
    next_billing_date: str | None   # 다음 결제 전체 날짜 (ISO 8601 또는 한국어 형식)
    usage_limit: float | None    # 사용 한도 (입력하지 않으면 None)
    usage_current: float | None  # 현재 사용량 (입력하지 않으면 None)
    usage_unit: str | None       # 사용량 단위 (예: messages / 3h, requests / month)
    billing_url: str | None      # 청구 설정 페이지 URL
    notes: str | None            # 메모
