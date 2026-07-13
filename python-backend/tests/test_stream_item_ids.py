from datetime import datetime

from chatkit.types import (
    AssistantMessageContent,
    AssistantMessageContentPartTextDelta,
    AssistantMessageItem,
    ThreadItemAddedEvent,
    ThreadItemDoneEvent,
    ThreadItemUpdatedEvent,
)

from server import merge_text_delta_events, normalize_synthetic_item_id


def test_synthetic_chat_completion_ids_are_unique_per_message() -> None:
    fake_item = AssistantMessageItem(
        id="__fake_id__",
        thread_id="thread-1",
        created_at=datetime.now(),
        content=[],
    )
    generated_ids = iter(["message-1", "message-2"])

    first_added, active_id = normalize_synthetic_item_id(
        ThreadItemAddedEvent(item=fake_item), None, lambda: next(generated_ids)
    )
    first_delta, active_id = normalize_synthetic_item_id(
        ThreadItemUpdatedEvent(
            item_id="__fake_id__",
            update=AssistantMessageContentPartTextDelta(
                content_index=0,
                delta="hello",
            ),
        ),
        active_id,
        lambda: next(generated_ids),
    )
    first_done, active_id = normalize_synthetic_item_id(
        ThreadItemDoneEvent(
            item=fake_item.model_copy(
                update={"content": [AssistantMessageContent(text="hello")]}
            )
        ),
        active_id,
        lambda: next(generated_ids),
    )
    second_added, active_id = normalize_synthetic_item_id(
        ThreadItemAddedEvent(item=fake_item),
        active_id,
        lambda: next(generated_ids),
    )

    assert first_added.item.id == "message-1"
    assert first_delta.item_id == "message-1"
    assert first_done.item.id == "message-1"
    assert second_added.item.id == "message-2"
    assert active_id == "message-2"


def test_adjacent_text_deltas_are_merged() -> None:
    first = ThreadItemUpdatedEvent(
        item_id="message-1",
        update=AssistantMessageContentPartTextDelta(content_index=0, delta="hello "),
    )
    second = ThreadItemUpdatedEvent(
        item_id="message-1",
        update=AssistantMessageContentPartTextDelta(content_index=0, delta="world"),
    )

    merged = merge_text_delta_events(first, second)

    assert merged is not None
    assert merged.item_id == "message-1"
    assert merged.update.delta == "hello world"


def test_text_deltas_for_different_items_are_not_merged() -> None:
    first = ThreadItemUpdatedEvent(
        item_id="message-1",
        update=AssistantMessageContentPartTextDelta(content_index=0, delta="hello"),
    )
    second = ThreadItemUpdatedEvent(
        item_id="message-2",
        update=AssistantMessageContentPartTextDelta(content_index=0, delta="world"),
    )

    assert merge_text_delta_events(first, second) is None
