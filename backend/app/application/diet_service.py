import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from openai import AsyncOpenAI

from app.adapter.mongodb.diet_repository import DietRepository
from app.application.chat_service import OPENAI_PRICING
from app.domain.diet import DietDay, DietProfile, MEAL_KEYS, MealSummary, Nutrients


DEFAULT_DIET_MODEL = "gpt-5-nano"
DEFAULT_RECENT_DAYS = 14
DEFAULT_RECENT_LIMIT = 20
KST = timezone(timedelta(hours=9))

_SYSTEM_PROMPT = """당신은 자연어 식사 기록을 날짜별 영양 요약으로 변환하는 식단 기록 도우미입니다.

목표:
- 사용자가 자연어로 적은 식사 기록을 대략적인 칼로리, 탄수화물, 단백질, 지방, 당으로 정리합니다.
- 사용자가 직접 음식명을 검색하거나 영양성분표를 찾지 않아도 되도록, 공개 정보와 일반적인 섭취량 추정을 조합합니다.
- 사용자의 새 입력과 기존 날짜 기록을 함께 보고, 해당 날짜의 최종 상태를 다시 계산합니다.
- 브랜드명/제품명/프랜차이즈 메뉴가 포함된 음식은 먼저 웹 검색으로 영양성분표, 제품 상세, 판매 페이지, 제조사/프랜차이즈 공식 정보를 확인합니다. 검색 없이 일반 추정으로 넘어가지 않습니다.
- 제품명 검색 결과를 찾지 못했거나 영양 정보가 없는 경우에만 비슷한 제품의 일반적인 값으로 추정하고, source_urls는 실제 참고한 URL만 넣습니다.
- 집밥, 일반 식당 음식, 양이 애매한 음식은 웹 검색에 시간을 쓰지 말고 문장에 나온 자연스러운 섭취 상황 기준으로 추정합니다.

분류 규칙:
- 출력 식사 구분은 breakfast, lunch, dinner, snack 네 가지뿐입니다.
- 아점, 브런치, 늦은 아침은 기본적으로 lunch로 합칩니다.
- 단, 같은 날짜에 사용자가 별도의 점심을 먹었다고 말하면 기존 아점/브런치/늦은 아침은 breakfast로 옮기고 새 점심을 lunch로 둡니다.
- 간식이 여러 번이면 snack 하나로 합산합니다.
- 사용자가 이전 입력을 정정하면 기존 기록을 수정해서 최종 상태에 반영합니다.
- 양을 입력하지 않은 경우는 권장 섭취량, 다이어트 기준량, 영양성분표의 1회 제공량이 아닌, 한국 성인 남성이 보통 그 표현으로 먹는 실제 섭취량을 기준으로 추정합니다.
- 영양성분표의 1회 제공량은 계산 단위일 뿐 실제 섭취량이 아닙니다. 실제 섭취량을 먼저 정한 뒤, 필요하면 1회 제공량 수치를 여러 배로 환산합니다.
- 예를 들어 "양념치킨에 맥주 한 캔"에서의 양념치킨은 당연히 1~2조각이 아닌 1마리가 기준입니다. 일반적인 성인 남성이 술안주로 치킨 1~2조각만 먹는 경우는 없습니다.
- 기존 채팅 내역과 저장된 식단을 보고 같은 음식이 중복 계산되지 않게 합니다.

출력 규칙:
- 반드시 JSON 객체만 출력합니다. 마크다운 코드블록, 설명 문장, 주석은 금지합니다.
- 모든 영양 수치는 0 이상의 정수입니다.
- tip은 다이어트에 도움되는 짧은 한국어 팁 한 문장입니다.
- tip에서 물을 많이 마시라는 조언, 수분 섭취 조언, 물 관련 문장은 금지합니다.
- items에는 사용자가 먹은 음식명을 짧게 넣습니다. 없으면 빈 배열입니다.
- 웹 검색을 참고한 경우 source_urls에 사용한 URL을 넣습니다. 없으면 빈 배열입니다.

JSON 형식:
{
  "meals": {
    "breakfast": {"items": ["음식"], "calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "sugar_g": 0},
    "lunch": {"items": [], "calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "sugar_g": 0},
    "dinner": {"items": [], "calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "sugar_g": 0},
    "snack": {"items": [], "calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "sugar_g": 0}
  },
  "source_urls": ["https://example.com/nutrition"],
  "tip": "짧은 팁"
}"""

