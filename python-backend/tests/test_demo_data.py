from enterprise_support.context import EnterpriseAgentContext
from enterprise_support.demo_data import hydrate_account, resolve_demo_account, search_knowledge


def test_resolve_demo_account_selects_nova() -> None:
    key, account = resolve_demo_account("account ACC-2048 at Nova Labs")

    assert key == "startup"
    assert account["company_name"] == "Nova Labs"


def test_hydrate_account_marks_identity_verified() -> None:
    context = EnterpriseAgentContext()

    hydrate_account(context, "Acme")

    assert context.account_id == "ACC-10086"
    assert context.tenant_id == "tenant_acme_cn"
    assert context.verified_identity is True


def test_search_knowledge_returns_grounded_source() -> None:
    results = search_knowledge("429 timeout retry")

    assert results[0]["id"] == "KB-API-003"
    assert results[0]["content"]


def test_search_knowledge_returns_empty_for_unknown_topic() -> None:
    assert search_knowledge("DeepSeek 售后服务政策") == []
