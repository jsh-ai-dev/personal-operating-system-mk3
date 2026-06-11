import asyncio
from types import SimpleNamespace

from app.application.search_service import RAG_ANSWER_MODEL, SearchService
from app.domain.conversation import Conversation


class FakeConversationRepo:
    def __init__(self, conversations: list[Conversation]):
        self.conversations = {conv.id: conv for conv in conversations}
        self.requested_owner_id = None

    async def find_conversations_by_ids(self, conversation_ids: list[str], owner_id: str):
        self.requested_owner_id = owner_id
        return {
            conversation_id: self.conversations[conversation_id]
            for conversation_id in conversation_ids
            if conversation_id in self.conversations
        }


class FakeVectorRepo:
    def __init__(self, points: list[SimpleNamespace]):
        self.points = points
        self.search_calls: list[dict] = []
        self.ensure_collection_called = False

    async def ensure_collection(self):
        self.ensure_collection_called = True

    async def search(self, vector, owner_id: str, limit: int):
        self.search_calls.append({"vector": vector, "owner_id": owner_id, "limit": limit})
        return self.points


class FakeEmbeddings:
    async def create(self, model: str, input: str):
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])],
            usage=SimpleNamespace(total_tokens=50),
        )


class FakeChatCompletions:
    def __init__(self):
        self.calls: list[dict] = []

    async def create(self, model: str, messages: list[dict]):
        self.calls.append({"model": model, "messages": messages})
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="요약 근거 기준 답변입니다."))],
            usage=SimpleNamespace(prompt_tokens=1200, completion_tokens=220),
        )


class FakeOpenAI:
    def __init__(self):
        self.embeddings = FakeEmbeddings()
        self.chat_completions = FakeChatCompletions()
        self.chat = SimpleNamespace(completions=self.chat_completions)


def _conversation(
    conversation_id: str,
    *,
    summary: str | None = "요약된 대화 내용",
    is_hidden: bool = False,
    title: str | None = None,
) -> Conversation:
    return Conversation(
        id=conversation_id,
        provider="openai",
        model="gpt-5-mini",
        title=title or f"대화 {conversation_id}",
        created_at="2026-06-01T10:30:00+00:00",
        updated_at="2026-06-01T10:35:00+00:00",
        message_count=4,
        total_tokens_input=100,
        total_tokens_output=40,
        total_cost_usd=0.001,
        summary=summary,
        is_hidden=is_hidden,
    )


def _point(conversation_id: str, score: float = 0.8421) -> SimpleNamespace:
    return SimpleNamespace(
        payload={
            "conversation_id": conversation_id,
            "title": f"대화 {conversation_id}",
            "model": "gpt-5-mini",
            "created_at": "2026-06-01T10:30:00+00:00",
        },
        score=score,
    )


def _service(conversations: list[Conversation], points: list[SimpleNamespace]):
    openai = FakeOpenAI()
    repo = FakeConversationRepo(conversations)
    vector_repo = FakeVectorRepo(points)
    return SearchService(repo, vector_repo, openai), repo, vector_repo, openai


def test_answer_returns_grounded_response_from_summarized_candidates():
    svc, repo, vector_repo, openai = _service(
        [
            _conversation("conv-1", summary="Kafka consumer는 처리 성공 후 offset을 commit해야 한다."),
            _conversation("conv-2", summary="재시도와 DLQ를 분리하면 중복 처리 위험을 줄일 수 있다."),
        ],
        [_point("conv-1"), _point("conv-2", 0.8012)],
    )

    result = asyncio.run(svc.answer("Kafka offset commit", "user-1"))

    assert result["status"] == "answered"
    assert result["answer"] == "요약 근거 기준 답변입니다."
    assert result["model"] == RAG_ANSWER_MODEL
    assert [source["conversation_id"] for source in result["sources"]] == ["conv-1", "conv-2"]
    assert repo.requested_owner_id == "user-1"
    assert vector_repo.search_calls[0]["owner_id"] == "user-1"
    assert openai.chat_completions.calls[0]["model"] == RAG_ANSWER_MODEL


def test_answer_returns_insufficient_grounding_without_summaries():
    svc, _, _, openai = _service(
        [_conversation("conv-1", summary=None)],
        [_point("conv-1")],
    )

    result = asyncio.run(svc.answer("Kafka offset commit", "user-1"))

    assert result["status"] == "insufficient_grounding"
    assert result["answer"] == ""
    assert result["sources"] == []
    assert result["tokens_input"] == 0
    assert result["tokens_output"] == 0
    assert openai.chat_completions.calls == []


def test_answer_sources_include_required_source_fields():
    svc, _, _, _ = _service(
        [
            _conversation(
                "conv-1",
                summary="Kafka consumer offset commit 전략을 정리했다. 처리 성공 후 commit하고 실패 시 재시도한다.",
                title="Kafka consumer offset handling",
            )
        ],
        [_point("conv-1")],
    )

    result = asyncio.run(svc.answer("Kafka offset commit", "user-1"))
    source = result["sources"][0]

    assert source == {
        "conversation_id": "conv-1",
        "title": "Kafka consumer offset handling",
        "summary_excerpt": "Kafka consumer offset commit 전략을 정리했다. 처리 성공 후 commit하고 실패 시 재시도한다.",
        "created_at": "2026-06-01T10:30:00+00:00",
        "provider": "openai",
        "model": "gpt-5-mini",
        "score": 0.8421,
        "href": "/mk3/chat/conv-1",
    }


def test_answer_excludes_hidden_conversations_and_caps_sources_to_five():
    conversations = [_conversation("hidden", is_hidden=True)] + [
        _conversation(f"conv-{idx}") for idx in range(1, 7)
    ]
    points = [_point("hidden", 0.99)] + [_point(f"conv-{idx}", 0.9) for idx in range(1, 7)]
    svc, _, _, _ = _service(conversations, points)

    result = asyncio.run(svc.answer("Kafka offset commit", "user-1"))

    source_ids = [source["conversation_id"] for source in result["sources"]]
    assert "hidden" not in source_ids
    assert source_ids == ["conv-1", "conv-2", "conv-3", "conv-4", "conv-5"]


def test_answer_returns_token_and_cost_metadata_from_openai_usage():
    svc, _, _, _ = _service(
        [_conversation("conv-1")],
        [_point("conv-1")],
    )

    result = asyncio.run(svc.answer("Kafka offset commit", "user-1"))

    assert result["tokens_input"] == 1200
    assert result["tokens_output"] == 220
    assert result["cost_usd"] == 0.00074
    assert result["search_cost_usd"] == 0.000001
