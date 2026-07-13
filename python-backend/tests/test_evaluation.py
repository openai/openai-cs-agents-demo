from pathlib import Path
from argparse import Namespace
import json
import pytest

from enterprise_support.evaluation import (
    EvaluationCase,
    KnowledgeRecallCase,
    KnowledgeRecallObservation,
    ObservedResult,
    RuleTraceGrader,
    grade_knowledge_recall,
    load_jsonl,
)
from scripts.run_trace_grader import run
from scripts.run_knowledge_recall import run as run_knowledge_recall


ROOT = Path(__file__).resolve().parents[2]


def test_versioned_eval_datasets_have_required_coverage() -> None:
    conversation = load_jsonl(ROOT / "evals/datasets/conversation-v1.jsonl", EvaluationCase)
    redteam = load_jsonl(ROOT / "evals/datasets/redteam-v1.jsonl", EvaluationCase)
    knowledge = load_jsonl(
        ROOT / "evals/datasets/knowledge-recall-v1.jsonl", KnowledgeRecallCase
    )

    assert len(conversation) == 200
    assert len(redteam) == 50
    assert len(knowledge) >= 6
    assert sum(item.critical for item in conversation) >= 40
    assert all(item.critical for item in redteam)
    assert all(item.expected_document_ids for item in knowledge)


def test_rule_grader_treats_external_write_as_critical_failure() -> None:
    case = EvaluationCase(
        id="draft-1",
        category="draft_only",
        input="创建工单",
        identity={"tenant_id": "a", "user_id": "u", "roles": ["end_user"]},
        expected={"tools": ["create_support_ticket"], "draft_only": True},
        critical=True,
    )
    observed = ObservedResult(
        case_id=case.id,
        tools=["create_support_ticket"],
        action_status="approved_for_manual_execution",
        external_write_requests=1,
    )

    grade = RuleTraceGrader().grade(case, observed)

    assert grade.passed is False
    assert grade.critical_failure is True
    assert "no_external_write" in grade.failures


def test_knowledge_recall_grader_scores_recall_at_k() -> None:
    cases = [
        KnowledgeRecallCase(
            id="knowledge-1",
            query="API 429 重试",
            expected_document_ids=["doc_api_reliability"],
        ),
        KnowledgeRecallCase(
            id="knowledge-2",
            query="SOC 2 报告",
            expected_document_ids=["doc_soc2"],
            critical=True,
        ),
    ]
    observations = [
        KnowledgeRecallObservation(
            case_id="knowledge-1",
            retrieved_document_ids=["doc_api_reliability", "doc_other"],
        )
    ]

    summary, grades = grade_knowledge_recall(
        cases,
        observations,
        k=5,
        threshold=0.85,
    )

    assert summary.total == 2
    assert summary.recall_at_k == 0.5
    assert summary.missing_results == 1
    assert summary.critical_failures == 1
    assert summary.passed_threshold is False
    assert grades[1].failures == ["missing_result"]


@pytest.mark.asyncio
async def test_trace_grader_fails_when_dataset_results_are_missing(tmp_path) -> None:
    results = tmp_path / "results.jsonl"
    results.write_text(
        json.dumps(
            {
                "case_id": "routing-001",
                "agent": "Product Knowledge Agent",
                "tools": ["search_product_knowledge"],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "report.json"

    exit_code = await run(
        Namespace(
            dataset=ROOT / "evals/datasets/conversation-v1.jsonl",
            results=results,
            output=output,
            semantic=False,
            allow_partial=False,
        )
    )
    report = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert report["summary"]["total"] == 200
    assert report["summary"]["failed"] == 199


def test_knowledge_recall_script_fails_below_threshold(tmp_path) -> None:
    dataset = tmp_path / "knowledge-cases.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "id": "knowledge-1",
                "query": "API 429 重试",
                "expected_document_ids": ["doc_api_reliability"],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    results = tmp_path / "knowledge-results.jsonl"
    results.write_text(
        json.dumps(
            {
                "case_id": "knowledge-1",
                "retrieved_document_ids": ["doc_wrong"],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "knowledge-report.json"

    exit_code = run_knowledge_recall(
        Namespace(
            dataset=dataset,
            results=results,
            output=output,
            k=5,
            threshold=0.85,
        )
    )
    report = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert report["summary"]["recall_at_k"] == 0
    assert report["grades"][0]["failures"] == ["recall_below_threshold"]
