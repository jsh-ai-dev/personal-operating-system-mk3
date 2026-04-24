# [테스트] 스크래퍼 API 유틸리티 함수 단위 테스트
# _parse_billing_day: 한국어 날짜 / ISO 8601(UTC) 형식 모두 처리하는 함수

import pytest
from app.api.v1.scraper import _parse_billing_day


class TestParseBillingDay:

    # ── 한국어 형식 (Claude 스크래퍼 반환값) ──────────────────────────────────

    def test_한국어_날짜_일_추출(self):
        assert _parse_billing_day("2026년 5월 22일") == 22

    def test_한국어_날짜_한자리_일(self):
        assert _parse_billing_day("2026년 1월 5일") == 5

    # ── ISO 8601 형식 (ChatGPT 스크래퍼 반환값, UTC 기준) ────────────────────

    def test_iso_utc_kst_변환_날짜_바뀌는_경우(self):
        # UTC 21:29 → KST 06:29 다음날: 14일 → 15일
        assert _parse_billing_day("2026-05-14T21:29:22+00:00") == 15

    def test_iso_utc_kst_변환_날짜_안바뀌는_경우(self):
        # UTC 10:00 → KST 19:00 같은날
        assert _parse_billing_day("2026-05-14T10:00:00+00:00") == 14

    def test_iso_이미_kst_오프셋(self):
        # +09:00 오프셋이 명시된 경우 그대로 KST로 해석
        assert _parse_billing_day("2026-05-15T06:29:22+09:00") == 15

    def test_iso_월말_날짜_넘어가는_경우(self):
        # UTC 23:00 → KST 08:00 다음날 (31일 → 1일)
        assert _parse_billing_day("2026-01-31T23:00:00+00:00") == 1

    # ── None / 잘못된 입력 ──────────────────────────────────────────────────────

    def test_none_입력(self):
        assert _parse_billing_day(None) is None

    def test_빈_문자열(self):
        assert _parse_billing_day("") is None

    def test_파싱_불가_문자열(self):
        assert _parse_billing_day("날짜없음") is None
