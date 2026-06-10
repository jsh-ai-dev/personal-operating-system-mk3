import asyncio
from datetime import date

import pytest

from app.adapter.mongodb.diet_repository import _meal_content_key, _merge_sources
from app.application.diet_service import DEFAULT_RECENT_DAYS, DEFAULT_RECENT_LIMIT, DietService, normalize_ai_result
from app.domain.diet import DietDay, DietMessage, MealSummary, Nutrients


class FakeDietRepo:
    def __init__(self):
        self.copy_result = None
        self.copy_calls = []
        self.clear_result = None
        self.clear_calls = []
        self.recent_calls = []

    async def copy_meal(
        self,
        owner_id: str,
        source_date_key: str,
        source_meal_key: str,
        target_date_key: str,
        target_meal_key: str,
    ):
        self.copy_calls.append(
            {
                "owner_id": owner_id,
                "source_date_key": source_date_key,
                "source_meal_key": source_meal_key,
                "target_date_key": target_date_key,
                "target_meal_key": target_meal_key,
            }
        )
        return self.copy_result

    async def clear_meal(
        self,
        owner_id: str,
        target_date_key: str,
        target_meal_key: str,
    ):
        self.clear_calls.append(
            {
                "owner_id": owner_id,
                "target_date_key": target_date_key,
                "target_meal_key": target_meal_key,
            }
        )
        return self.clear_result

    async def list_recent_meal_candidates(
        self,
        owner_id: str,
        start_date_key: str,
        end_date_key: str,
        limit: int,
    ):
        self.recent_calls.append(
            {
                "owner_id": owner_id,
                "start_date_key": start_date_key,
                "end_date_key": end_date_key,
                "limit": limit,
            }
        )
        return [
            {
                "date_key": end_date_key,
                "meal_key": "dinner",
                "label": "저녁",
                "items": ["닭가슴살"],
                "nutrients": {
                    "calories": 220,
                    "protein_g": 35,
                    "carbs_g": 3,
                    "fat_g": 6,
                    "sugar_g": 1,
                },
            }
        ]


def test_normalize_ai_result_fills_missing_meals_and_clamps_numbers():
    meals, tip = normalize_ai_result(
        {
            "meals": {
                "lunch": {
                    "items": ["김밥", " 라떼 "],
                    "calories": "720.4",
                    "protein_g": 22,
                    "carbs_g": -1,
                    "fat_g": True,
                    "sugar_g": 14.2,
                }
            },
            "tip": "단백질을 먼저 챙기세요.",
        }
    )

    assert meals["breakfast"].nutrients.calories == 0
    assert meals["lunch"].items == ["김밥", "라떼"]
    assert meals["lunch"].nutrients.calories == 720
    assert meals["lunch"].nutrients.protein_g == 22
    assert meals["lunch"].nutrients.carbs_g == 0
    assert meals["lunch"].nutrients.fat_g == 0
    assert meals["lunch"].nutrients.sugar_g == 14
    assert tip == "단백질을 먼저 챙기세요."


def test_merge_sources_keeps_order_and_removes_duplicates():
    assert _merge_sources(
        ["https://example.com/bagel", "https://example.com/jam"],
        ["https://example.com/bagel", "https://example.com/chicken"],
    ) == [
        "https://example.com/bagel",
        "https://example.com/jam",
        "https://example.com/chicken",
    ]


def test_meal_content_key_ignores_label_for_copy_duplicates():
    nutrients = Nutrients(calories=520, protein_g=28, carbs_g=62, fat_g=18, sugar_g=9)
    lunch = MealSummary(label="lunch", items=["bagel", "jam"], nutrients=nutrients)
    dinner = MealSummary(label="dinner", items=["bagel", "jam"], nutrients=nutrients)
    changed = MealSummary(
        label="dinner",
        items=["bagel", "jam"],
        nutrients=Nutrients(calories=521, protein_g=28, carbs_g=62, fat_g=18, sugar_g=9),
    )

    assert _meal_content_key(lunch) == _meal_content_key(dinner)
    assert _meal_content_key(lunch) != _meal_content_key(changed)


