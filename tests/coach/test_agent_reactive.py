"""Unit tests for CoachAgent.react() with a stubbed LLM. No live DB
required — tool calls are stubbed via tool_overrides."""

from banko_ai.coach.agent import CoachAgent
from banko_ai.coach.signals import Signal, SignalType


def _make_signal(sig_type: SignalType = SignalType.BUDGET_THRESHOLD) -> Signal:
    return Signal(
        signal_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        user_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        signal_type=sig_type,
        severity="warn",
        payload={"category": "dining", "pct_used": 0.82},
        idempotency_key="agent-test-1",
    )


def _is_planner(messages) -> bool:
    last_system = next(
        (m for m in messages if m.__class__.__name__ == "SystemMessage"),
        None,
    )
    content = getattr(last_system, "content", "") if last_system else ""
    return "PLANNER" in content


def _stub_llm_invoker(messages, **kwargs):
    if _is_planner(messages):
        return '{"steps": [{"tool": "get_user_budget", '\
               '"args": {"category": "dining"}}]}'
    return "You are at 82% of your dining budget. 9 days left in the month."


def test_react_returns_nudge_with_message_and_tool_trace():
    agent = CoachAgent(
        database_url="postgresql://stub",
        llm_invoker=_stub_llm_invoker,
        tool_overrides={
            "get_user_budget": lambda **kw: {"category": "dining",
                                              "monthly_budget": 400.0,
                                              "source": "default"}
        },
        provider_name="stub",
    )
    nudge = agent.react(_make_signal())

    assert "dining" in nudge["message"].lower()
    assert nudge["provider_used"] == "stub"
    assert len(nudge["tool_trace"]) >= 1
    assert nudge["tool_trace"][0]["tool"] == "get_user_budget"


def test_react_handles_planner_returning_invalid_json():
    """If planner returns garbage, agent falls back to a no-tools plan and
    still produces a nudge from the signal alone."""
    def bad_planner(messages, **kw):
        if _is_planner(messages):
            return "not json at all"
        return "Fallback nudge text."

    agent = CoachAgent(
        database_url="postgresql://stub",
        llm_invoker=bad_planner,
        tool_overrides={},
        provider_name="stub",
    )
    nudge = agent.react(_make_signal())
    assert nudge["message"]
    assert nudge["provider_used"] == "stub"


def test_react_caps_executor_at_max_steps():
    """Planner asks for 10 steps; executor hard-caps at max_steps=2."""
    big_plan = '{"steps": [' + ",".join(
        ['{"tool": "get_user_budget", "args": {"category": "dining"}}'] * 10
    ) + ']}'

    call_count = {"n": 0}
    def counting_budget(**kw):
        call_count["n"] += 1
        return {"category": "dining", "monthly_budget": 400.0,
                "source": "default"}

    def llm(messages, **kwargs):
        if _is_planner(messages):
            return big_plan
        return "synth"

    agent = CoachAgent(
        database_url="postgresql://stub",
        llm_invoker=llm,
        tool_overrides={"get_user_budget": counting_budget},
        provider_name="stub",
        max_steps=2,
    )
    agent.react(_make_signal())
    assert call_count["n"] == 2


def test_react_uses_insights_tools_when_planner_requests_them():
    """The new insights tools (velocity, top_merchants) must be
    invokable by the agent so nudges can cite concrete numbers."""
    plan = (
        '{"steps": ['
        '{"tool": "get_spending_velocity", '
        '"args": {"category": "dining", "monthly_budget": 400.0}},'
        '{"tool": "get_top_merchants", '
        '"args": {"days": 14, "k": 3, "category": "dining"}}'
        ']}'
    )

    def llm(messages, **kwargs):
        if _is_planner(messages):
            return plan
        return "At 82% of dining with $312 projected EOM; Chipotle driving."

    agent = CoachAgent(
        database_url="postgresql://stub",
        llm_invoker=llm,
        tool_overrides={
            "get_spending_velocity": lambda **kw: {
                "category": "dining", "spent_so_far": 328.0,
                "projected_eom": 412.0, "pct_of_budget": 0.82,
                "on_track": False,
            },
            "get_top_merchants": lambda **kw: [
                {"merchant": "Chipotle", "total": 145.0,
                 "transaction_count": 5},
            ],
        },
        provider_name="stub",
    )
    nudge = agent.react(_make_signal())
    tool_names = [t["tool"] for t in nudge["tool_trace"]]
    assert "get_spending_velocity" in tool_names
    assert "get_top_merchants" in tool_names
    # Confirm the executor actually called the override with sane args
    velocity_entry = next(t for t in nudge["tool_trace"]
                          if t["tool"] == "get_spending_velocity")
    assert velocity_entry["result"]["projected_eom"] == 412.0


def test_react_handles_tool_failure_gracefully():
    """A failing tool produces an error trace but the synthesizer still
    runs and the user still gets a nudge."""
    def boom(**kw):
        raise RuntimeError("simulated tool failure")

    def llm(messages, **kwargs):
        if _is_planner(messages):
            return '{"steps": [{"tool": "get_user_budget", "args": {}}]}'
        return "Coach nudge text"

    agent = CoachAgent(
        database_url="postgresql://stub",
        llm_invoker=llm,
        tool_overrides={"get_user_budget": boom},
        provider_name="stub",
    )
    nudge = agent.react(_make_signal())
    assert nudge["message"] == "Coach nudge text"
    assert nudge["tool_trace"][0]["error"] == "simulated tool failure"
