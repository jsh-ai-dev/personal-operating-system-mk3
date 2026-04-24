# [테스트] ChatGPT 스크래퍼 파싱 함수 단위 테스트
# CDP/Chrome/네트워크 없이 실행 가능한 순수 파싱 로직만 대상으로 함
# 실제 API 응답 구조를 그대로 반영한 픽스처를 사용해 현실성 확보

import pytest
from app.adapter.scraper.chatgpt_scraper import (
    _extract_plan_raw,
    _extract_billing_date,
    _parse_result,
    _PLAN_MAP,
)


# ── 픽스처: 실제 API 응답과 동일한 구조 ──────────────────────────────────────

@pytest.fixture
def session_plus():
    """정상 로그인 + Plus 플랜 세션 응답"""
    return {
        "user": {"email": "user@example.com", "name": "홍길동"},
        "account": {"planType": "plus"},
        "accessToken": "eyJ...",
    }


@pytest.fixture
def session_pro():
    return {
        "user": {"email": "user@example.com", "name": "홍길동"},
        "account": {"planType": "pro"},
    }


@pytest.fixture
def session_no_plan():
    """planType 필드가 없는 세션 (account 자체가 없는 경우)"""
    return {
        "user": {"email": "user@example.com", "name": "홍길동"},
        "account": {},
    }


@pytest.fixture
def subscription_plus():
    """Bearer 토큰 포함 호출 시 반환되는 실제 Plus 구독 응답"""
    return {
        "accounts": {
            "default": {
                "account": {"plan_type": "plus"},
                "entitlement": {
                    "subscription_plan": "chatgptplusplan",
                    "has_active_subscription": True,
                    "renews_at": "2026-05-14T21:29:22+00:00",
                    "expires_at": "2026-05-15T03:29:22+00:00",
                    "cancels_at": None,
                },
            }
        }
    }


@pytest.fixture
def subscription_guest():
    """Bearer 토큰 없이 호출 시 반환되는 guest 응답 — plan 정보 신뢰 불가"""
    return {
        "accounts": {
            "default": {
                "account": {"plan_type": "guest"},
                "entitlement": {
                    "subscription_plan": "chatgptguestplan",
                    "has_active_subscription": False,
                    "renews_at": None,
                    "expires_at": None,
                    "cancels_at": None,
                },
            }
        }
    }


@pytest.fixture
def subscription_cancelled():
    """해지 예정 구독: cancels_at에 날짜가 있고 renews_at은 없음"""
    return {
        "accounts": {
            "default": {
                "entitlement": {
                    "subscription_plan": "chatgptplusplan",
                    "renews_at": None,
                    "expires_at": None,
                    "cancels_at": "2026-06-01T00:00:00+00:00",
                },
            }
        }
    }


# ── _extract_plan_raw ──────────────────────────────────────────────────────────

class TestExtractPlanRaw:

    def test_session_plantype_우선_사용(self, session_plus, subscription_plus):
        # session.account.planType이 있으면 subscription보다 우선해야 함
        assert _extract_plan_raw(session_plus, subscription_plus) == "plus"

    def test_session_plantype_pro(self, session_pro):
        assert _extract_plan_raw(session_pro, None) == "pro"

    def test_session_없으면_subscription_fallback(self, session_no_plan, subscription_plus):
        # session에 planType 없을 때 subscription entitlement로 대체
        result = _extract_plan_raw(session_no_plan, subscription_plus)
        assert result == "chatgptplusplan"

    def test_subscription_guest_플랜_무시(self, session_no_plan, subscription_guest):
        # guest 플랜은 신뢰할 수 없으므로 None 반환
        assert _extract_plan_raw(session_no_plan, subscription_guest) is None

    def test_session_none_subscription_none(self):
        assert _extract_plan_raw(None, None) is None

    def test_session_none_subscription_plus(self, subscription_plus):
        result = _extract_plan_raw(None, subscription_plus)
        assert result == "chatgptplusplan"


# ── _extract_billing_date ──────────────────────────────────────────────────────

class TestExtractBillingDate:

    def test_renews_at_반환(self, subscription_plus):
        # renews_at이 있으면 해당 값 반환
        assert _extract_billing_date(subscription_plus) == "2026-05-14T21:29:22+00:00"

    def test_renews_at_없으면_expires_at_사용(self):
        sub = {
            "accounts": {"default": {"entitlement": {
                "renews_at": None,
                "expires_at": "2026-05-15T03:29:22+00:00",
                "cancels_at": None,
            }}}
        }
        assert _extract_billing_date(sub) == "2026-05-15T03:29:22+00:00"

    def test_cancels_at만_있는_경우(self, subscription_cancelled):
        assert _extract_billing_date(subscription_cancelled) == "2026-06-01T00:00:00+00:00"

    def test_모든_날짜_null이면_none(self, subscription_guest):
        assert _extract_billing_date(subscription_guest) is None

    def test_subscription_none이면_none(self):
        assert _extract_billing_date(None) is None

    def test_entitlement_구조_없으면_none(self):
        assert _extract_billing_date({"accounts": {"default": {}}}) is None


# ── _parse_result ──────────────────────────────────────────────────────────────

class TestParseResult:

    def test_정상_응답_전체_필드_파싱(self, session_plus, subscription_plus):
        result = _parse_result(session_plus, None, subscription_plus)

        assert result["email"] == "user@example.com"
        assert result["user_name"] == "홍길동"
        assert result["plan_name"] == "ChatGPT Plus"          # PLAN_MAP 변환 확인
        assert result["next_billing_date"] == "2026-05-14T21:29:22+00:00"

    def test_플랜맵_변환(self, session_pro):
        result = _parse_result(session_pro, None, None)
        assert result["plan_name"] == "ChatGPT Pro"

    def test_알수없는_플랜은_원본값_사용(self):
        session = {"user": {}, "account": {"planType": "unknown_plan"}}
        result = _parse_result(session, None, None)
        # PLAN_MAP에 없는 값은 그대로 반환
        assert result["plan_name"] == "unknown_plan"

    def test_이메일_없으면_키_미포함(self):
        session = {"user": {"name": "홍길동"}, "account": {"planType": "plus"}}
        result = _parse_result(session, None, None)
        assert "email" not in result

    def test_결제일_없으면_키_미포함(self, session_plus, subscription_guest):
        result = _parse_result(session_plus, None, subscription_guest)
        assert "next_billing_date" not in result

    def test_session_none이면_빈_결과(self):
        result = _parse_result(None, None, None)
        assert "email" not in result
        assert "plan_name" not in result


# ── _PLAN_MAP 매핑 검증 ────────────────────────────────────────────────────────

class TestPlanMap:

    @pytest.mark.parametrize("raw, expected", [
        ("plus",       "ChatGPT Plus"),
        ("pro",        "ChatGPT Pro"),
        ("team",       "ChatGPT Team"),
        ("enterprise", "ChatGPT Enterprise"),
        ("free",       "Free"),
    ])
    def test_플랜맵_전체(self, raw, expected):
        assert _PLAN_MAP[raw] == expected
