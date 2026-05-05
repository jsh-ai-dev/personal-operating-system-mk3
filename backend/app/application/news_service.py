# [서비스] 뉴스 스크래핑, 기업명·태그 자동 추출, 기사 AI 분석을 담당하는 비즈니스 로직
# 스크랩 시: API 호출 없음 (텍스트 수집만)
# 분석 버튼 클릭 시: 선택한 GPT 모델로 메타·키워드·요약·질문 추출, 하이라이팅은 로컬 처리

import json
import re
from datetime import datetime, timezone

from openai import OpenAI

from app.adapter.mongodb.article_repository import ArticleRepository
from app.adapter.scraper import naver_news_scraper
from app.application.chat_service import OPENAI_PRICING
from app.core.config import settings
from app.domain.article import Article

DEFAULT_MODEL = "gpt-5-mini"

# 전자신문 oid (기본값)
_DEFAULT_OID = "030"

# 숫자·날짜·퍼센트 포함 문장 판별
_NUM_PATTERN = re.compile(r"[\d]+[,.]?[\d]*\s*(%|년|월|일|억|조|만|개|명|건|배|배율|GW|MW|nm|인치)?")


def _client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _chat(prompt: str, max_tokens: int, model: str) -> tuple[str, int, int]:
    """(content, tokens_input, tokens_output) 반환"""
    resp = _client().chat.completions.create(
        model=model,
        max_completion_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    choice = resp.choices[0]
    content = choice.message.content or ""
    if choice.finish_reason == "length":
        raise RuntimeError(
            f"{model} 응답이 토큰 한도({max_tokens})에서 잘렸습니다. "
            f"응답 길이: {len(content)}자"
        )
    content = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    usage = resp.usage
    return content, (usage.prompt_tokens if usage else 0), (usage.completion_tokens if usage else 0)


def _build_highlighted_html(content: str, keywords: list[str]) -> str:
    """
    AI가 뽑은 키워드·기업명을 기준으로 서버에서 직접 하이라이팅한다.
    숫자 포함 문장 → <span class="num">, 키워드 포함 문장 → <span class="kw">
    API 토큰을 쓰지 않아 비용 절감.
    """
    # 키워드 매칭용 패턴 (대소문자 무시)
    kw_pattern = re.compile(
        "|".join(re.escape(k) for k in keywords if k),
        re.IGNORECASE,
    ) if keywords else None

    lines = content.splitlines()
    html_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            html_lines.append("")
            continue
        escaped = stripped.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if _NUM_PATTERN.search(stripped):
            html_lines.append(f'<span class="num">{escaped}</span>')
        elif kw_pattern and kw_pattern.search(stripped):
            html_lines.append(f'<span class="kw">{escaped}</span>')
        else:
            html_lines.append(escaped)

    return "<br>".join(html_lines)


def _analyze(title: str, content: str, model: str) -> dict:
    """
    선택한 GPT 모델로 companies, tags, keywords, motivation_summary, questions를 추출한다.
    highlighted_html은 응답에서 제외하고 로컬에서 생성해 토큰 비용을 절감한다.
    분석에 사용한 모델명과 비용(USD)도 함께 반환한다.
    """
    prompt = f"""다음 기사를 분석해서 JSON만 반환해줘. 면접 준비를 위해 기업을 조사하는 용도야.

제목: {title}
내용: {content}

{{
  "companies": ["기사의 주제가 되는 핵심 기업 1~2개만 (언급만 된 기업 제외)"],
  "tags": ["기사의 핵심 주제 태그 1~3개 (예: 반도체, AI, 파운드리)"],
  "keywords": [{{"keyword": "개발자에게 중요한 기술 키워드", "explanation": "한 줄 설명"}}],
  "motivation_summary": "지원 동기에 활용할 기업 제품·기술·사업 특징 요약 (3~5문장)",
  "questions": [{{"question": "기사만으로 알기 어려운 내용을 현직자에게 묻는 질문", "expected_answer": "예상 답변 2~3문장"}}]
}}

keywords는 정확히 3개, questions는 정확히 2개 반환해줘."""

    raw, tokens_in, tokens_out = _chat(prompt, 3000, model)
    data = json.loads(raw)

    pricing = OPENAI_PRICING.get(model, {"input": 0.0, "output": 0.0})
    cost_usd = (tokens_in * pricing["input"] + tokens_out * pricing["output"]) / 1_000_000

    kw_terms = [k["keyword"] for k in data.get("keywords", [])] + data.get("companies", [])
    data["highlighted_html"] = _build_highlighted_html(content, kw_terms)
    data["analysis_model"] = model
    data["analysis_cost_usd"] = cost_usd

    return data


class NewsService:
    def __init__(self, repo: ArticleRepository):
        self.repo = repo

    async def scrape(self, date: str, owner_id: str) -> list[Article]:
        """
        date 형식: "2026-05-04"
        1~5면 기사를 수집하고 companies/tags를 자동 추출해 저장한다.
        이미 저장된 기사(url 중복)는 건너뛴다.
        """
        # date "2026-05-04" → "20260504"
        date_compact = date.replace("-", "")
        raw_articles = naver_news_scraper.scrape(_DEFAULT_OID, date_compact)

        new_articles = []
        for item in raw_articles:
            if await self.repo.find_by_url(item["url"], owner_id):
                continue
            new_articles.append({
                "date": date,
                "page_num": item["page_num"],
                "title": item["title"],
                "url": item["url"],
                "content": item["content"],
                "companies": [],
                "tags": [],
                "scraped_at": _now_iso(),
                "analysis": None,
            })

        if not new_articles:
            return await self.repo.find_by_date(date, owner_id)

        await self.repo.insert_many(new_articles, owner_id)
        return await self.repo.find_by_date(date, owner_id)

    async def list_by_date(self, date: str, owner_id: str) -> list[Article]:
        return await self.repo.find_by_date(date, owner_id)

    async def list_by_filter(
        self, owner_id: str, company: str | None, tag: str | None
    ) -> list[Article]:
        return await self.repo.find_by_filter(owner_id, company=company, tag=tag)

    async def get_filter_options(self, owner_id: str) -> dict:
        return await self.repo.find_filter_options(owner_id)

    async def get(self, id: str, owner_id: str) -> Article | None:
        return await self.repo.find_by_id(id, owner_id)

    async def analyze(self, id: str, owner_id: str, model: str = DEFAULT_MODEL) -> Article | None:
        """버튼 클릭 시 전체 AI 분석을 생성하고 저장한다. companies/tags도 함께 추출한다."""
        article = await self.repo.find_by_id(id, owner_id)
        if not article:
            return None

        data = _analyze(article.title, article.content, model)

        companies = data.pop("companies", [])
        tags = data.pop("tags", [])
        data["analyzed_at"] = _now_iso()

        await self.repo.update_meta(id, owner_id, companies, tags)
        return await self.repo.update_analysis(id, owner_id, data)
