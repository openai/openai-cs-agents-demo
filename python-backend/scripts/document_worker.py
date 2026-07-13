from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from uuid import uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from enterprise_support.documents import extract_document_text
from enterprise_support.object_storage import MalwareScanner, build_object_storage
from persistent_store import PersistentStore


def process_one(store: PersistentStore, worker_id: str) -> bool:
    task = store.claim_document_task(worker_id)
    if task is None:
        return False
    storage = build_object_storage()
    try:
        data = storage.get(task["object_key"])
        MalwareScanner().scan(data)
        content = extract_document_text(task["filename"], data)
        if not content:
            raise ValueError("No readable text was extracted")
        store.complete_document_task(task, content=content)
    except Exception as exc:
        store.fail_document_task(task, str(exc))
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Process queued enterprise knowledge documents")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()
    worker_id = f"document-worker-{uuid4().hex[:8]}"
    store = PersistentStore()
    try:
        while True:
            processed = process_one(store, worker_id)
            if args.once:
                return 0
            if not processed:
                time.sleep(max(args.poll_seconds, 0.2))
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
