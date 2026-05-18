from app.adapter.scraper.chatgpt_scraper import (
    _current_cycle_start_from_next_billing as chatgpt_cycle_start,
)
from app.adapter.scraper.claude_scraper import (
    _current_cycle_start_from_next_billing as claude_cycle_start,
    _extract_subscribed_at,
)
from app.adapter.scraper.codex_scraper import (
    _current_cycle_start_from_next_billing as codex_cycle_start,
)


def test_chatgpt_cycle_start_uses_previous_month_in_kst():
    assert chatgpt_cycle_start("2026-06-14T21:29:22+00:00") == "2026-05-15"


def test_codex_cycle_start_uses_previous_month_in_kst():
    assert codex_cycle_start("2026-06-14T21:29:22+00:00") == "2026-05-15"


def test_cycle_start_clamps_month_end():
    assert chatgpt_cycle_start("2026-03-31T10:00:00+00:00") == "2026-02-28"


def test_claude_subscribed_at_uses_latest_billing_date():
    text = "2026년 5월 15일 결제\n2026년 4월 15일 결제"
    assert _extract_subscribed_at(text) == "2026-05-15"


def test_claude_subscribed_at_ignores_future_next_billing_date():
    text = "Next billing June 15, 2026\nInvoice May 15, 2026\nInvoice April 15, 2026"
    assert _extract_subscribed_at(text) == "2026-05-15"


def test_claude_cycle_start_falls_back_from_english_next_billing():
    assert claude_cycle_start("June 15, 2026") == "2026-05-15"
