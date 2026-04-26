from dataclasses import dataclass, field


@dataclass
class Message:
    id: str
    conversation_id: str
    role: str                    # "user" | "assistant"
    content: str
    model: str | None
    tokens_input: int | None     # 요청 전체 토큰 (assistant만)
    tokens_output: int | None    # 응답 토큰 (assistant만)
    cost_usd: float | None
    created_at: str
    qdrant_id: str | None = None


@dataclass
class Conversation:
    id: str
    provider: str                # "openai" | "anthropic" | "google"
    model: str
    title: str
    created_at: str
    updated_at: str
    message_count: int
    total_tokens_input: int
    total_tokens_output: int
    total_cost_usd: float
    summary: str | None = None
    tags: list = field(default_factory=list)
    qdrant_id: str | None = None
