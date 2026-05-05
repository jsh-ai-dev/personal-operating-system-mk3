# [도메인] 신문 기사(Article)와 AI 분석 결과(ArticleAnalysis) 도메인 모델
# 순수 Python 데이터 클래스 — DB/프레임워크 의존성 없이 비즈니스 개념만 정의

from dataclasses import dataclass, field


@dataclass
class ArticleAnalysis:
    # 숫자 포함 문장은 <span class="num">, 키워드 문장은 <span class="kw"> 로 마킹된 HTML
    highlighted_html: str
    # 개발자 관점 핵심 키워드 3개 [{keyword, explanation}]
    keywords: list
    # 지원 동기에 활용할 기업 제품/기술/사업 특징 요약
    motivation_summary: str
    # 현직자에게 물어볼 질문 2개 [{question, expected_answer}]
    questions: list
    analyzed_at: str
    analysis_model: str = ""
    analysis_cost_usd: float = 0.0


@dataclass
class Article:
    id: str
    date: str           # "2026-05-04"
    page_num: int       # 1~5 (신문 면)
    title: str
    url: str
    content: str
    # 스크랩 시 자동 추출 (Claude API)
    companies: list = field(default_factory=list)   # 언급 기업명
    tags: list = field(default_factory=list)         # 핵심 주제 태그
    scraped_at: str = ""
    # 버튼 클릭 시 생성
    analysis: ArticleAnalysis | None = None
