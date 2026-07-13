from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from enterprise_support.evaluation import (
    KnowledgeRecallCase,
    KnowledgeRecallObservation,
    grade_knowledge_recall,
    load_jsonl,
)


def run(args: argparse.Namespace) -> int:
    cases = [
        item
        for item in load_jsonl(args.dataset, KnowledgeRecallCase)
        if isinstance(item, KnowledgeRecallCase)
    ]
    observations = [
        item
        for item in load_jsonl(args.results, KnowledgeRecallObservation)
        if isinstance(item, KnowledgeRecallObservation)
    ]
    case_ids = {item.id for item in cases}
    unknown_ids = sorted({item.case_id for item in observations}.difference(case_ids))
    if unknown_ids:
        raise ValueError(f"Unknown knowledge recall case(s): {', '.join(unknown_ids)}")

    summary, grades = grade_knowledge_recall(
        cases,
        observations,
        k=args.k,
        threshold=args.threshold,
    )
    report = {
        "dataset": str(args.dataset),
        "results": str(args.results),
        "k": args.k,
        "summary": asdict(summary),
        "grades": [grade.model_dump(mode="json") for grade in grades],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if summary.passed_threshold else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Grade knowledge retrieval Recall@K")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--threshold", type=float, default=0.85)
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
