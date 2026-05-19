# [서비스] 뉴스 스크래핑, 기업명·태그 자동 추출, 기사 AI 분석을 담당하는 비즈니스 로직
# 스크랩 시: API 호출 없음 (텍스트 수집만)
# 분석 버튼 클릭 시: 선택한 GPT 모델로 메타·키워드·요약·질문 추출, 하이라이팅은 로컬 처리

import asyncio
import json
import logging
import random
import re
from datetime import datetime, timedelta, timezone

from openai import OpenAI
import requests

from app.adapter.mongodb.article_repository import ArticleRepository
from app.adapter.mongodb.news_scrape_job_repository import NewsScrapeJobRepository
from app.adapter.scraper import naver_news_scraper
from app.application.chat_service import OPENAI_PRICING
from app.core.config import settings
from app.domain.article import Article

DEFAULT_MODEL = "gpt-5-mini"

# 전자신문 oid (기본값)
_DEFAULT_OID = "030"
_ARTICLE_DELAY_RANGE_SECONDS = (5.0, 10.0)
_REQUEST_MAX_ATTEMPTS = 3
_RATE_LIMIT_COOLDOWN_MINUTES = 30

logger = logging.getLogger(__name__)

# 숫자·날짜·퍼센트 포함 문장 판별
_NUM_PATTERN = re.compile(r"[\d]+[,.]?[\d]*\s*(%|년|월|일|억|조|만|개|명|건|배|배율|GW|MW|nm|인치)?")


def _client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _minutes_from_now_iso(minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


class NewsScrapeRateLimited(RuntimeError):
    pass


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


# 하이라이팅 기능 비활성화 — 숫자 문장(빨강)·키워드 문장(파랑) 색상 표시가 실용적이지 않아 제거
# 재활성화 시: _analyze()에서 주석 해제 후 highlighted_html 필드에 결과 저장
# def _build_highlighted_html(content: str, keywords: list[str]) -> str:
#     kw_pattern = re.compile(
#         "|".join(re.escape(k) for k in keywords if k), re.IGNORECASE,
#     ) if keywords else None
#     lines = content.splitlines()
#     html_lines = []
#     for line in lines:
#         stripped = line.strip()
#         if not stripped:
#             html_lines.append("")
#             continue
#         escaped = stripped.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
#         if _NUM_PATTERN.search(stripped):
#             html_lines.append(f'<span class="num">{escaped}</span>')
#         elif kw_pattern and kw_pattern.search(stripped):
#             html_lines.append(f'<span class="kw">{escaped}</span>')
#         else:
#             html_lines.append(escaped)
#     return "<br>".join(html_lines)


def _analyze(title: str, content: str, model: str) -> dict:
    """
    선택한 GPT 모델로 companies, tags, keywords, motivation_summary, questions를 추출한다.
    highlighted_html은 응답에서 제외하고 로컬에서 생성해 토큰 비용을 절감한다.
    분석에 사용한 모델명과 비용(USD)도 함께 반환한다.
    """
    prompt = f"""다음 기사를 분석해서 JSON만 반환해줘. 개발자 면접 준비를 위해 기업을 조사하는 용도야.

제목: {title}
내용: {content}

{{
  "companies": ["기사의 주제가 되는 핵심 기업 1~2개 (언급만 된 기업 제외, 없으면 빈 배열 [])"],
  "tags": ["기사의 핵심 주제 한 단어 태그 1~2개"],
  "summary": "기사 핵심 내용 요약 (4~6문장)",
  "keywords": [{{"keyword": "개발자에게 중요한 기술 키워드 3개", "explanation": "간단한 설명"}}],
  "motivation_summary": "지원 동기에 활용할 기업 제품·기술·사업 특징 요약 (2~4문장)",
  "questions": [{{"question": "기사만으로 알기 어려운 내용을 현직자에게 묻는 질문 2개", "expected_answer": "예상 답변 1~2문장"}}]
}}

"""

    raw, tokens_in, tokens_out = _chat(prompt, 5000, model)
    data = json.loads(raw)

    pricing = OPENAI_PRICING.get(model, {"input": 0.0, "output": 0.0})
    cost_usd = (tokens_in * pricing["input"] + tokens_out * pricing["output"]) / 1_000_000

    # 하이라이팅 비활성화 — _build_highlighted_html() 참고
    # kw_terms = [k["keyword"] for k in data.get("keywords", [])] + data.get("companies", [])
    # data["highlighted_html"] = _build_highlighted_html(content, kw_terms)
    data["analysis_model"] = model
    data["analysis_cost_usd"] = cost_usd

    return data


async def _fetch_article_content_with_retries(url: str) -> str:
    for attempt in range(1, _REQUEST_MAX_ATTEMPTS + 1):
        try:
            return await asyncio.to_thread(naver_news_scraper.fetch_article_content, url)
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else 0
            if status_code == 429:
                raise NewsScrapeRateLimited(f"Naver returned 429 Too Many Requests for {url}") from e
            if attempt >= _REQUEST_MAX_ATTEMPTS or status_code < 500:
                raise
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout,
            requests.exceptions.Timeout,
        ):
            if attempt >= _REQUEST_MAX_ATTEMPTS:
                raise

        delay = min(60.0, (2 ** attempt) + random.uniform(0.5, 2.5))
        await asyncio.sleep(delay)

    return ""


