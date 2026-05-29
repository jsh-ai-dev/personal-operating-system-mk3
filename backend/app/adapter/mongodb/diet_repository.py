from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.domain.diet import DietDay, DietMessage, DietProfile, MEAL_KEYS, MealSummary, Nutrients


def _iso(value):
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc).isoformat() if value.tzinfo is None else value.isoformat()
    return value


def _to_int(value) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return max(0, int(round(value)))
    return 0


def _nutrients_from_doc(doc: dict | None) -> Nutrients:
    doc = doc or {}
    return Nutrients(
        calories=_to_int(doc.get("calories")),
        protein_g=_to_int(doc.get("protein_g")),
        carbs_g=_to_int(doc.get("carbs_g")),
        fat_g=_to_int(doc.get("fat_g")),
        sugar_g=_to_int(doc.get("sugar_g")),
    )


def _nutrients_to_doc(nutrients: Nutrients) -> dict:
    return {
        "calories": nutrients.calories,
        "protein_g": nutrients.protein_g,
        "carbs_g": nutrients.carbs_g,
        "fat_g": nutrients.fat_g,
        "sugar_g": nutrients.sugar_g,
    }


def _empty_meals() -> dict[str, MealSummary]:
    labels = {
        "breakfast": "아침",
        "lunch": "점심",
        "dinner": "저녁",
        "snack": "간식",
    }
    return {key: MealSummary(label=labels[key]) for key in MEAL_KEYS}


def _calc_total(meals: dict[str, MealSummary]) -> Nutrients:
    return Nutrients(
        calories=sum(meal.nutrients.calories for meal in meals.values()),
        protein_g=sum(meal.nutrients.protein_g for meal in meals.values()),
        carbs_g=sum(meal.nutrients.carbs_g for meal in meals.values()),
        fat_g=sum(meal.nutrients.fat_g for meal in meals.values()),
        sugar_g=sum(meal.nutrients.sugar_g for meal in meals.values()),
    )


class DietRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.profiles = db["diet_profiles"]
        self.days = db["diet_days"]

    def _to_profile(self, doc: dict | None) -> DietProfile:
        if not doc:
            return DietProfile()
        return DietProfile(
            current_weight_kg=doc.get("current_weight_kg"),
            target_weight_kg=doc.get("target_weight_kg"),
            daily_calories=doc.get("daily_calories"),
            protein_g=doc.get("protein_g"),
            carbs_g=doc.get("carbs_g"),
            fat_g=doc.get("fat_g"),
            updated_at=_iso(doc.get("updated_at")),
        )

    def _to_day(self, doc: dict | None, date_key: str) -> DietDay:
        if not doc:
            meals = _empty_meals()
            return DietDay(date_key=date_key, meals=meals, total=_calc_total(meals), tip="", messages=[])

        meals = _empty_meals()
        raw_meals = doc.get("meals") if isinstance(doc.get("meals"), dict) else {}
        for key in MEAL_KEYS:
            raw_meal = raw_meals.get(key) if isinstance(raw_meals.get(key), dict) else {}
            items = raw_meal.get("items") if isinstance(raw_meal.get("items"), list) else []
            meals[key] = MealSummary(
                label=raw_meal.get("label") or meals[key].label,
                items=[str(item) for item in items if str(item).strip()],
                nutrients=_nutrients_from_doc(raw_meal.get("nutrients")),
            )

        raw_messages = doc.get("messages") if isinstance(doc.get("messages"), list) else []
        messages = [
            DietMessage(
                role=str(message.get("role", "")),
                content=str(message.get("content", "")),
                created_at=_iso(message.get("created_at")),
                model=message.get("model"),
                tokens_input=message.get("tokens_input"),
                tokens_output=message.get("tokens_output"),
                cost_usd=message.get("cost_usd"),
            )
            for message in raw_messages
            if isinstance(message, dict)
        ]

        return DietDay(
            date_key=date_key,
            meals=meals,
            total=_calc_total(meals),
            tip=str(doc.get("tip") or ""),
            messages=messages,
            sources=[str(source) for source in doc.get("sources", []) if str(source).strip()],
            updated_at=_iso(doc.get("updated_at")),
        )

    async def get_profile(self, owner_id: str) -> DietProfile:
        doc = await self.profiles.find_one({"owner_id": owner_id})
        return self._to_profile(doc)

    async def upsert_profile(self, owner_id: str, data: dict) -> DietProfile:
        now = datetime.now(timezone.utc)
        payload = {
            "current_weight_kg": data.get("current_weight_kg"),
            "target_weight_kg": data.get("target_weight_kg"),
            "daily_calories": data.get("daily_calories"),
            "protein_g": data.get("protein_g"),
            "carbs_g": data.get("carbs_g"),
            "fat_g": data.get("fat_g"),
            "updated_at": now,
        }
        await self.profiles.update_one(
            {"owner_id": owner_id},
            {"$set": payload, "$setOnInsert": {"owner_id": owner_id}},
            upsert=True,
        )
        return await self.get_profile(owner_id)

    async def get_day(self, owner_id: str, date_key: str) -> DietDay:
        doc = await self.days.find_one({"owner_id": owner_id, "date_key": date_key})
        return self._to_day(doc, date_key)

    async def save_analysis(
        self,
        owner_id: str,
        date_key: str,
        meals: dict[str, MealSummary],
        tip: str,
        user_message: str,
        assistant_content: str,
        sources: list[str],
        model: str,
        tokens_input: int,
        tokens_output: int,
        cost_usd: float,
    ) -> DietDay:
        now = datetime.now(timezone.utc)
        meal_docs = {
            key: {
                "label": meal.label,
                "items": meal.items,
                "nutrients": _nutrients_to_doc(meal.nutrients),
            }
            for key, meal in meals.items()
        }
        messages = [
            {"role": "user", "content": user_message, "created_at": now},
            {
                "role": "assistant",
                "content": assistant_content,
                "created_at": now,
                "model": model,
                "tokens_input": tokens_input,
                "tokens_output": tokens_output,
                "cost_usd": cost_usd,
            },
        ]
        await self.days.update_one(
            {"owner_id": owner_id, "date_key": date_key},
            {
                "$set": {
                    "meals": meal_docs,
                    "tip": tip,
                    "sources": sources,
                    "updated_at": now,
                },
                "$push": {"messages": {"$each": messages}},
                "$setOnInsert": {"owner_id": owner_id, "date_key": date_key},
            },
            upsert=True,
        )
        return await self.get_day(owner_id, date_key)
