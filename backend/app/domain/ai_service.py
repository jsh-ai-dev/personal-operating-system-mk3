# [도메인 모델] AI 서비스(ChatGPT, Claude 등) 구독 정보를 나타내는 핵심 데이터 구조
# Clean Architecture에서 가장 안쪽 레이어 — DB나 프레임워크에 의존하지 않는 순수한 데이터 클래스

from dataclasses import dataclass


@dataclass
class AIService:
    id: str
    name: str            # 서비스명 (예: ChatGPT, Claude)
    plan_name: str       # 플랜명 (예: Plus, Pro, Max)
    monthly_cost: float  # 월 구독료
    currency: str        # 통화 (USD, KRW)
    billing_day: int     # 매월 결제일 (1~31)
    usage_limit: float | None    # 사용 한도 (입력하지 않으면 None)
    usage_current: float | None  # 현재 사용량 (입력하지 않으면 None)
    usage_unit: str | None       # 사용량 단위 (예: messages / 3h, requests / month)
    billing_url: str | None      # 청구 설정 페이지 URL
    notes: str | None            # 메모
