"""Unit tests for CoachAgent.converse() — multi-turn, with stubbed LLM
and tools. Checkpointer integration is tested separately."""

from banko_ai.coach.agent import CoachAgent


def _is_planner(messages) -> bool:
    last = next((m for m in messages
                 if m.__class__.__name__ == "SystemMessage"), None)
    content = getattr(last, "content", "") if last else ""
    return "PLANNER" in content


def test_converse_returns_text_for_single_turn():
    def llm(messages, **kwargs):
        if _is_planner(messages):
            return ('{"steps": [{"tool": "get_recent_transactions", '
                    '"args": {"category": "dining", "limit": 3, "days": 14}}]}')
        return "Last 14 days: $312.50 across 5 dining transactions."

    agent = CoachAgent(
        database_url="postgresql://stub",
        llm_invoker=llm,
        tool_overrides={
            "get_recent_transactions": lambda **kw: [
                {"description": "Olive Garden", "amount": 64.20,
                 "category": "dining", "expense_date": "2026-05-18"},
                {"description": "Chipotle", "amount": 12.80,
                 "category": "dining", "expense_date": "2026-05-15"},
            ],
        },
        provider_name="stub",
    )
    reply = agent.converse(
        user_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
        message="show me last 2 weeks of dining",
        history=[],
    )
    assert "dining" in reply["message"].lower()
    assert reply["provider_used"] == "stub"
    assert len(reply["tool_trace"]) == 1
    assert reply["tool_trace"][0]["tool"] == "get_recent_transactions"


def test_converse_respects_history_in_prompt():
    captured = []
    def llm(messages, **kwargs):
        captured.append(messages)
        if _is_planner(messages):
            return '{"steps": []}'
        return "ok"

    agent = CoachAgent(
        database_url="postgresql://stub",
        llm_invoker=llm,
        tool_overrides={},
        provider_name="stub",
    )
    agent.converse(
        user_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
        message="and what about groceries?",
        history=[
            {"role": "user", "content": "show me dining"},
            {"role": "assistant", "content": "$312 last 2 weeks"},
        ],
    )
    planner_call = captured[0]
    human = next(m for m in planner_call
                 if m.__class__.__name__ == "HumanMessage")
    assert "show me dining" in human.content
    assert "and what about groceries?" in human.content


def test_converse_can_call_insights_tools():
    """Conversational planner must also have access to insights tools,
    so 'why am I overspending on dining?' can pull velocity + top
    merchants in one turn."""
    def llm(messages, **kwargs):
        if _is_planner(messages):
            return ('{"steps": ['
                    '{"tool": "get_spending_velocity", '
                    '"args": {"category": "dining", "monthly_budget": 400}},'
                    '{"tool": "get_top_merchants", '
                    '"args": {"days": 14, "k": 3, "category": "dining"}}'
                    ']}')
        return "Pace $412 vs $400 budget; Chipotle drove $145."

    agent = CoachAgent(
        database_url="postgresql://stub",
        llm_invoker=llm,
        tool_overrides={
            "get_spending_velocity": lambda **kw: {
                "spent_so_far": 328.0, "projected_eom": 412.0,
                "on_track": False,
            },
            "get_top_merchants": lambda **kw: [
                {"merchant": "Chipotle", "total": 145.0,
                 "transaction_count": 5},
            ],
        },
        provider_name="stub",
    )
    reply = agent.converse(
        user_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
        message="why am I overspending on dining?",
        history=[],
    )
    tool_names = [t["tool"] for t in reply["tool_trace"]]
    assert "get_spending_velocity" in tool_names
    assert "get_top_merchants" in tool_names


def test_converse_context_passed_to_planner():
    """When context (e.g. nudge_id) is supplied, planner sees it."""
    captured = []
    def llm(messages, **kwargs):
        captured.append(messages)
        if _is_planner(messages):
            return '{"steps": []}'
        return "ok"

    agent = CoachAgent(
        database_url="postgresql://stub",
        llm_invoker=llm,
        tool_overrides={},
        provider_name="stub",
    )
    agent.converse(
        user_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
        message="why did I get this nudge?",
        history=[],
        context={"nudge_id": "n-123"},
    )
    human = next(m for m in captured[0]
                 if m.__class__.__name__ == "HumanMessage")
    assert "n-123" in human.content
