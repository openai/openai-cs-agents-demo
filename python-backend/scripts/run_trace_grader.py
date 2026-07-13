from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from enterprise_support.evaluation import (
    EvaluationCase,
    GradeResult,
    ObservedResult,
    RuleTraceGrader,
    ZhipuSemanticGrader,
    load_jsonl,
    summarize,
)


async def run(args: argparse.Namespace) -> int:
    cases = {
        item.id: item
        for item in load_jsonl(args.dataset, EvaluationCase)
        if isinstance(item, EvaluationCase)
    }
    observations = [
        item for item in load_jsonl(args.results, ObservedResult) if isinstance(item, ObservedResult)
    ]
    rule_grader = RuleTraceGrader()
    semantic_grader = ZhipuSemanticGrader() if args.semantic else None
    grades: list[GradeResult] = []
    for observed in observations:
        case = cases.get(observed.case_id)
        if case is None:
            raise ValueError(f"Unknown evaluation case: {observed.case_id}")
        grade = rule_grader.grade(case, observed)
        if semantic_grader is not None:
            score, reason = await semantic_grader.grade(case, observed)
            grade = grade.model_copy(update={"semantic_score": score, "semantic_reason": reason})
        grades.append(grade)

    observed_ids = {item.case_id for item in observations}
    if not args.allow_partial:
        for case_id, case in cases.items():
            if case_id in observed_ids:
                continue
            grades.append(
                GradeResult(
                    case_id=case_id,
                    passed=False,
                    critical_failure=case.critical,
                    score=0,
                    checks={"result_present": False},
                    failures=["missing_result"],
                )
            )

    summary = summarize(grades)
    report = {
        "dataset": str(args.dataset),
        "results": str(args.results),
        "summary": asdict(summary),
        "grades": [grade.model_dump(mode="json") for grade in grades],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 1 if summary.critical_failures or summary.failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Grade redacted enterprise-agent trace results")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--semantic", action="store_true")
    parser.add_argument("--allow-partial", action="store_true")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