_DIET_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "meals": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                key: {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "items": {"type": "array", "items": {"type": "string"}},
                        "calories": {"type": "integer"},
                        "protein_g": {"type": "integer"},
                        "carbs_g": {"type": "integer"},
                        "fat_g": {"type": "integer"},
                        "sugar_g": {"type": "integer"},
                    },
                    "required": ["items", "calories", "protein_g", "carbs_g", "fat_g", "sugar_g"],
                }
                for key in MEAL_KEYS
            },
            "required": list(MEAL_KEYS),
        },
        "source_urls": {"type": "array", "items": {"type": "string"}},
        "tip": {"type": "string"},
    },
    "required": ["meals", "source_urls", "tip"],
}


def _calc_cost(model: str, tokens_input: int, tokens_output: int) -> float:
    pricing = OPENAI_PRICING.get(model, {"input": 0.0, "output": 0.0})
    return (tokens_input * pricing["input"] + tokens_output * pricing["output"]) / 1_000_000


def _as_int(value) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return max(0, int(round(value)))
    if isinstance(value, str):
        try:
            return max(0, int(round(float(value.strip()))))
        except ValueError:
            return 0
    return 0


def normalize_ai_result(payload: dict) -> tuple[dict[str, MealSummary], str]:
    labels = {
        "breakfast": "아침",
        "lunch": "점심",
        "dinner": "저녁",
        "snack": "간식",
    }
    raw_meals = payload.get("meals") if isinstance(payload.get("meals"), dict) else {}
    meals: dict[str, MealSummary] = {}
    for key in MEAL_KEYS:
        raw = raw_meals.get(key) if isinstance(raw_meals.get(key), dict) else {}
        items = raw.get("items") if isinstance(raw.get("items"), list) else []
        meals[key] = MealSummary(
            label=labels[key],
            items=[str(item).strip() for item in items if str(item).strip()],
            nutrients=Nutrients(
                calories=_as_int(raw.get("calories")),
                protein_g=_as_int(raw.get("protein_g")),
                carbs_g=_as_int(raw.get("carbs_g")),
                fat_g=_as_int(raw.get("fat_g")),
                sugar_g=_as_int(raw.get("sugar_g")),
            ),
        )
    tip = str(payload.get("tip") or "").strip()
    return meals, tip


def normalize_sources(payload: dict) -> list[str]:
    raw_sources = payload.get("source_urls") if isinstance(payload.get("source_urls"), list) else []
    sources: list[str] = []
    for source in raw_sources:
        url = str(source).strip()
        if url.startswith(("http://", "https://")) and url not in sources:
            sources.append(url)
    return sources[:8]


def validate_meal_key(meal_key: str) -> str:
    if meal_key not in MEAL_KEYS:
        raise ValueError(f"지원하지 않는 식사 구분: {meal_key}")
    return meal_key


def _day_for_prompt(day: DietDay) -> dict:
    return {
        "meals": {
            key: {
                "items": meal.items,
                "calories": meal.nutrients.calories,
                "protein_g": meal.nutrients.protein_g,
                "carbs_g": meal.nutrients.carbs_g,
                "fat_g": meal.nutrients.fat_g,
                "sugar_g": meal.nutrients.sugar_g,
            }
            for key, meal in day.meals.items()
        },
        "tip": day.tip,
        "sources": day.sources,
    }


def _profile_for_prompt(profile: DietProfile) -> dict:
    return {
        "current_weight_kg": profile.current_weight_kg,
        "target_weight_kg": profile.target_weight_kg,
        "daily_calories": profile.daily_calories,
        "protein_g": profile.protein_g,
        "carbs_g": profile.carbs_g,
        "fat_g": profile.fat_g,
    }


