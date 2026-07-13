from enterprise_support.agents import ALL_AGENTS, triage_agent


def test_agent_team_has_expected_specialists() -> None:
    names = {agent.name for agent in ALL_AGENTS}

    assert names == {
        "Triage Agent",
        "Product Knowledge Agent",
        "Solution Architect Agent",
        "Technical Support Agent",
        "Account and Billing Agent",
        "Security and Compliance Agent",
    }


def test_triage_can_reach_all_specialists() -> None:
    handoff_names = {
        getattr(item, "agent_name", getattr(item, "name", ""))
        for item in triage_agent.handoffs
    }

    assert len(handoff_names) == 5

