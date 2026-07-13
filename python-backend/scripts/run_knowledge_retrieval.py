from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from enterprise_support.evaluation import (
    KnowledgeRecallCase,
    KnowledgeRecallObservation,
    load_jsonl,
)
from enterprise_support.identity import RequestIdentity
from persistent_store import PersistentStore


def run(args: argparse.Namespace) -> int:
    cases = [
        item
        for item in load_jsonl(args.dataset, KnowledgeRecallCase)
        if isinstance(item, KnowledgeRecallCase)
    ]
    identity = RequestIdentity(
        tenant_id=args.tenant_id,
        user_id=args.user_id,
        roles=frozenset(args.roles.split(",")),
    )
    store = PersistentStore(args.database_path)
    observations: list[KnowledgeRecallObservation] = []
    try:
        for case in cases:
            matches = store.search_knowledge(
                identity,
                case.query,
                category=case.category,
                limit=args.k,
            )
            observations.append(
                KnowledgeRecallObservation(
                    case_id=case.id,
                    retrieved_document_ids=[item["document_id"] for item in matches],
                )
            )
    finally:
        store.close()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "\n".join(item.model_dump_json() for item in observations) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"cases": len(observations), "output": str(output)}, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local knowledge retrieval for Recall@K grading")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--database-path")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--tenant-id", default="tenant_acme_cn")
    parser.add_argument("--user-id", default="local-admin")
    parser.add_argument(
        "--roles",
        default="tenant_admin,knowledge_editor,knowledge_reviewer,support_agent",
    )
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