class NewsService:
    def __init__(
        self,
        repo: ArticleRepository,
        job_repo: NewsScrapeJobRepository | None = None,
    ):
        self.repo = repo
        self.job_repo = job_repo

    async def scrape(self, date: str, owner_id: str) -> tuple[list[Article], int]:
        """
        date 형식: "2026-05-04"
        1~5면 기사를 수집하고 companies/tags를 자동 추출해 저장한다.
        이미 저장된 기사(url 중복)는 건너뛴다.
        반환: (전체 기사 목록, 새로 추가된 건수)
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

        if new_articles:
            await self.repo.insert_many(new_articles, owner_id)

        return await self.repo.find_by_date(date, owner_id), len(new_articles)

    async def start_scrape_job(self, date: str, owner_id: str) -> tuple[dict, bool]:
        if not self.job_repo:
            raise RuntimeError("News scrape job repository is not configured.")

        active = await self.job_repo.find_active(owner_id, date)
        if active:
            return active, False
        return await self.job_repo.create(owner_id, date), True

    async def get_scrape_job(self, job_id: str, owner_id: str) -> dict | None:
        if not self.job_repo:
            raise RuntimeError("News scrape job repository is not configured.")
        return await self.job_repo.find_by_id(job_id, owner_id)

    async def get_latest_scrape_job(self, owner_id: str, date: str | None = None) -> dict | None:
        if not self.job_repo:
            raise RuntimeError("News scrape job repository is not configured.")
        return await self.job_repo.find_latest(owner_id, date)

    async def run_scrape_job(self, job_id: str, date: str, owner_id: str) -> None:
        if not self.job_repo:
            raise RuntimeError("News scrape job repository is not configured.")

        inserted = 0
        skipped_existing = 0
        failed = 0
        processed = 0

        try:
            await self.job_repo.update(
                job_id,
                status="running",
                message="Fetching article list.",
                started_at=_now_iso(),
            )
            date_compact = date.replace("-", "")
            try:
                links = await asyncio.to_thread(
                    naver_news_scraper.fetch_article_links,
                    _DEFAULT_OID,
                    date_compact,
                )
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response is not None else 0
                if status_code == 429:
                    cooldown_until = _minutes_from_now_iso(_RATE_LIMIT_COOLDOWN_MINUTES)
                    message = "Naver returned 429 Too Many Requests while fetching the article list."
                    await self.job_repo.append_error(job_id, message)
                    await self.job_repo.update(
                        job_id,
                        status="limited",
                        cooldown_until=cooldown_until,
                        finished_at=_now_iso(),
                        message=f"{message} Cooldown until {cooldown_until}.",
                    )
                    return
                raise
            await self.job_repo.update(
                job_id,
                total=len(links),
                message=f"Found {len(links)} article links.",
            )

            for item in links:
                current_url = item["url"]
                await self.job_repo.update(
                    job_id,
                    current_url=current_url,
                    message=f"Processing {processed + 1}/{len(links)}.",
                )

                if await self.repo.find_by_url(current_url, owner_id):
                    skipped_existing += 1
                    processed += 1
                    await self.job_repo.update(
                        job_id,
                        processed=processed,
                        skipped_existing=skipped_existing,
                    )
                    continue

                try:
                    content = await _fetch_article_content_with_retries(current_url)
                except NewsScrapeRateLimited as e:
                    cooldown_until = _minutes_from_now_iso(_RATE_LIMIT_COOLDOWN_MINUTES)
                    await self.job_repo.append_error(job_id, str(e))
                    await self.job_repo.update(
                        job_id,
                        status="limited",
                        processed=processed,
                        inserted=inserted,
                        skipped_existing=skipped_existing,
                        failed=failed,
                        current_url=current_url,
                        cooldown_until=cooldown_until,
                        finished_at=_now_iso(),
                        message=(
                            "Naver returned 429 Too Many Requests. "
                            f"Cooldown until {cooldown_until}."
                        ),
                    )
                    return
                except requests.exceptions.RequestException as e:
                    failed += 1
                    await self.job_repo.append_error(job_id, f"{type(e).__name__}: {current_url}")
                    logger.warning("News article scrape failed: %s", current_url, exc_info=True)
                else:
                    await self.repo.insert_many(
                        [{
                            "date": date,
                            "page_num": item["page_num"],
                            "title": item["title"],
                            "url": current_url,
                            "content": content,
                            "companies": [],
                            "tags": [],
                            "scraped_at": _now_iso(),
                            "analysis": None,
                        }],
                        owner_id,
                    )
                    inserted += 1

                processed += 1
                await self.job_repo.update(
                    job_id,
                    processed=processed,
                    inserted=inserted,
                    skipped_existing=skipped_existing,
                    failed=failed,
                )
                await asyncio.sleep(random.uniform(*_ARTICLE_DELAY_RANGE_SECONDS))

            await self.job_repo.update(
                job_id,
                status="completed",
                processed=processed,
                inserted=inserted,
                skipped_existing=skipped_existing,
                failed=failed,
                current_url="",
                finished_at=_now_iso(),
                message="Scrape job completed.",
            )
        except Exception as e:
            await self.job_repo.append_error(job_id, f"{type(e).__name__}: {e}")
            await self.job_repo.update(
                job_id,
                status="failed",
                processed=processed,
                inserted=inserted,
                skipped_existing=skipped_existing,
                failed=failed,
                finished_at=_now_iso(),
                message="Scrape job failed.",
            )
            logger.exception("News scrape job failed: %s", job_id)

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
