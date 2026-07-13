from enterprise_support.context import EnterpriseAgentContext, public_context


def test_public_context_hides_internal_tenant_data() -> None:
    context = EnterpriseAgentContext(
        company_name="Acme Intelligence",
        tenant_id="tenant-secret",
        verified_identity=True,
        source_refs=["KB-001"],
        internal_notes=["internal"],
    )

    result = public_context(context)

    assert result["company_name"] == "Acme Intelligence"
    assert "tenant_id" not in result
    assert "verified_identity" not in result
    assert "source_refs" not in result
    assert "internal_notes" not in result


def test_public_context_omits_empty_compliance_topics() -> None:
    assert "compliance_topics" not in public_context(EnterpriseAgentContext())

