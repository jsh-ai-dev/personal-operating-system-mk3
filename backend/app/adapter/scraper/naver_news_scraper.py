# [스크래퍼] 네이버 뉴스 신문지면(listType=paper)에서 기사 목록과 본문을 수집
# requests + BeautifulSoup 사용 — 네이버 뉴스는 SSR이라 Playwright 불필요

import re
import time

import requests
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# 수집할 면 범위 (1~5면)
_PAGE_RANGE = range(1, 6)


def _get(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=_HEADERS, timeout=10)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def fetch_article_links(oid: str, date: str) -> list[dict]:
    """
    신문지면 목록 페이지에서 1~5면 기사 링크를 수집한다.
    date 형식: "20260504"
    반환: [{"page_num": 1, "url": "https://...", "title": "..."}]
    """
    url = (
        f"https://news.naver.com/main/list.naver"
        f"?mode=LPOD&mid=sec&oid={oid}&listType=paper&date={date}"
    )
    soup = _get(url)
    results = []

    for h4 in soup.select("h4.paper_h4"):
        label = h4.get_text(strip=True)
        # "1면", "2면" 형태에서 숫자 추출
        m = re.match(r"^(\d+)면$", label)
        if not m:
            continue
        page_num = int(m.group(1))
        if page_num not in _PAGE_RANGE:
            continue

        # h4 다음 형제 ul 안의 기사 링크 수집
        ul = h4.find_next_sibling("ul")
        if not ul:
            continue

        for a in ul.select("dt a[href]"):
            href = a.get("href", "")
            if "n.news.naver.com" not in href:
                continue
            title = a.get_text(strip=True) or a.get("alt", "").strip()
            if not title:
                continue
            results.append({"page_num": page_num, "url": href, "title": title})

    return results


def fetch_article_content(url: str) -> str:
    """
    기사 상세 페이지에서 본문 텍스트를 추출한다.
    기자명·이메일은 제거한다.
    """
    soup = _get(url)

    article_tag = soup.find("article", id="dic_area")
    if not article_tag:
        return ""

    # 이미지 캡션 태그 제거
    for tag in article_tag.select("em.img_desc, .nbd_im_w, span.end_photo_org"):
        tag.decompose()

    # <br> → 줄바꿈, <p> → 단락 구분으로 변환 후 텍스트 추출
    for br in article_tag.find_all("br"):
        br.replace_with("\n")
    for p in article_tag.find_all("p"):
        p.insert_before("\n\n")

    text = article_tag.get_text(separator="")
    # 3개 이상 연속 줄바꿈은 2개로 정리
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 각 줄 앞뒤 공백 제거
    text = "\n".join(line.strip() for line in text.splitlines())
    text = text.strip()

    # "홍길동 기자 id@domain.com" 패턴 제거
    text = re.sub(r"\s*\S+\s*기자(\s+\S+@\S+)?\s*$", "", text).strip()

    return text


def scrape(oid: str, date: str) -> list[dict]:
    """
    date 형식: "20260504"
    반환: [{"page_num", "url", "title", "content"}]
    """
    links = fetch_article_links(oid, date)
    articles = []

    for item in links:
        content = fetch_article_content(item["url"])
        articles.append({**item, "content": content})
        # 연속 요청 간 간격 — 서버 부하 방지
        time.sleep(0.3)

    return articles
