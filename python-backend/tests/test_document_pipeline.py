from enterprise_support.identity import RequestIdentity
from enterprise_support.object_storage import LocalObjectStorage, document_object_key
from persistent_store import PersistentStore


def _identity() -> RequestIdentity:
    return RequestIdentity(
        tenant_id="tenant-docs",
        user_id="editor",
        roles=frozenset({"tenant_admin", "knowledge_editor", "knowledge_reviewer"}),
    )


def test_local_object_storage_rejects_path_traversal(tmp_path) -> None:
    storage = LocalObjectStorage(tmp_path)
    storage.put("tenant/document.txt", b"content")

    assert storage.get("tenant/document.txt") == b"content"

    try:
        storage.put("../outside.txt", b"bad")
    except ValueError:
        pass
    else:
        raise AssertionError("Path traversal must be rejected")


def test_document_task_moves_content_to_review_pending(tmp_path) -> None:
    store = PersistentStore(":memory:")
    identity = _identity()
    storage = LocalObjectStorage(tmp_path)
    key = document_object_key(identity.tenant_id, "guide.md")
    storage.put(key, "# 产品指南\n\n仅供审核。".encode())
    document = store.create_document(
        identity,
        title="产品指南",
        content="Document processing is pending.",
        source="guide.md",
    )
    queued = store.enqueue_document_processing(
        identity,
        document_id=document["id"],
        object_key=key,
        filename="guide.md",
        content_type="text/markdown",
        content_hash="hash",
    )

    task = store.claim_document_task("worker-test")
    store.complete_document_task(task, content=storage.get(key).decode())
    processed = store.get_document(identity, queued["id"])

    assert queued["status"] == "processing"
    assert processed["status"] == "review_pending"
    assert "仅供审核" in processed["content"]
    assert store.search_knowledge(identity, "产品指南") == []
    store.close()