class DietService:
    def __init__(self, repo: DietRepository, openai_client: AsyncOpenAI):
        self.repo = repo
        self.openai = openai_client

    async def get_profile(self, owner_id: str) -> DietProfile:
        return await self.repo.get_profile(owner_id)

    async def upsert_profile(self, owner_id: str, data: dict) -> DietProfile:
        return await self.repo.upsert_profile(owner_id, data)

    async def get_day(self, owner_id: str, date_key: str) -> DietDay:
        return await self.repo.get_day(owner_id, date_key)

    async def delete_day(self, owner_id: str, date_key: str) -> bool:
        return await self.repo.delete_day(owner_id, date_key)

    async def list_recent_meal_candidates(
        self,
        owner_id: str,
        days: int = DEFAULT_RECENT_DAYS,
        limit: int = DEFAULT_RECENT_LIMIT,
    ) -> list[dict]:
        bounded_days = min(max(days, 1), DEFAULT_RECENT_DAYS)
        bounded_limit = min(max(limit, 1), DEFAULT_RECENT_LIMIT)
        today = datetime.now(KST).date()
        start = today - timedelta(days=bounded_days - 1)
        return await self.repo.list_recent_meal_candidates(
            owner_id=owner_id,
            start_date_key=start.isoformat(),
            end_date_key=today.isoformat(),
            limit=bounded_limit,
        )

    async def copy_meal(
        self,
        owner_id: str,
        source_date_key: str,
        source_meal_key: str,
        target_date_key: str,
        target_meal_key: str,
    ) -> DietDay:
        validate_meal_key(source_meal_key)
        validate_meal_key(target_meal_key)
        copied = await self.repo.copy_meal(
            owner_id=owner_id,
            source_date_key=source_date_key,
            source_meal_key=source_meal_key,
            target_date_key=target_date_key,
            target_meal_key=target_meal_key,
        )
        if copied is None:
            raise ValueError("복사할 원본 식사가 비어 있거나 없습니다.")
        return copied

    async def clear_meal(
        self,
        owner_id: str,
        target_date_key: str,
        target_meal_key: str,
    ) -> DietDay:
        validate_meal_key(target_meal_key)
        return await self.repo.clear_meal(
            owner_id=owner_id,
            target_date_key=target_date_key,
            target_meal_key=target_meal_key,
        )

    async def analyze_day(
        self,
        owner_id: str,
        date_key: str,
        message: str,
        model: str = DEFAULT_DIET_MODEL,
    ) -> dict:
        profile = await self.repo.get_profile(owner_id)
        day = await self.repo.get_day(owner_id, date_key)
        history = [
            {"role": m.role, "content": m.content}
            for m in day.messages[-12:]
            if m.role in {"user", "assistant"}
        ]

        user_prompt = json.dumps(
            {
                "date": date_key,
                "profile": _profile_for_prompt(profile),
                "current_saved_day": _day_for_prompt(day),
                "recent_chat_history": history,
                "new_user_input": message,
            },
            ensure_ascii=False,
        )

        response = await self.openai.responses.create(
            model=model,
            input=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            tools=[
                {
                    "type": "web_search",
                    "search_context_size": "low",
                    "user_location": {
                        "type": "approximate",
                        "country": "KR",
                        "timezone": "Asia/Seoul",
                    },
                }
            ],
            tool_choice="auto",
            text={
                "format": {
                    "type": "json_schema",
                    "name": "diet_day_analysis",
                    "schema": _DIET_JSON_SCHEMA,
                    "strict": True,
                },
                "verbosity": "low",
            },
        )
        raw = response.output_text or "{}"
        parsed = json.loads(raw)
        meals, tip = normalize_ai_result(parsed)
        sources = normalize_sources(parsed)
        usage = response.usage
        tokens_input = getattr(usage, "input_tokens", 0) if usage else 0
        tokens_output = getattr(usage, "output_tokens", 0) if usage else 0
        cost_usd = _calc_cost(model, tokens_input, tokens_output)
        saved = await self.repo.save_analysis(
            owner_id=owner_id,
            date_key=date_key,
            meals=meals,
            tip=tip,
            user_message=message,
            assistant_content=json.dumps(parsed, ensure_ascii=False),
            sources=sources,
            model=model,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost_usd=cost_usd,
        )
        return {
            "day": asdict(saved),
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "cost_usd": cost_usd,
        }