def test_copy_meal_returns_target_day_without_ai_call():
    repo = FakeDietRepo()
    repo.copy_result = DietDay(
        date_key="2026-06-09",
        meals={
            "breakfast": MealSummary(label="아침"),
            "lunch": MealSummary(
                label="점심",
                items=["양념치킨", "맥주"],
                nutrients=Nutrients(calories=2200, protein_g=110, carbs_g=140, fat_g=120, sugar_g=45),
            ),
            "dinner": MealSummary(label="저녁"),
            "snack": MealSummary(label="간식"),
        },
        total=Nutrients(calories=2200, protein_g=110, carbs_g=140, fat_g=120, sugar_g=45),
        tip="기존 팁 유지",
        messages=[DietMessage(role="user", content="기존 기록", created_at="2026-06-09T00:00:00+00:00")],
        sources=["https://example.com/original"],
    )
    svc = DietService(repo, openai_client=None)

    result = asyncio.run(
        svc.copy_meal(
            owner_id="user-1",
            source_date_key="2026-06-08",
            source_meal_key="dinner",
            target_date_key="2026-06-09",
            target_meal_key="lunch",
        )
    )

    assert result.meals["lunch"].items == ["양념치킨", "맥주"]
    assert result.tip == "기존 팁 유지"
    assert result.sources == ["https://example.com/original"]
    assert result.messages[0].content == "기존 기록"
    assert repo.copy_calls == [
        {
            "owner_id": "user-1",
            "source_date_key": "2026-06-08",
            "source_meal_key": "dinner",
            "target_date_key": "2026-06-09",
            "target_meal_key": "lunch",
        }
    ]


def test_copy_meal_rejects_invalid_meal_key():
    svc = DietService(FakeDietRepo(), openai_client=None)

    with pytest.raises(ValueError, match="지원하지 않는 식사 구분"):
        asyncio.run(
            svc.copy_meal(
                owner_id="user-1",
                source_date_key="2026-06-08",
                source_meal_key="midnight",
                target_date_key="2026-06-09",
                target_meal_key="lunch",
            )
        )


def test_copy_meal_rejects_empty_or_missing_source():
    svc = DietService(FakeDietRepo(), openai_client=None)

    with pytest.raises(ValueError, match="복사할 원본 식사"):
        asyncio.run(
            svc.copy_meal(
                owner_id="user-1",
                source_date_key="2026-06-08",
                source_meal_key="dinner",
                target_date_key="2026-06-09",
                target_meal_key="lunch",
            )
        )


def test_clear_meal_returns_target_day_without_ai_call():
    repo = FakeDietRepo()
    repo.clear_result = DietDay(
        date_key="2026-06-10",
        meals={
            "breakfast": MealSummary(label="breakfast"),
            "lunch": MealSummary(label="lunch"),
            "dinner": MealSummary(
                label="dinner",
                items=["bagel"],
                nutrients=Nutrients(calories=430, protein_g=28, carbs_g=50, fat_g=12, sugar_g=6),
            ),
            "snack": MealSummary(label="snack"),
        },
        total=Nutrients(calories=430, protein_g=28, carbs_g=50, fat_g=12, sugar_g=6),
        tip="existing tip",
        messages=[DietMessage(role="user", content="existing message", created_at="2026-06-10T00:00:00+00:00")],
        sources=["https://example.com/original"],
    )
    svc = DietService(repo, openai_client=None)

    result = asyncio.run(
        svc.clear_meal(
            owner_id="user-1",
            target_date_key="2026-06-10",
            target_meal_key="lunch",
        )
    )

    assert result.meals["lunch"].items == []
    assert result.meals["lunch"].nutrients.calories == 0
    assert result.tip == "existing tip"
    assert result.sources == ["https://example.com/original"]
    assert repo.clear_calls == [
        {
            "owner_id": "user-1",
            "target_date_key": "2026-06-10",
            "target_meal_key": "lunch",
        }
    ]


def test_clear_meal_rejects_invalid_meal_key():
    svc = DietService(FakeDietRepo(), openai_client=None)

    with pytest.raises(ValueError, match="지원하지 않는 식사 구분"):
        asyncio.run(
            svc.clear_meal(
                owner_id="user-1",
                target_date_key="2026-06-10",
                target_meal_key="midnight",
            )
        )


def test_list_recent_meal_candidates_bounds_window_and_limit():
    repo = FakeDietRepo()
    svc = DietService(repo, openai_client=None)

    result = asyncio.run(svc.list_recent_meal_candidates("user-1", days=999, limit=999))

    call = repo.recent_calls[0]
    start = date.fromisoformat(call["start_date_key"])
    end = date.fromisoformat(call["end_date_key"])
    assert (end - start).days == DEFAULT_RECENT_DAYS - 1
    assert call["limit"] == DEFAULT_RECENT_LIMIT
    assert result[0]["meal_key"] == "dinner"
