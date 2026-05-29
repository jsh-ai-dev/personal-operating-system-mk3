from dataclasses import dataclass, field


MEAL_KEYS = ("breakfast", "lunch", "dinner", "snack")


@dataclass
class Nutrients:
    calories: int = 0
    protein_g: int = 0
    carbs_g: int = 0
    fat_g: int = 0
    sugar_g: int = 0


@dataclass
class MealSummary:
    label: str
    items: list[str] = field(default_factory=list)
    nutrients: Nutrients = field(default_factory=Nutrients)


@dataclass
class DietMessage:
    role: str
    content: str
    created_at: str
    model: str | None = None
    tokens_input: int | None = None
    tokens_output: int | None = None
    cost_usd: float | None = None


@dataclass
class DietDay:
    date_key: str
    meals: dict[str, MealSummary]
    total: Nutrients
    tip: str
    messages: list[DietMessage]
    sources: list[str] = field(default_factory=list)
    updated_at: str | None = None


@dataclass
class DietProfile:
    current_weight_kg: float | None = None
    target_weight_kg: float | None = None
    daily_calories: int | None = None
    protein_g: int | None = None
    carbs_g: int | None = None
    fat_g: int | None = None
    updated_at: str | None = None
