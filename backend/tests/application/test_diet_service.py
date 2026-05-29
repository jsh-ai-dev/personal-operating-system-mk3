from app.application.diet_service import normalize_ai_result


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
