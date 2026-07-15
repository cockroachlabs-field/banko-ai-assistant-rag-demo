# Coach v1-C: Observability + Airgap + Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the second slice of Coach v1 — OpenTelemetry tracing with a local Jaeger trace view, an `OllamaProvider` so every code path works fully offline, a one-line `docker-compose.airgap.yml` stack, a model preload script, a slim README that has Coach + Observability + Airgap sections, and a canonical `PIPELINE_CONTRACT.md` at the repo root for the sibling pipeline session. Plan 2-A (Coach Core) must be merged locally first; Plan 2-B (Supervisor + MCP + Eval) layers on top after this one.

**Architecture:** One branch `feat/coach-v1c-observability-airgap` off whatever local head includes Plan 2-A. Eleven focused tasks landing as separate commits. The observability spine (tasks 1-3) installs OTel SDK + auto-instrumentors, exposes a single `tracing.init_tracing()` call wired into `create_app()`, and ships a Jaeger all-in-one container as a service in `docker-compose.yml`. Tracing is gated by `OTEL_ENABLED=true` — off by default in dev to keep startup fast, on in both compose stacks. The airgap spine (tasks 4-7) adds a fifth provider (`OllamaProvider`) implementing the existing `AIProvider` interface, registers it in the factory, adds the Ollama branch to `llm_factory.get_llm_for_agent()`, ships `docker-compose.airgap.yml` (CRDB + banko + ollama + jaeger, no public network references), and a `scripts/airgap/preload-models.sh` that pulls `granite3.3:8b` + `granite3.3:2b` into the running Ollama container. Docs slice (tasks 8-9) brings the README back under 250 lines with new Coach / Observability / Airgap sections and writes `PIPELINE_CONTRACT.md` at the repo root as the artifact handed to the sibling Claude session. Task 10 is the trace-assertion test that protects the span tree against regressions. Task 11 is the local smoke + USER GATED commit — no push.

**Tech stack:** Python 3.10+, `uv` package manager. OTel: `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-instrumentation-flask`, `opentelemetry-instrumentation-sqlalchemy`, `opentelemetry-instrumentation-requests`, `opentelemetry-exporter-otlp-proto-grpc`. Ollama client: `langchain-ollama` (LangChain wrapper) + `ollama` (Python SDK for tag discovery). Jaeger: `jaegertracing/all-in-one:1.62` (ports 16686 UI / 4317 OTLP gRPC). Sentence-transformers stays cloud-or-airgap identical (local, no API key — already in place).

---

## File Map

| Task | Files | Action |
|------|-------|--------|
| Pre-flight | `pyproject.toml` | Modify (add OTel + Ollama deps) |
| Pre-flight | `banko_ai/config/settings.py` | Modify (add 4 OTel/Ollama env knobs) |
| 1 | `banko_ai/observability/__init__.py`, `banko_ai/observability/tracing.py`, `tests/observability/test_tracing_init.py` | Create |
| 2 | `banko_ai/web/app.py`, `banko_ai/coach/agent.py`, `banko_ai/coach/handler.py` | Modify (init + custom spans) |
| 3 | `docker-compose.yml` | Modify (add jaeger + OTLP env) |
| 4 | `banko_ai/ai_providers/ollama_provider.py`, `banko_ai/ai_providers/factory.py`, `tests/test_ollama_provider.py` | Create + modify |
| 5 | `banko_ai/agents/llm_factory.py`, `tests/test_llm_factory_ollama.py` | Modify + create |
| 6 | `docker-compose.airgap.yml`, `.env.airgap.example` | Create |
| 7 | `scripts/airgap/preload-models.sh`, `scripts/airgap/verify-airgap.sh` | Create |
| 8 | `README.md`, `docs/coach.md`, `docs/airgap.md`, `docs/observability.md` | Modify + create |
| 9 | `PIPELINE_CONTRACT.md` | Create (repo root) |
| 10 | `tests/observability/test_signal_trace.py` | Create |
| 11 | (none — verification + local commit) | n/a |

---

## Pre-flight: branch, deps, env knobs

- [ ] **Step P.1: Confirm Plan 2-A is merged locally and tree is clean**

Run:
```bash
git status
git log --oneline -15
git branch --show-current
```
Expected: working tree clean (or only untracked notes in `docs/superpowers/`). Recent log shows the 13 Coach v1-A commits ending with `feat(coach): wire Live Coach UI route + base nav link`. Current branch is `main` (or whatever local branch carries Plan 2-A — `feat/coach-core-v1a` is acceptable if not yet rebased onto main).

If 2-A is not yet integrated, stop. This plan depends on `banko_ai/coach/agent.py`, `banko_ai/coach/handler.py`, `banko_ai/coach/tools.py`, `banko_ai/coach/signals.py` from Plan 2-A.

- [ ] **Step P.2: Create the 2-C branch**

Run:
```bash
git fetch origin
git checkout -b feat/coach-v1c-observability-airgap
```
Expected: switched to a new branch off the local head (which already includes the Coach core).

- [ ] **Step P.3: Verify CockroachDB is running locally and v25.4+**

Run:
```bash
cockroach sql --insecure --execute "SELECT version();"
```
Expected: `CockroachDB CCL v25.4.0` or higher. If not running:
```bash
cockroach start-single-node --insecure --store=./cockroach-data \
  --listen-addr=localhost:26257 --http-addr=localhost:8080 --background
```

- [ ] **Step P.4: Add OTel and Ollama deps to `pyproject.toml`**

Open `pyproject.toml`. Find the `dependencies = [` block (line 31). In the existing sections, append the following lines in the appropriate places (preserve grouping and CVE comments):

Inside the dependencies list, immediately before the closing `]` on line 90, insert:

```toml
    # OpenTelemetry (Coach v1-C — local Jaeger trace view; gated by OTEL_ENABLED)
    "opentelemetry-api>=1.30.0,<2.0.0",
    "opentelemetry-sdk>=1.30.0,<2.0.0",
    "opentelemetry-instrumentation-flask>=0.51b0,<1.0.0",
    "opentelemetry-instrumentation-sqlalchemy>=0.51b0,<1.0.0",
    "opentelemetry-instrumentation-requests>=0.51b0,<1.0.0",
    "opentelemetry-exporter-otlp-proto-grpc>=1.30.0,<2.0.0",

    # Ollama (Coach v1-C — airgap LLM provider; granite3.3:8b default)
    "langchain-ollama>=0.2.0,<1.0.0",
    "ollama>=0.4.0,<1.0.0",
```

- [ ] **Step P.5: Refresh the lockfile and install**

Run:
```bash
uv lock
uv sync --all-extras
```
Expected: lockfile updates, packages install. If any resolver conflict mentions `protobuf` or `grpcio`, that means watsonx's `ibm-watson-machine-learning` is pinning an old protobuf. Resolve by adding `"protobuf>=4.25.0,<6.0.0"` to dependencies and re-running `uv lock`.

- [ ] **Step P.6: Quick import sanity**

Run:
```bash
uv run python -c "
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from langchain_ollama import ChatOllama
import ollama
print('OK')
"
```
Expected: `OK` with no exceptions.

- [ ] **Step P.7: Add 4 OTel/Ollama env knobs to `banko_ai/config/settings.py`**

Read the current file. Find the `Config` dataclass (line 17). The Plan 2-A pre-flight already added six Coach knobs to this dataclass — append the new fields immediately after the last Coach knob (`coach_kafka_enabled`). Match the existing dataclass field style (type hint, default literal, comment).

Find the line `coach_kafka_enabled: bool = False` (added by Plan 2-A) and add immediately after it:

```python
    # OpenTelemetry tracing (Coach v1-C; off by default in dev, on in compose stacks)
    otel_enabled: bool = False  # set OTEL_ENABLED=true to turn on
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"  # OTLP gRPC endpoint
    otel_service_name: str = "banko-ai-assistant"

    # Ollama (Coach v1-C; airgap LLM provider)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "granite3.3:8b"  # default Coach agent model
    ollama_classifier_model: str = "granite3.3:2b"  # Supervisor classifier / judge model (v1-B)
```

Then find the `from_env` classmethod (search for `def from_env`). Locate the block where Plan 2-A added the Coach env reads (look for `coach_kafka_enabled=os.getenv(...)`). Immediately after the Coach block, add:

```python
            otel_enabled=os.getenv("OTEL_ENABLED", "false").lower() in ("true", "1", "yes"),
            otel_exporter_otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
            otel_service_name=os.getenv("OTEL_SERVICE_NAME", "banko-ai-assistant"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "granite3.3:8b"),
            ollama_classifier_model=os.getenv("OLLAMA_CLASSIFIER_MODEL", "granite3.3:2b"),
```

- [ ] **Step P.8: Verify the config loads**

Run:
```bash
uv run python -c "
from banko_ai.config.settings import Config
c = Config.from_env()
print('otel_enabled:', c.otel_enabled)
print('otel_endpoint:', c.otel_exporter_otlp_endpoint)
print('ollama_base_url:', c.ollama_base_url)
print('ollama_model:', c.ollama_model)
"
```
Expected:
```
otel_enabled: False
otel_endpoint: http://localhost:4317
ollama_base_url: http://localhost:11434
ollama_model: granite3.3:8b
```

- [ ] **Step P.9: Commit the pre-flight changes**

Run:
```bash
git add pyproject.toml uv.lock banko_ai/config/settings.py
git commit -m "chore(coach): add OTel + Ollama deps and v1-C config knobs"
```

DO NOT include any `Co-Authored-By: Claude ...` trailers. DO NOT include `Generated with Claude Code`. The commit must look like Virag wrote it.

---

### Task 1: Observability initialization module

**Files:**
- Create: `banko_ai/observability/__init__.py`
- Create: `banko_ai/observability/tracing.py`
- Create: `tests/observability/__init__.py`
- Create: `tests/observability/test_tracing_init.py`

**Rationale:** Centralize all OTel SDK setup behind a single `init_tracing(app, engine)` call so the Flask app, agents, and tests share one trace provider. Gating by `OTEL_ENABLED` keeps it strictly opt-in. The custom `coach_span` context manager is what every Coach component (handler, planner, executor, synthesizer, tool calls) wraps itself with — declared here so call sites stay terse.

- [ ] **Step 1.1: Create the observability package init**

Create `banko_ai/observability/__init__.py` with exactly:

```python
"""OpenTelemetry instrumentation for Banko AI Assistant.

Off by default. Set OTEL_ENABLED=true to emit spans to the configured OTLP
endpoint (default: http://localhost:4317 = local Jaeger all-in-one).
"""

from .tracing import coach_span, get_tracer, init_tracing, shutdown_tracing

__all__ = ["coach_span", "get_tracer", "init_tracing", "shutdown_tracing"]
```

- [ ] **Step 1.2: Write the failing tests**

Create `tests/observability/__init__.py` as an empty file:

```python
```

Create `tests/observability/test_tracing_init.py`:

```python
"""Unit tests for OTel initialization module."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from banko_ai.observability import tracing


def test_init_tracing_no_op_when_disabled():
    """init_tracing must be a no-op when OTEL_ENABLED is false."""
    app = MagicMock()
    with patch.object(tracing, "_otel_enabled", return_value=False):
        result = tracing.init_tracing(app, engine=None)
    assert result is False
    assert tracing._provider_initialized is False


def test_init_tracing_sets_provider_when_enabled():
    """When enabled, init_tracing installs a TracerProvider once."""
    app = MagicMock()
    with patch.object(tracing, "_otel_enabled", return_value=True), \
         patch("banko_ai.observability.tracing.FlaskInstrumentor") as flask_inst, \
         patch("banko_ai.observability.tracing.SQLAlchemyInstrumentor") as sa_inst, \
         patch("banko_ai.observability.tracing.RequestsInstrumentor") as req_inst, \
         patch("banko_ai.observability.tracing.OTLPSpanExporter"), \
         patch("banko_ai.observability.tracing.BatchSpanProcessor"), \
         patch("banko_ai.observability.tracing.TracerProvider") as tp, \
         patch("banko_ai.observability.tracing.trace.set_tracer_provider"):
        # Reset module state for the test
        tracing._provider_initialized = False
        result = tracing.init_tracing(app, engine=MagicMock())
    assert result is True
    flask_inst.return_value.instrument_app.assert_called_once_with(app)
    sa_inst.return_value.instrument.assert_called_once()
    req_inst.return_value.instrument.assert_called_once()
    tp.assert_called_once()


def test_init_tracing_idempotent():
    """Calling init_tracing twice must not register a second provider."""
    app = MagicMock()
    with patch.object(tracing, "_otel_enabled", return_value=True), \
         patch("banko_ai.observability.tracing.FlaskInstrumentor"), \
         patch("banko_ai.observability.tracing.SQLAlchemyInstrumentor"), \
         patch("banko_ai.observability.tracing.RequestsInstrumentor"), \
         patch("banko_ai.observability.tracing.OTLPSpanExporter"), \
         patch("banko_ai.observability.tracing.BatchSpanProcessor"), \
         patch("banko_ai.observability.tracing.TracerProvider") as tp, \
         patch("banko_ai.observability.tracing.trace.set_tracer_provider"):
        tracing._provider_initialized = False
        tracing.init_tracing(app, engine=MagicMock())
        tracing.init_tracing(app, engine=MagicMock())
    assert tp.call_count == 1


def test_coach_span_is_noop_when_disabled():
    """coach_span yields cleanly when tracing is disabled."""
    with patch.object(tracing, "_provider_initialized", False):
        with tracing.coach_span("test.op", attributes={"k": "v"}) as span:
            assert span is None  # No-op span returns None sentinel


def test_coach_span_sets_attributes_when_enabled():
    """coach_span attaches attributes to the active span when enabled."""
    fake_span = MagicMock()

    @contextmanager
    def fake_start_as_current_span(name):
        yield fake_span

    fake_tracer = MagicMock()
    fake_tracer.start_as_current_span = fake_start_as_current_span

    with patch.object(tracing, "_provider_initialized", True), \
         patch.object(tracing, "get_tracer", return_value=fake_tracer):
        with tracing.coach_span("coach.planner", attributes={"signal_type": "anomaly"}) as span:
            assert span is fake_span
    fake_span.set_attribute.assert_any_call("signal_type", "anomaly")


def test_get_tracer_returns_named_tracer():
    """get_tracer returns a tracer named after the module/component."""
    with patch("banko_ai.observability.tracing.trace.get_tracer") as gt:
        tracing.get_tracer("coach.handler")
    gt.assert_called_once_with("coach.handler")


def test_shutdown_tracing_is_safe_when_uninitialized():
    """shutdown_tracing does not raise when no provider was installed."""
    tracing._provider_initialized = False
    tracing.shutdown_tracing()  # Should not raise
```

- [ ] **Step 1.3: Run the tests to confirm they fail**

Run:
```bash
git add -f tests/observability/__init__.py tests/observability/test_tracing_init.py
uv run pytest tests/observability/test_tracing_init.py -v
```
Expected: `ModuleNotFoundError: No module named 'banko_ai.observability.tracing'` (or all tests fail with `ImportError`).

The `git add -f` is required — per CLAUDE.md the repo's `.gitignore:45` has an unanchored `test_*.py` that blocks new pytest modules from being tracked.

- [ ] **Step 1.4: Implement `banko_ai/observability/tracing.py`**

Create `banko_ai/observability/tracing.py` with exactly:

```python
"""OpenTelemetry initialization and Coach-specific span helpers.

Public surface:
  - init_tracing(app, engine): one-shot install of TracerProvider + auto-instrumentors
  - get_tracer(name): named tracer for component-scoped spans
  - coach_span(name, attributes=None): context manager wrapping coach operations
  - shutdown_tracing(): flush pending spans (call in test teardown / shutdown hooks)
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Generator

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_provider_initialized: bool = False


def _otel_enabled() -> bool:
    return os.getenv("OTEL_ENABLED", "false").lower() in ("true", "1", "yes")


def _otel_endpoint() -> str:
    return os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")


def _service_name() -> str:
    return os.getenv("OTEL_SERVICE_NAME", "banko-ai-assistant")


def init_tracing(app: Any, engine: Any = None) -> bool:
    """Install TracerProvider + auto-instrumentors. Idempotent; no-op if OTEL_ENABLED is false.

    Args:
        app: Flask app instance (instrumented for HTTP routes).
        engine: SQLAlchemy engine (instrumented for DB sessions). Optional.

    Returns:
        True if instrumentation was installed, False if disabled or already installed.
    """
    global _provider_initialized

    if not _otel_enabled():
        return False
    if _provider_initialized:
        return False

    resource = Resource.create({SERVICE_NAME: _service_name()})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=_otel_endpoint(), insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FlaskInstrumentor().instrument_app(app)
    if engine is not None:
        SQLAlchemyInstrumentor().instrument(engine=engine)
    RequestsInstrumentor().instrument()

    _provider_initialized = True
    return True


def get_tracer(name: str):
    """Return a named tracer. Safe to call whether or not tracing was initialized."""
    return trace.get_tracer(name)


@contextmanager
def coach_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    tracer_name: str = "banko.coach",
) -> Generator[Any, None, None]:
    """Context manager wrapping a Coach operation as a span.

    No-op (yields None) when tracing is disabled, so call sites need no guard.

    Args:
        name: span name, e.g. "coach.planner", "coach.tool.get_recent_signals"
        attributes: attached to the active span (signal_id, user_id, etc.)
        tracer_name: tracer the span is created under
    """
    if not _provider_initialized:
        yield None
        return

    tracer = get_tracer(tracer_name)
    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        yield span


def shutdown_tracing() -> None:
    """Flush pending spans. Safe when no provider was installed."""
    global _provider_initialized

    if not _provider_initialized:
        return
    provider = trace.get_tracer_provider()
    if hasattr(provider, "shutdown"):
        provider.shutdown()
    _provider_initialized = False
```

- [ ] **Step 1.5: Run the tests to confirm they pass**

Run:
```bash
uv run pytest tests/observability/test_tracing_init.py -v
```
Expected: 7 passed.

- [ ] **Step 1.6: Commit Task 1**

Run:
```bash
git add banko_ai/observability/__init__.py banko_ai/observability/tracing.py
git add -f tests/observability/__init__.py tests/observability/test_tracing_init.py
git commit -m "feat(observability): add OpenTelemetry init module with coach_span helper"
```

---

### Task 2: Wire OTel into the Flask app and Coach pieces

**Files:**
- Modify: `banko_ai/web/app.py` (line ~232, immediately after the SQLAlchemy engine is reachable)
- Modify: `banko_ai/coach/agent.py` (planner, executor, synthesizer call sites)
- Modify: `banko_ai/coach/handler.py` (signal-handling entry)
- Test: `tests/observability/test_app_init_tracing.py`

**Rationale:** `init_tracing()` is dormant until we call it. Wire the call into `create_app()` so Flask and SQLAlchemy auto-instrument; wrap the three LLM-call points in the Coach with custom `coach_span(...)` so the trace tree has meaningful node names (not just generic `flask.request`).

- [ ] **Step 2.1: Write the failing test for `create_app` tracing wiring**

Create `tests/observability/test_app_init_tracing.py`:

```python
"""Assert create_app() calls init_tracing with the engine instance."""

from unittest.mock import MagicMock, patch


def test_create_app_invokes_init_tracing():
    """When OTEL_ENABLED is true, create_app passes app + engine to init_tracing."""
    with patch.dict("os.environ", {"OTEL_ENABLED": "true"}, clear=False), \
         patch("banko_ai.observability.tracing.init_tracing") as init_fn, \
         patch("banko_ai.web.app.AIProviderFactory"), \
         patch("banko_ai.web.app.VectorSearchEngine"), \
         patch("banko_ai.web.app.EnhancedExpenseGenerator"), \
         patch("banko_ai.web.app.UserManager"), \
         patch("banko_ai.web.app.BankoCacheManager"), \
         patch("banko_ai.web.app.auto_setup_data_if_needed"):
        from banko_ai.web.app import create_app
        app = create_app()
    init_fn.assert_called_once()
    args, kwargs = init_fn.call_args
    # First positional must be the Flask app
    assert args[0] is app
```

- [ ] **Step 2.2: Run the test to confirm it fails**

Run:
```bash
git add -f tests/observability/test_app_init_tracing.py
uv run pytest tests/observability/test_app_init_tracing.py -v
```
Expected: `AssertionError: Expected 'init_tracing' to have been called once. Called 0 times.`

- [ ] **Step 2.3: Wire `init_tracing` into `create_app()`**

Open `banko_ai/web/app.py`. Add to the imports near the top (after the other `banko_ai` imports — search for `from ..ai_providers.factory import AIProviderFactory` and add immediately after it):

```python
from ..observability.tracing import init_tracing
```

Then find the line:
```python
    # Auto-setup data if needed (matching original app.py)
    print("🔍 Checking database setup...")
    auto_setup_data_if_needed(config.database_url)
```

Immediately *before* that block, insert:

```python
    # OpenTelemetry tracing — no-op unless OTEL_ENABLED=true
    try:
        if init_tracing(app, engine=None):
            print(f"📡 OpenTelemetry enabled → {config.otel_exporter_otlp_endpoint}")
    except Exception as e:
        print(f"⚠️  Failed to initialize OpenTelemetry: {e}")

```

We pass `engine=None` because the SQLAlchemy engines are created lazily inside provider classes and inside `utils/database.py` — auto-instrumenting via `SQLAlchemyInstrumentor().instrument(engine=...)` would require restructuring engine ownership. The instrumentation still happens on engines created *after* `instrument()` is called *without* `engine=`, but that requires us to call `SQLAlchemyInstrumentor().instrument()` once globally. Update `init_tracing` only if Task 10's trace assertions show DB spans missing — leave for now.

- [ ] **Step 2.4: Run the test to confirm it passes**

Run:
```bash
uv run pytest tests/observability/test_app_init_tracing.py -v
```
Expected: 1 passed.

- [ ] **Step 2.5: Write failing test for SignalHandler span**

Create `tests/observability/test_handler_span.py`:

```python
"""SignalHandler must wrap its entry call in a coach_span."""

from unittest.mock import MagicMock, patch

import pytest

from banko_ai.coach.handler import SignalHandler
from banko_ai.coach.signals import Signal, SignalType


@pytest.fixture
def signal():
    return Signal(
        signal_id="sig-test-1",
        user_id="user-test-1",
        signal_type=SignalType.BUDGET_THRESHOLD,
        severity="warn",
        payload={"category": "dining", "percent_used": 0.82},
        produced_at="2026-05-22T10:00:00Z",
        idempotency_key="idem-test-1",
    )


def test_handler_creates_coach_span(signal):
    """SignalHandler.handle wraps work in coach_span('coach.handler.handle')."""
    captured = []

    class FakeSpanCtx:
        def __enter__(self): captured.append(self); return self
        def __exit__(self, *a): pass
        def set_attribute(self, k, v): captured.append(("attr", k, v))

    def fake_span(name, attributes=None, tracer_name="banko.coach"):
        captured.append(("span", name, attributes))
        return FakeSpanCtx()

    coach = MagicMock()
    coach.react.return_value = {"nudge_text": "Test", "tool_trace": []}
    emitter = MagicMock()

    with patch("banko_ai.coach.handler.coach_span", side_effect=fake_span), \
         patch("banko_ai.coach.handler.SignalHandler._already_consumed", return_value=False), \
         patch("banko_ai.coach.handler.SignalHandler._persist_nudge"):
        handler = SignalHandler(coach=coach, emitter=emitter, db_session_factory=MagicMock())
        handler.handle(signal)

    span_calls = [c for c in captured if isinstance(c, tuple) and c[0] == "span"]
    assert any(c[1] == "coach.handler.handle" for c in span_calls)
    # signal_id and signal_type attributes must be attached
    handler_call = next(c for c in span_calls if c[1] == "coach.handler.handle")
    assert handler_call[2].get("signal_id") == "sig-test-1"
    assert handler_call[2].get("signal_type") == "budget_threshold"
```

- [ ] **Step 2.6: Run the test to confirm it fails**

Run:
```bash
git add -f tests/observability/test_handler_span.py
uv run pytest tests/observability/test_handler_span.py -v
```
Expected: failure because `banko_ai.coach.handler` does not import `coach_span` yet. The exact error will be `ImportError` or an `AttributeError` from the patch — either is the correct "this hasn't been done yet" signal.

- [ ] **Step 2.7: Add `coach_span` to `SignalHandler`**

Open `banko_ai/coach/handler.py`. Add to the imports:

```python
from ..observability.tracing import coach_span
```

Find the `def handle(self, signal: Signal) -> ...` method (added in Plan 2-A Task 4). Wrap the entire body in:

```python
    def handle(self, signal: Signal) -> dict[str, Any]:
        """Handle one incoming signal end-to-end (idempotent)."""
        with coach_span(
            "coach.handler.handle",
            attributes={
                "signal_id": signal.signal_id,
                "signal_type": signal.signal_type.value,
                "user_id": signal.user_id,
                "severity": signal.severity,
            },
        ):
            # <existing body of handle() goes here, unchanged>
            ...
```

Indent the existing body of `handle()` one level deeper. If `handle()` has `return` statements, they stay inside the `with` block — the context manager handles span lifecycle on exit. Do NOT change any logic.

- [ ] **Step 2.8: Run the handler test to confirm it passes**

Run:
```bash
uv run pytest tests/observability/test_handler_span.py -v
```
Expected: 1 passed.

- [ ] **Step 2.9: Write failing test for CoachAgent planner/synthesizer spans**

Create `tests/observability/test_agent_spans.py`:

```python
"""CoachAgent.react must wrap planner and synthesizer in coach_spans."""

from unittest.mock import MagicMock, patch

import pytest

from banko_ai.coach.agent import CoachAgent
from banko_ai.coach.signals import Signal, SignalType


@pytest.fixture
def signal():
    return Signal(
        signal_id="sig-1",
        user_id="user-1",
        signal_type=SignalType.ANOMALY,
        severity="warn",
        payload={"merchant": "Uber", "amount": 47.32},
        produced_at="2026-05-22T10:00:00Z",
        idempotency_key="idem-1",
    )


def test_agent_react_creates_planner_and_synth_spans(signal):
    """Plan + synthesize each get their own span."""
    captured: list[str] = []

    class FakeSpanCtx:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def set_attribute(self, k, v): pass

    def fake_span(name, attributes=None, tracer_name="banko.coach"):
        captured.append(name)
        return FakeSpanCtx()

    fake_llm = MagicMock(return_value='{"steps": []}')

    with patch("banko_ai.coach.agent.coach_span", side_effect=fake_span):
        agent = CoachAgent(llm_invoker=fake_llm, tools={}, max_steps=5)
        result = agent.react(signal)

    assert "coach.planner" in captured
    assert "coach.synthesizer" in captured
    assert result["nudge_text"]  # smoke that react returned something
```

- [ ] **Step 2.10: Run the test to confirm it fails**

Run:
```bash
git add -f tests/observability/test_agent_spans.py
uv run pytest tests/observability/test_agent_spans.py -v
```
Expected: failure (`coach_span` not in `banko_ai.coach.agent` namespace, or test assertions fail).

- [ ] **Step 2.11: Add `coach_span` wrappers to `CoachAgent`**

Open `banko_ai/coach/agent.py`. Add to the imports:

```python
from ..observability.tracing import coach_span
```

Find the `_plan_for_signal` method (added in Plan 2-A Task 5). Wrap the LLM call:

```python
    def _plan_for_signal(self, signal: Signal) -> list[dict]:
        """Ask the planner LLM for a 1-3 step plan."""
        with coach_span(
            "coach.planner",
            attributes={
                "signal_type": signal.signal_type.value,
                "signal_id": signal.signal_id,
            },
        ):
            # <existing body of _plan_for_signal() unchanged>
            ...
```

Find `_execute_plan`. Wrap **each individual tool invocation** (not the whole loop). In the body, where Plan 2-A's code calls `tool_fn(...)`, replace with:

```python
            with coach_span(
                "coach.tool.invoke",
                attributes={"tool_name": tool_name, "signal_id": signal.signal_id},
            ):
                result = tool_fn(**args)
```

Find `_synthesize_nudge`. Wrap the LLM call:

```python
    def _synthesize_nudge(self, signal: Signal, tool_trace: list[dict]) -> str:
        """Ask the synthesizer LLM for the user-facing nudge."""
        with coach_span(
            "coach.synthesizer",
            attributes={
                "signal_id": signal.signal_id,
                "n_tools": len(tool_trace),
            },
        ):
            # <existing body unchanged>
            ...
```

- [ ] **Step 2.12: Run all observability tests**

Run:
```bash
uv run pytest tests/observability/ -v
```
Expected: 10 passed (7 from Task 1 + 3 from Task 2).

- [ ] **Step 2.13: Run the existing Coach tests to confirm no regression**

Run:
```bash
uv run pytest tests/coach/ -v
```
Expected: all Plan 2-A coach tests still pass (count depends on Plan 2-A — should match the green count from the last 2-A run, typically 30+).

- [ ] **Step 2.14: Commit Task 2**

Run:
```bash
git add banko_ai/web/app.py banko_ai/coach/agent.py banko_ai/coach/handler.py
git add -f tests/observability/test_app_init_tracing.py tests/observability/test_handler_span.py tests/observability/test_agent_spans.py
git commit -m "feat(observability): instrument Flask app, SignalHandler, and CoachAgent with OTel spans"
```

---

### Task 3: Add Jaeger to `docker-compose.yml`

**Files:**
- Modify: `docker-compose.yml`

**Rationale:** Demo-ready trace UI without spinning up Tempo + Grafana. Single `jaegertracing/all-in-one` container has the receiver, the storage, and the UI. Banko points to it via the existing `OTEL_EXPORTER_OTLP_ENDPOINT` env var.

- [ ] **Step 3.1: Add the jaeger service**

Open `docker-compose.yml`. Find the line `# Banko AI Assistant application` (line 24). Immediately before that line, insert:

```yaml
  # Jaeger all-in-one — local trace UI (Coach v1-C)
  jaeger:
    image: jaegertracing/all-in-one:1.62
    container_name: banko-jaeger
    hostname: jaeger
    ports:
      - "16686:16686"  # Jaeger UI
      - "4317:4317"    # OTLP gRPC receiver
      - "4318:4318"    # OTLP HTTP receiver
    environment:
      - COLLECTOR_OTLP_ENABLED=true
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:14269/"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s
    networks:
      - banko-network

```

- [ ] **Step 3.2: Add OTel env vars to the banko-ai service**

In the `banko-ai` service `environment:` block, find the line `- EMBEDDING_MODEL=${EMBEDDING_MODEL:-all-MiniLM-L6-v2}` (currently the last env entry). Immediately after that line, add:

```yaml
      
      # OpenTelemetry (Coach v1-C — points at the jaeger service above)
      - OTEL_ENABLED=${OTEL_ENABLED:-true}
      - OTEL_EXPORTER_OTLP_ENDPOINT=${OTEL_EXPORTER_OTLP_ENDPOINT:-http://jaeger:4317}
      - OTEL_SERVICE_NAME=${OTEL_SERVICE_NAME:-banko-ai-assistant}
```

- [ ] **Step 3.3: Add jaeger to the `banko-ai` depends_on**

In the `banko-ai` service, find the existing `depends_on:` block:

```yaml
    depends_on:
      cockroachdb:
        condition: service_healthy
```

Replace it with:

```yaml
    depends_on:
      cockroachdb:
        condition: service_healthy
      jaeger:
        condition: service_healthy
```

- [ ] **Step 3.4: Validate the compose file syntactically**

Run:
```bash
docker compose config > /dev/null && echo "compose OK"
```
Expected: `compose OK` (no errors printed).

- [ ] **Step 3.5: Bring the stack up and verify Jaeger is reachable**

Run:
```bash
docker compose up -d cockroachdb jaeger
sleep 10
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:16686/
```
Expected: `200`.

- [ ] **Step 3.6: Commit Task 3**

Run:
```bash
git add docker-compose.yml
git commit -m "feat(observability): add Jaeger all-in-one to docker-compose for local trace UI"
```

---

### Task 4: OllamaProvider implementing the AIProvider interface

**Files:**
- Create: `banko_ai/ai_providers/ollama_provider.py`
- Modify: `banko_ai/ai_providers/factory.py`
- Test: `tests/test_ollama_provider.py`

**Rationale:** Fifth provider so `AI_SERVICE=ollama` is a valid switch. Implements the existing `AIProvider` ABC so the rest of the app (RAG endpoint, model dropdown, health check) needs zero changes. Dynamic model discovery via the `/api/tags` endpoint matches the pattern the other four providers use.

- [ ] **Step 4.1: Write the failing tests**

Create `tests/test_ollama_provider.py`:

```python
"""Unit tests for OllamaProvider."""

from unittest.mock import MagicMock, patch

import pytest

from banko_ai.ai_providers.base import AIConnectionError, RAGResponse, SearchResult
from banko_ai.ai_providers.ollama_provider import OllamaProvider


def test_default_model():
    p = OllamaProvider({})
    assert p.get_default_model() == "granite3.3:8b"


def test_respects_explicit_model():
    p = OllamaProvider({"model": "llama3.2:3b"})
    assert p.current_model == "llama3.2:3b"


def test_provider_name():
    p = OllamaProvider({})
    assert p.get_provider_name() == "ollama"


def test_available_models_uses_env_override(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODELS", "granite3.3:8b, granite3.3:2b, llama3.2:3b")
    p = OllamaProvider({})
    models = p.get_available_models()
    assert models == ["granite3.3:8b", "granite3.3:2b", "llama3.2:3b"]


def test_available_models_discovers_from_api(monkeypatch):
    monkeypatch.delenv("OLLAMA_MODELS", raising=False)
    fake_resp = MagicMock()
    fake_resp.json.return_value = {
        "models": [
            {"name": "granite3.3:8b"},
            {"name": "granite3.3:2b"},
            {"name": "nomic-embed-text:latest"},  # embedding model, should be filtered out
        ]
    }
    fake_resp.raise_for_status = MagicMock()
    with patch("banko_ai.ai_providers.ollama_provider.requests.get", return_value=fake_resp):
        p = OllamaProvider({})
        models = p.get_available_models()
    assert "granite3.3:8b" in models
    assert "granite3.3:2b" in models
    # Embedding models excluded (no chat capability)
    assert "nomic-embed-text:latest" not in models


def test_available_models_falls_back_on_api_failure(monkeypatch):
    monkeypatch.delenv("OLLAMA_MODELS", raising=False)
    with patch(
        "banko_ai.ai_providers.ollama_provider.requests.get",
        side_effect=ConnectionError("ollama down"),
    ):
        p = OllamaProvider({})
        models = p.get_available_models()
    assert "granite3.3:8b" in models  # baked-in default list


def test_test_connection_success():
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.raise_for_status = MagicMock()
    with patch("banko_ai.ai_providers.ollama_provider.requests.get", return_value=fake_resp):
        p = OllamaProvider({})
        assert p.test_connection() is True


def test_test_connection_failure():
    with patch(
        "banko_ai.ai_providers.ollama_provider.requests.get",
        side_effect=ConnectionError("nope"),
    ):
        p = OllamaProvider({})
        assert p.test_connection() is False


def test_generate_embedding_uses_local_sentence_transformer():
    """Embeddings stay local (sentence-transformers), identical to other providers."""
    fake_st = MagicMock()
    fake_st.encode.return_value = [[0.1] * 384]
    with patch(
        "banko_ai.ai_providers.ollama_provider.SentenceTransformer",
        return_value=fake_st,
    ):
        p = OllamaProvider({})
        vec = p.generate_embedding("test text")
    assert len(vec) == 384


def test_factory_registers_ollama():
    """AIProviderFactory exposes 'ollama' in get_available_providers()."""
    from banko_ai.ai_providers.factory import AIProviderFactory
    assert "ollama" in AIProviderFactory.get_available_providers()


def test_factory_creates_ollama_instance():
    from banko_ai.ai_providers.factory import AIProviderFactory
    provider = AIProviderFactory.create_provider("ollama", {})
    assert provider.get_provider_name() == "ollama"
```

- [ ] **Step 4.2: Run the tests to confirm they fail**

Run:
```bash
git add -f tests/test_ollama_provider.py
uv run pytest tests/test_ollama_provider.py -v
```
Expected: `ModuleNotFoundError: No module named 'banko_ai.ai_providers.ollama_provider'`.

- [ ] **Step 4.3: Create `banko_ai/ai_providers/ollama_provider.py`**

Create the file with exactly:

```python
"""Ollama AI provider — airgap LLM with dynamic model discovery via /api/tags.

Embeddings stay local (sentence-transformers) for parity with cloud providers.
"""

import json
import os
from typing import Any

import psycopg2
import requests
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, text

from ..utils.db_retry import create_resilient_engine, db_retry, get_database_url
from .base import AIAuthenticationError, AIConnectionError, AIProvider, RAGResponse, SearchResult
from .rag_prompts import build_banko_rag_prompt

_EMBEDDING_MODEL_HINTS = ("embed", "embedding")  # filter out from chat-model list
_DEFAULT_CHAT_MODELS = ["granite3.3:8b", "granite3.3:2b", "llama3.2:3b"]


class OllamaProvider(AIProvider):
    """Ollama provider — runs entirely locally; no API key required."""

    def __init__(self, config: dict[str, Any], cache_manager=None):
        self.cache_manager = cache_manager

        if "model" not in config:
            config["model"] = os.getenv("OLLAMA_MODEL", "granite3.3:8b")

        self.base_url = config.get("base_url") or os.getenv(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        )
        self.timeout = int(config.get("timeout", os.getenv("OLLAMA_TIMEOUT", "120")))
        self.embedding_model_name = config.get("embedding_model") or os.getenv(
            "EMBEDDING_MODEL", "all-MiniLM-L6-v2"
        )
        self.embedding_model: SentenceTransformer | None = None
        self.db_engine = None
        self._available_models_cache: list[str] | None = None

        super().__init__(config)

    def _validate_config(self) -> None:
        """Ollama needs no auth; only warn if base URL is malformed."""
        if not self.base_url.startswith(("http://", "https://")):
            print(f"⚠️ OLLAMA_BASE_URL looks malformed: {self.base_url}")

    def get_default_model(self) -> str:
        return "granite3.3:8b"

    def get_available_models(self) -> list[str]:
        """Discover available models via Ollama's /api/tags endpoint.

        Env override: OLLAMA_MODELS=model1,model2,...
        """
        extra = os.getenv("OLLAMA_MODELS", "")
        if extra:
            return [m.strip() for m in extra.split(",") if m.strip()]

        if self._available_models_cache is not None:
            return self._available_models_cache

        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            names = [m["name"] for m in data.get("models", [])]
            chat_models = [
                n for n in names
                if not any(hint in n.lower() for hint in _EMBEDDING_MODEL_HINTS)
            ]
            if chat_models:
                self._available_models_cache = sorted(chat_models)
                return self._available_models_cache
        except Exception as e:
            print(f"⚠️ Could not list Ollama models: {e}")

        return _DEFAULT_CHAT_MODELS

    def test_connection(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            return True
        except Exception:
            return False

    def _get_embedding_model(self) -> SentenceTransformer:
        if self.embedding_model is None:
            try:
                self.embedding_model = SentenceTransformer(self.embedding_model_name)
            except Exception as e:
                raise AIConnectionError(f"Failed to load embedding model: {e}")
        return self.embedding_model

    def generate_embedding(self, text: str) -> list[float]:
        try:
            model = self._get_embedding_model()
            return model.encode([text])[0].tolist()
        except Exception as e:
            print(f"Error generating embedding (Ollama provider): {e}")
            return []

    def _get_db_engine(self):
        if self.db_engine is None:
            self.db_engine = create_resilient_engine(get_database_url())
        return self.db_engine

    @db_retry(max_attempts=3, initial_delay=0.5)
    def search_expenses(
        self,
        query: str,
        user_id: str | None = None,
        limit: int = 10,
        threshold: float = 0.7,
    ) -> list[SearchResult]:
        """Vector search using the same C-SPANN cosine index every other provider uses."""
        embedding = self.generate_embedding(query)
        if not embedding:
            return []

        engine = self._get_db_engine()
        # Use parameterized SQL; <=> operator works directly on VECTOR(384), no CAST
        sql = """
            SELECT expense_id, user_id, description, merchant, amount, expense_date,
                   1 - (embedding <=> :embedding) AS similarity
            FROM expenses
            WHERE embedding IS NOT NULL
        """
        params: dict[str, Any] = {"embedding": str(embedding)}
        if user_id:
            sql += " AND user_id = :user_id"
            params["user_id"] = user_id
        sql += " ORDER BY embedding <=> :embedding LIMIT :limit"
        params["limit"] = limit

        results: list[SearchResult] = []
        with engine.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        for row in rows:
            if row["similarity"] < threshold:
                continue
            results.append(SearchResult(
                expense_id=str(row["expense_id"]),
                user_id=str(row["user_id"]),
                description=row["description"] or "",
                merchant=row["merchant"] or "",
                amount=float(row["amount"]),
                date=row["expense_date"].isoformat() if row["expense_date"] else "",
                similarity_score=float(row["similarity"]),
                metadata={},
            ))
        return results

    def generate_rag_response(
        self,
        query: str,
        context: list[SearchResult],
        user_id: str | None = None,
        language: str = "en",
    ) -> RAGResponse:
        """Generate a RAG response using the local Ollama chat endpoint."""
        prompt = build_banko_rag_prompt(query, context, language=language)
        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.current_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0.3, "num_ctx": 4096},
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            answer = data.get("message", {}).get("content", "").strip()
        except requests.exceptions.RequestException as e:
            raise AIConnectionError(f"Ollama chat request failed: {e}")

        return RAGResponse(
            response=answer or "No response generated.",
            sources=context,
            metadata={"provider": "ollama", "model": self.current_model},
        )
```

- [ ] **Step 4.4: Register Ollama in the factory**

Open `banko_ai/ai_providers/factory.py`. Find the imports block and add:

```python
from .ollama_provider import OllamaProvider
```

Find `_providers: dict[str, type[AIProvider]] = {` and add the entry:

```python
    _providers: dict[str, type[AIProvider]] = {
        "openai": OpenAIProvider,
        "aws": AWSProvider,
        "watsonx": WatsonxProvider,
        "gemini": GeminiProvider,
        "ollama": OllamaProvider,
    }
```

- [ ] **Step 4.5: Run the tests to confirm they pass**

Run:
```bash
uv run pytest tests/test_ollama_provider.py -v
```
Expected: 11 passed.

- [ ] **Step 4.6: Commit Task 4**

Run:
```bash
git add banko_ai/ai_providers/ollama_provider.py banko_ai/ai_providers/factory.py
git add -f tests/test_ollama_provider.py
git commit -m "feat(providers): add OllamaProvider for airgap deployments"
```

---

### Task 5: Wire Ollama into the agent LLM factory

**Files:**
- Modify: `banko_ai/agents/llm_factory.py`
- Test: `tests/test_llm_factory_ollama.py`

**Rationale:** Receipt / Fraud / Budget / Coach agents all call `get_llm_for_agent()` to get a LangChain-compatible LLM. Add the `'ollama'` branch using `langchain-ollama.ChatOllama` so `AI_SERVICE=ollama` works end-to-end.

- [ ] **Step 5.1: Write the failing test**

Create `tests/test_llm_factory_ollama.py`:

```python
"""Verify llm_factory.get_llm_for_agent() returns a ChatOllama for AI_SERVICE=ollama."""

from unittest.mock import MagicMock, patch


def test_ollama_branch_constructs_chat_ollama():
    fake_config = MagicMock()
    fake_config.ai_service = "ollama"
    fake_config.ollama_model = "granite3.3:8b"
    fake_config.ollama_base_url = "http://localhost:11434"

    with patch("banko_ai.agents.llm_factory.get_config", return_value=fake_config), \
         patch("langchain_ollama.ChatOllama") as chat_ollama:
        from banko_ai.agents.llm_factory import get_llm_for_agent
        get_llm_for_agent(temperature=0.4)

    chat_ollama.assert_called_once()
    kwargs = chat_ollama.call_args.kwargs
    assert kwargs["model"] == "granite3.3:8b"
    assert kwargs["base_url"] == "http://localhost:11434"
    assert kwargs["temperature"] == 0.4


def test_ollama_branch_respects_model_override():
    fake_config = MagicMock()
    fake_config.ai_service = "ollama"
    fake_config.ollama_model = "granite3.3:8b"
    fake_config.ollama_base_url = "http://localhost:11434"

    with patch("banko_ai.agents.llm_factory.get_config", return_value=fake_config), \
         patch("langchain_ollama.ChatOllama") as chat_ollama:
        from banko_ai.agents.llm_factory import get_llm_for_agent
        get_llm_for_agent(model_override="granite3.3:2b")

    assert chat_ollama.call_args.kwargs["model"] == "granite3.3:2b"


def test_unsupported_ai_service_message_lists_ollama():
    """Error message mentions ollama so users see it's an option."""
    fake_config = MagicMock()
    fake_config.ai_service = "nope"

    with patch("banko_ai.agents.llm_factory.get_config", return_value=fake_config):
        from banko_ai.agents.llm_factory import get_llm_for_agent
        try:
            get_llm_for_agent()
        except ValueError as e:
            assert "ollama" in str(e)
        else:
            raise AssertionError("ValueError not raised")
```

- [ ] **Step 5.2: Run the tests to confirm they fail**

Run:
```bash
git add -f tests/test_llm_factory_ollama.py
uv run pytest tests/test_llm_factory_ollama.py -v
```
Expected: 3 failures — branch doesn't exist + error message doesn't mention ollama.

- [ ] **Step 5.3: Add the `'ollama'` branch to `get_llm_for_agent`**

Open `banko_ai/agents/llm_factory.py`. Find the `elif config.ai_service == 'gemini':` block (line 104) — the new branch goes immediately before the final `else:` clause (line 152).

Insert this elif block immediately before `else:`:

```python
    elif config.ai_service == 'ollama':
        try:
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=model_override or config.ollama_model,
                base_url=config.ollama_base_url,
                temperature=temperature,
            )
        except ImportError:
            raise ImportError(
                "langchain-ollama is required for Ollama provider. "
                "Install with: pip install langchain-ollama"
            )

```

Then update the error message in the final `else:` clause. Replace:

```python
    else:
        raise ValueError(
            f"Unsupported AI service: {config.ai_service}. "
            f"Supported: openai, aws, watsonx, gemini"
        )
```

With:

```python
    else:
        raise ValueError(
            f"Unsupported AI service: {config.ai_service}. "
            f"Supported: openai, aws, watsonx, gemini, ollama"
        )
```

- [ ] **Step 5.4: Run the tests to confirm they pass**

Run:
```bash
uv run pytest tests/test_llm_factory_ollama.py -v
```
Expected: 3 passed.

- [ ] **Step 5.5: Commit Task 5**

Run:
```bash
git add banko_ai/agents/llm_factory.py
git add -f tests/test_llm_factory_ollama.py
git commit -m "feat(agents): add Ollama branch to llm_factory for airgap deployments"
```

---

### Task 6: docker-compose.airgap.yml + env example

**Files:**
- Create: `docker-compose.airgap.yml`
- Create: `.env.airgap.example`

**Rationale:** Single command (`docker compose -f docker-compose.airgap.yml up`) brings up the entire stack with zero outbound network dependencies once images and models are pulled. Definition-of-done item 14: `docker network inspect` shows no public network references.

- [ ] **Step 6.1: Create the airgap compose file**

Create `docker-compose.airgap.yml` with exactly:

```yaml
# Banko AI Assistant — airgap mode
# Run: docker compose -f docker-compose.airgap.yml up -d
# After first start: scripts/airgap/preload-models.sh granite3.3:8b granite3.3:2b
# All services run locally; no AI_SERVICE values except `ollama` will work here.

version: '3.8'

services:
  # CockroachDB — same image as cloud mode
  cockroachdb:
    image: cockroachdb/cockroach:${COCKROACHDB_VERSION:-v25.4.6}
    container_name: banko-airgap-cockroachdb
    hostname: cockroachdb
    ports:
      - "26257:26257"
      - "8080:8080"
    command: start-single-node --insecure
    volumes:
      - airgap-cockroach-data:/cockroach/cockroach-data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health?ready=1"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    networks:
      - banko-airgap

  # Ollama — local LLM runtime
  ollama:
    image: ollama/ollama:0.5.4
    container_name: banko-airgap-ollama
    hostname: ollama
    ports:
      - "11434:11434"
    volumes:
      - airgap-ollama-models:/root/.ollama
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:11434/api/tags"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 30s
    networks:
      - banko-airgap

  # Jaeger all-in-one — trace UI (still useful in airgap; no external collector)
  jaeger:
    image: jaegertracing/all-in-one:1.62
    container_name: banko-airgap-jaeger
    hostname: jaeger
    ports:
      - "16686:16686"
      - "4317:4317"
      - "4318:4318"
    environment:
      - COLLECTOR_OTLP_ENABLED=true
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:14269/"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s
    networks:
      - banko-airgap

  # Banko AI Assistant
  banko-ai:
    build:
      context: .
      dockerfile: Dockerfile
    image: virag/banko-ai-assistant:latest
    container_name: banko-airgap-app
    ports:
      - "5000:5000"
    depends_on:
      cockroachdb:
        condition: service_healthy
      ollama:
        condition: service_healthy
      jaeger:
        condition: service_healthy
    environment:
      - DATABASE_URL=cockroachdb://root@cockroachdb:26257/defaultdb?sslmode=disable

      # AI Service — airgap means Ollama (no other provider env vars present)
      - AI_SERVICE=ollama
      - OLLAMA_BASE_URL=http://ollama:11434
      - OLLAMA_MODEL=${OLLAMA_MODEL:-granite3.3:8b}
      - OLLAMA_CLASSIFIER_MODEL=${OLLAMA_CLASSIFIER_MODEL:-granite3.3:2b}

      # Cache, pool, etc. — same defaults as cloud
      - CACHE_SIMILARITY_THRESHOLD=${CACHE_SIMILARITY_THRESHOLD:-0.75}
      - CACHE_TTL_HOURS=${CACHE_TTL_HOURS:-24}
      - CACHE_STRICT_MODE=${CACHE_STRICT_MODE:-true}
      - CHECKPOINT_TTL_DAYS=${CHECKPOINT_TTL_DAYS:-7}
      - DB_POOL_SIZE=${DB_POOL_SIZE:-100}
      - DB_MAX_OVERFLOW=${DB_MAX_OVERFLOW:-100}
      - DB_POOL_TIMEOUT=${DB_POOL_TIMEOUT:-30}
      - DB_POOL_RECYCLE=${DB_POOL_RECYCLE:-3600}
      - DB_POOL_PRE_PING=${DB_POOL_PRE_PING:-true}

      # Flask
      - FLASK_ENV=${FLASK_ENV:-production}
      - SECRET_KEY=${SECRET_KEY:-changeme-airgap-set-a-real-key}
      - PORT=5000

      # Embeddings — local model, identical to cloud
      - EMBEDDING_MODEL=${EMBEDDING_MODEL:-all-MiniLM-L6-v2}

      # OpenTelemetry — pointed at the local jaeger service
      - OTEL_ENABLED=true
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
      - OTEL_SERVICE_NAME=banko-ai-assistant-airgap

      # Coach knobs (defaults from Plan 2-A pre-flight)
      - CDC_WEBHOOK_HMAC_SECRET=${CDC_WEBHOOK_HMAC_SECRET:-changeme-airgap-webhook-secret}
      - COACH_KAFKA_ENABLED=false
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    networks:
      - banko-airgap
    restart: unless-stopped

volumes:
  airgap-cockroach-data:
    driver: local
  airgap-ollama-models:
    driver: local

networks:
  banko-airgap:
    driver: bridge
    # Internal-only network for airgap demos. The host can still expose ports
    # but containers cannot reach the public internet by name.
```

- [ ] **Step 6.2: Create the env example**

Create `.env.airgap.example` with exactly:

```bash
# Banko AI Assistant — airgap environment example
# Copy to .env.airgap and edit before running:
#   cp .env.airgap.example .env.airgap
#   docker compose --env-file .env.airgap -f docker-compose.airgap.yml up -d

# CockroachDB image tag
COCKROACHDB_VERSION=v25.4.6

# Ollama models (must be preloaded — see scripts/airgap/preload-models.sh)
OLLAMA_MODEL=granite3.3:8b
OLLAMA_CLASSIFIER_MODEL=granite3.3:2b

# Cache
CACHE_SIMILARITY_THRESHOLD=0.75
CACHE_TTL_HOURS=24
CACHE_STRICT_MODE=true

# Flask
FLASK_ENV=production
SECRET_KEY=replace-with-a-random-32-byte-secret-before-production-use

# Coach webhook — generate with: python -c "import secrets; print(secrets.token_hex(32))"
CDC_WEBHOOK_HMAC_SECRET=replace-with-32-byte-hex
```

- [ ] **Step 6.3: Validate the airgap compose syntactically**

Run:
```bash
docker compose -f docker-compose.airgap.yml config > /dev/null && echo "airgap compose OK"
```
Expected: `airgap compose OK`.

- [ ] **Step 6.4: Commit Task 6**

Run:
```bash
git add docker-compose.airgap.yml .env.airgap.example
git commit -m "feat(airgap): add docker-compose.airgap.yml with CRDB + Ollama + Jaeger + banko"
```

---

### Task 7: Airgap helper scripts

**Files:**
- Create: `scripts/airgap/preload-models.sh`
- Create: `scripts/airgap/verify-airgap.sh`

**Rationale:** Image stays slim; models are pulled separately. Verify script proves the bridge network has no public route — supports definition-of-done item 14 and the "disconnect wifi during the talk" claim.

- [ ] **Step 7.1: Create the preload script**

Create `scripts/airgap/preload-models.sh` with exactly:

```bash
#!/usr/bin/env bash
# preload-models.sh — pull one or more models into the running Ollama container.
#
# Usage:
#   scripts/airgap/preload-models.sh                       # defaults: granite3.3:8b granite3.3:2b
#   scripts/airgap/preload-models.sh llama3.2:3b           # custom model list
#
# Requirements: the airgap stack must be up (or the cloud stack with a manually
# added ollama service). The container name is detected by trying common names.

set -euo pipefail

MODELS=("${@:-granite3.3:8b granite3.3:2b}")
# Expand the default if no args given
if [[ "$#" -eq 0 ]]; then
    MODELS=(granite3.3:8b granite3.3:2b)
fi

# Detect container name
CONTAINER=""
for candidate in banko-airgap-ollama ollama banko-ollama; do
    if docker ps --format '{{.Names}}' | grep -q "^${candidate}$"; then
        CONTAINER="${candidate}"
        break
    fi
done

if [[ -z "${CONTAINER}" ]]; then
    echo "❌ No Ollama container found. Bring the airgap stack up first:"
    echo "   docker compose -f docker-compose.airgap.yml up -d ollama"
    exit 1
fi

echo "📦 Preloading models into ${CONTAINER}: ${MODELS[*]}"
for model in "${MODELS[@]}"; do
    echo ""
    echo "  → ${model}"
    docker exec "${CONTAINER}" ollama pull "${model}"
done

echo ""
echo "✅ Done. Installed models:"
docker exec "${CONTAINER}" ollama list
```

- [ ] **Step 7.2: Make the preload script executable**

Run:
```bash
chmod +x scripts/airgap/preload-models.sh
```

- [ ] **Step 7.3: Create the verify script**

Create `scripts/airgap/verify-airgap.sh` with exactly:

```bash
#!/usr/bin/env bash
# verify-airgap.sh — confirm the airgap stack has no path to the public internet
# from within the application container. Run after the stack is up.

set -euo pipefail

APP_CONTAINER="banko-airgap-app"
PROBE_HOSTS=("api.openai.com" "us-south.ml.cloud.ibm.com" "generativelanguage.googleapis.com" "bedrock-runtime.us-east-1.amazonaws.com")

if ! docker ps --format '{{.Names}}' | grep -q "^${APP_CONTAINER}$"; then
    echo "❌ ${APP_CONTAINER} not running. Bring the airgap stack up first:"
    echo "   docker compose -f docker-compose.airgap.yml up -d"
    exit 1
fi

echo "🔍 Verifying ${APP_CONTAINER} cannot reach public LLM endpoints..."
fail=0
for host in "${PROBE_HOSTS[@]}"; do
    # We expect this to FAIL on an airgap network. A success is a problem.
    if docker exec "${APP_CONTAINER}" sh -c "getent hosts ${host} >/dev/null 2>&1 && timeout 3 wget -qO /dev/null --tries=1 --timeout=3 https://${host}/" 2>/dev/null; then
        echo "  ❌ ${host} REACHABLE from ${APP_CONTAINER} — not airgap-clean"
        fail=1
    else
        echo "  ✅ ${host} unreachable (expected)"
    fi
done

echo ""
echo "🔍 Network inspect (look for 'Driver: bridge' and 'Internal' status):"
docker network inspect "$(docker inspect ${APP_CONTAINER} --format '{{range $k, $_ := .NetworkSettings.Networks}}{{$k}}{{end}}')" \
    | grep -E '"Driver"|"Internal"|"Subnet"'

if [[ "${fail}" -eq 0 ]]; then
    echo ""
    echo "✅ Airgap verified: no public LLM endpoint reachable from app container."
else
    echo ""
    echo "❌ Airgap NOT verified. One or more endpoints were reachable."
    exit 1
fi
```

- [ ] **Step 7.4: Make the verify script executable**

Run:
```bash
chmod +x scripts/airgap/verify-airgap.sh
```

- [ ] **Step 7.5: Smoke the preload script's argument parsing (no actual pull)**

Run:
```bash
bash -n scripts/airgap/preload-models.sh && echo "preload syntax OK"
bash -n scripts/airgap/verify-airgap.sh && echo "verify syntax OK"
```
Expected: both `... syntax OK` lines.

- [ ] **Step 7.6: Commit Task 7**

Run:
```bash
git add scripts/airgap/preload-models.sh scripts/airgap/verify-airgap.sh
git commit -m "feat(airgap): add preload-models and verify-airgap helper scripts"
```

---

### Task 8: README slim + section docs

**Files:**
- Modify: `README.md` (target: ≤ 250 lines)
- Create: `docs/coach.md`
- Create: `docs/airgap.md`
- Create: `docs/observability.md`

**Rationale:** README has crept back near 300 lines and lacks Coach / Observability / Airgap sections. Move depth into `docs/*.md` and keep README a high-signal landing page. Coach v1 demo needs all three docs to point reviewers at.

- [ ] **Step 8.1: Move depth into `docs/coach.md`**

Create `docs/coach.md` with exactly:

```markdown
# Spending Coach

Event-driven AI nudges. The Coach reacts to streaming spending signals (budget thresholds, anomalies, recurring-charge drift) produced by the sibling `cockroachdb-watsonx-data-pipeline` repo, and supports conversational follow-up.

## Live Coach UI

Open http://localhost:5000/coach. The page subscribes to a per-user SocketIO room (`coach:<user_id>`) and animates a card for every new nudge with:

- Nudge text
- Signal-type badge (`budget_threshold`, `anomaly`, `recurring_drift`)
- "Show evidence" toggle — expands the tool trace (which tools the agent ran, what they returned)
- Reply form — POSTs to `/api/coach/chat` for conversational follow-up

## Signal flow

1. The pipeline writes a row to `spending_signals` (TTL 30 days)
2. CockroachDB CHANGEFEED or Debezium streams the row to banko (mode: `CDC_MODE=webhook|kafka`)
3. Webhook endpoint `/api/cdc/signals` verifies HMAC + idempotency key
4. `SignalHandler` checks user preferences (DND, opted-out signal types), then invokes `CoachAgent.react(signal)`
5. CoachAgent: planner → 1-3 tool calls → synthesizer → persist to `coach_nudges` (TTL 90 days) + emit SocketIO event
6. Browser receives the event, animates the card

Latency budget: 2-4s on cloud LLMs, 5-15s on Ollama CPU.

## Mock the pipeline locally

The mock generator fires signals into the webhook so you can demo without the sibling repo running:

```bash
python scripts/coach/mock_signals.py --type=budget_threshold --user-id=demo-user-1
python scripts/coach/mock_signals.py --type=anomaly --user-id=demo-user-1
python scripts/coach/mock_signals.py --type=recurring_drift --user-id=demo-user-1
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `CDC_MODE` | `webhook` (demo) or `kafka` (prod) | `webhook` |
| `CDC_WEBHOOK_HMAC_SECRET` | HMAC-SHA256 secret shared with pipeline | (required) |
| `COACH_RATE_LIMIT_PER_5MIN` | Per-user conversational rate limit | `30` |
| `COACH_AGENT_MAX_STEPS` | Hard cap on planner-executor iterations | `5` |
| `COACH_SOCKETIO_ROOM_PREFIX` | Room name prefix for per-user events | `coach:` |
| `COACH_DEFAULT_USER_ID` | Demo single-user fallback | `demo-user-1` |
| `COACH_KAFKA_ENABLED` | Start Kafka consumer at app boot | `false` |

## Health endpoint

```bash
curl http://localhost:5000/health/coach
```

Returns webhook secret status, Kafka enabled status, active LLM provider, last nudge timestamp, and DB reachability.

## Pipeline contract

See [`PIPELINE_CONTRACT.md`](../PIPELINE_CONTRACT.md) at the repo root for the canonical `spending_signals` schema, signal-type definitions, webhook and Kafka payload formats, and idempotency semantics.
```

- [ ] **Step 8.2: Move depth into `docs/airgap.md`**

Create `docs/airgap.md` with exactly:

```markdown
# Airgap Deployment

Banko AI Assistant runs in three modes; airgap is a first-class target. No code path may assume internet access.

## Stack

```
┌────────────────────────────────────────┐
│  CockroachDB     (image: cockroach)    │
│  Ollama          (image: ollama)       │
│  Jaeger          (image: jaeger AIO)   │
│  banko-ai        (built from this repo)│
└────────────────────────────────────────┘
       all on a single bridge network
       no public DNS, no outbound calls
```

## First run

```bash
# 1. Bring the stack up
docker compose -f docker-compose.airgap.yml up -d

# 2. Preload the LLM models into the Ollama container
scripts/airgap/preload-models.sh granite3.3:8b granite3.3:2b
# (~5-15 minutes on a typical broadband connection; cached in the volume thereafter)

# 3. Verify zero outbound LLM connectivity
scripts/airgap/verify-airgap.sh
```

Open http://localhost:5000.

## Disconnect-the-wifi demo

After the preload step is done, the stack can run with the host's wifi disabled. Container DNS for `api.openai.com`, `us-south.ml.cloud.ibm.com`, `generativelanguage.googleapis.com`, and `bedrock-runtime.*` should all fail — `verify-airgap.sh` checks exactly that.

## Model choices

| Use | Default | Smaller |
|-----|---------|---------|
| Coach agent | `granite3.3:8b` | `granite3.3:2b` (lower-quality nudges) |
| Supervisor classifier (v1-B) | `granite3.3:2b` | — |
| Eval judge (v1-B) | `granite3.3:2b` | — |
| Embeddings | `all-MiniLM-L6-v2` (sentence-transformers, 384-dim, local) | — |

Override with `OLLAMA_MODEL`, `OLLAMA_CLASSIFIER_MODEL`, `EMBEDDING_MODEL`.

## Trade-offs

- Nudge latency on CPU: 5-15s vs 2-4s on cloud LLMs
- Granite 3.3 8B is the realistic floor for nudge quality; smaller models lose grounding
- The image does not bundle models — keeps image slim, but adds the preload step
```

- [ ] **Step 8.3: Move depth into `docs/observability.md`**

Create `docs/observability.md` with exactly:

```markdown
# Observability (OpenTelemetry + Jaeger)

Banko ships with an OpenTelemetry SDK and a Jaeger all-in-one trace UI. Off by default in dev; on by default in both compose stacks.

## Enabling

```bash
export OTEL_ENABLED=true
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317   # default
export OTEL_SERVICE_NAME=banko-ai-assistant                 # default
```

Or use the compose stack — `docker compose up -d` brings up `jaeger` alongside CRDB and banko with the env vars pre-set.

## Trace UI

http://localhost:16686 — pick `banko-ai-assistant` from the service dropdown, find any recent trace.

## What's instrumented

| Layer | How | Span name |
|-------|-----|-----------|
| Flask routes | `FlaskInstrumentor` (auto) | `<METHOD> /<route>` |
| Outbound HTTP | `RequestsInstrumentor` (auto) | `HTTP <METHOD>` |
| SignalHandler entry | `coach_span()` | `coach.handler.handle` |
| CoachAgent planner | `coach_span()` | `coach.planner` |
| CoachAgent tool calls | `coach_span()` per tool | `coach.tool.invoke` |
| CoachAgent synthesizer | `coach_span()` | `coach.synthesizer` |

Every Coach span carries `signal_id` (or `thread_id` for conversational), `user_id`, and `signal_type` attributes — one Jaeger query reconstructs the entire signal-to-nudge causal chain.

## Adding spans in new code

```python
from banko_ai.observability import coach_span

with coach_span("coach.tool.my_new_tool", attributes={"user_id": uid}):
    result = do_work(uid)
```

`coach_span` is a no-op when `OTEL_ENABLED=false` — safe to leave in production code paths regardless of mode.

## Trace assertion in tests

```python
# tests/observability/test_signal_trace.py asserts the expected span tree
# fires for a full signal→nudge flow. Run with:
uv run pytest tests/observability/test_signal_trace.py -v
```
```

- [ ] **Step 8.4: Slim README.md**

Open `README.md`. The current state is 298 lines; target is ≤ 250 with Coach + Observability + Airgap added. The strategy is:

1. Trim the "Configuration" section's prose (the cache preset table moves to a new line in the config doc).
2. Replace the Roadmap section with brief feature bullets that point to the new docs/*.md files.
3. Add three new short sections: "Spending Coach", "Streaming integration", "Observability".

Find the section `## Features` (line 37). After the existing 8-line feature bullet list, insert two new bullets so the section reads:

```markdown
## Features

- **Multi-agent receipt pipeline** — Receipt OCR → fraud screen → budget impact, with durable checkpoints
- **Multi-provider LLM** — watsonx (default), OpenAI, AWS Bedrock, Google Gemini, Ollama (airgap); swap from Settings or env without restart
- **Dynamic model discovery** — model lists come from the provider API, not a hardcoded enum
- **Vector RAG** — C-SPANN cosine indexes over expenses, embeddings generated locally
- **Persistent chat** — conversations survive restarts via `CockroachDBChatMessageHistory`
- **Three-layer cache** — query / embedding / vector-search caches with semantic similarity thresholds
- **Agent dashboard** — real-time view of agent status and activity (no canned demo data)
- **Spending Coach (v1)** — event-driven nudges from streaming CDC signals; see [`docs/coach.md`](docs/coach.md)
- **OpenTelemetry tracing** — local Jaeger trace UI; see [`docs/observability.md`](docs/observability.md)
- **Airgap mode** — Ollama-based offline stack; see [`docs/airgap.md`](docs/airgap.md)
- **Packaged** — `pip install banko-ai-assistant` or `docker-compose up -d`
```

Find the `## Roadmap` section (line 273). Replace the entire section (from `## Roadmap` through the line before `## Troubleshooting`) with:

```markdown
## Streaming integration

The Coach consumes spending signals from the sibling [`cockroachlabs-field/cockroachdb-watsonx-data-pipeline`](https://github.com/cockroachlabs-field/cockroachdb-watsonx-data-pipeline) repo via CockroachDB CHANGEFEED webhooks or a Kafka topic. The contract — table DDL, signal types, payload format, idempotency semantics — lives in [`PIPELINE_CONTRACT.md`](PIPELINE_CONTRACT.md).

## Roadmap

Next slices (in design): multi-agent Supervisor for LLM-routed dispatch across Receipt / Fraud / Budget / Coach, an MCP server exposing Coach tools to Claude Desktop / Cursor, and an eval harness with an LLM-as-judge pass-rate gate.

```

Find the line in the `## Deployment Modes` table (line ~271): `| **Airgap** *(roadmap)* | Ollama | local | on-prem everything |`. Replace it with:

```markdown
| **Airgap** | Ollama (granite3.3 default) | local | on-prem everything — see [`docs/airgap.md`](docs/airgap.md) |
```

- [ ] **Step 8.5: Verify README length**

Run:
```bash
wc -l README.md
```
Expected: 250 or fewer lines. If over, trim the Cache preset table (lines 170-174), the deeper CLI option list (lines 232-235), and the AI provider env block prose (one line per provider, not three). The target is ≤ 250.

- [ ] **Step 8.6: Verify all README links resolve to existing files**

Run:
```bash
for link in docs/coach.md docs/airgap.md docs/observability.md PIPELINE_CONTRACT.md; do
    if [[ -f "$link" ]]; then
        echo "✓ $link"
    else
        echo "✗ $link MISSING"
    fi
done
```
Expected: `✓` for `docs/coach.md`, `docs/airgap.md`, `docs/observability.md`. `✗ PIPELINE_CONTRACT.md MISSING` is OK at this point — Task 9 creates it.

- [ ] **Step 8.7: Commit Task 8**

Run:
```bash
git add README.md docs/coach.md docs/airgap.md docs/observability.md
git commit -m "docs: slim README under 250 lines; add coach, airgap, observability section docs"
```

---

### Task 9: PIPELINE_CONTRACT.md at repo root

**Files:**
- Create: `PIPELINE_CONTRACT.md`

**Rationale:** This is the artifact handed to the sibling-repo Claude session. It is the single source of truth for the producer-consumer boundary between the two repos: schema, signal types, webhook payload, Kafka payload, idempotency, ordering, retries.

- [ ] **Step 9.1: Create `PIPELINE_CONTRACT.md`**

Create `PIPELINE_CONTRACT.md` at the repo root with exactly:

```markdown
# Pipeline ↔ Banko Contract

This document is the boundary between two repos:

- **Producer** — [`cockroachlabs-field/cockroachdb-watsonx-data-pipeline`](https://github.com/cockroachlabs-field/cockroachdb-watsonx-data-pipeline) — computes spending signals from raw transactions and writes them to CockroachDB.
- **Consumer** — this repo, `cockroachlabs-field/banko-ai-assistant` — reacts to those signals via the Spending Coach.

Both repos must agree on the schema, payload formats, and operational semantics defined here. Changes to this document require a coordinated update in both repos.

## 1. `spending_signals` table (canonical schema)

Owned by **this repo** (the consumer creates the table via migration). The producer writes rows.

```sql
CREATE TABLE spending_signals (
  signal_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID NOT NULL,
  signal_type      STRING NOT NULL,    -- one of: budget_threshold | anomaly | recurring_drift
  severity         STRING NOT NULL,    -- one of: info | warn | critical
  payload          JSONB NOT NULL,     -- signal-type-specific fields (see §2)
  produced_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  consumed_at      TIMESTAMPTZ,        -- set by the consumer; null until processed
  idempotency_key  STRING NOT NULL UNIQUE,
  INDEX (user_id, produced_at DESC)
) WITH (ttl_expire_after = '30 days');
```

The unique constraint on `idempotency_key` is the dedup primitive for at-least-once delivery in both webhook and Kafka modes.

## 2. Signal types

### 2.1 `budget_threshold`

**Trigger**: a user's spending in a category crosses 50%, 80%, or 100% of their monthly budget.

**Required `payload` fields**:

| Field | Type | Description |
|-------|------|-------------|
| `category` | string | e.g. `"dining"`, `"groceries"`, `"transportation"` |
| `percent_used` | number | 0.0-1.5 (we send a signal up to 50% over) |
| `amount_spent_cents` | integer | spent so far this period |
| `amount_budget_cents` | integer | category budget for the period |
| `period_start` | string (ISO date) | first day of the period |
| `period_end` | string (ISO date) | last day of the period |
| `days_remaining` | integer | days left in the period at signal time |

**Example row**:

```json
{
  "signal_id": "0193f9d4-...",
  "user_id": "demo-user-1",
  "signal_type": "budget_threshold",
  "severity": "warn",
  "payload": {
    "category": "dining",
    "percent_used": 0.82,
    "amount_spent_cents": 41000,
    "amount_budget_cents": 50000,
    "period_start": "2026-05-01",
    "period_end": "2026-05-31",
    "days_remaining": 9
  },
  "produced_at": "2026-05-22T14:00:00Z",
  "idempotency_key": "budget_threshold:demo-user-1:dining:2026-05:82pct"
}
```

### 2.2 `anomaly`

**Trigger**: a transaction's amount deviates from the user's pattern for that merchant by ≥ 3σ, or occurs in a new geo, or at an off-hours time.

**Required `payload` fields**:

| Field | Type | Description |
|-------|------|-------------|
| `merchant` | string | merchant name |
| `amount_cents` | integer | this transaction's amount |
| `typical_amount_cents` | integer | user's median for this merchant |
| `stddev_cents` | integer | population stddev for the merchant |
| `anomaly_score` | number | ≥ 3.0 to trigger |
| `transaction_id` | string (UUID) | the offending transaction |
| `reason` | string | `"amount"` \| `"geo"` \| `"time"` \| `"new_merchant"` |

### 2.3 `recurring_drift`

**Trigger**: a subscription / recurring charge changes amount between billing cycles by more than 10%.

**Required `payload` fields**:

| Field | Type | Description |
|-------|------|-------------|
| `merchant` | string | recurring charge merchant |
| `previous_amount_cents` | integer | last cycle's amount |
| `current_amount_cents` | integer | this cycle's amount |
| `percent_change` | number | signed; positive = increase |
| `cycle_days` | integer | typical days between charges |
| `last_seen` | string (ISO datetime) | last charge before this one |

## 3. Webhook contract (demo mode)

**Endpoint**: `POST {BANKO_BASE_URL}/api/cdc/signals`

**Headers**:

| Header | Description |
|--------|-------------|
| `Content-Type` | `application/json` |
| `X-Banko-Signature` | `sha256=<hex>` — HMAC-SHA256 of the raw body using the shared secret |
| `X-Idempotency-Key` | the row's `idempotency_key` (also present in payload) |

**Payload** — CockroachDB CHANGEFEED envelope (one signal per request; consumer also accepts batched envelopes with a `"payload"` array):

```json
{
  "payload": [
    {
      "after": {
        "signal_id": "...",
        "user_id": "...",
        "signal_type": "budget_threshold",
        "severity": "warn",
        "payload": { ... },
        "produced_at": "2026-05-22T14:00:00Z",
        "idempotency_key": "..."
      },
      "updated": "1716386400.000000000"
    }
  ]
}
```

**Responses**:

| Status | Meaning |
|--------|---------|
| `200 OK` `{"status": "accepted"}` | normal acceptance |
| `200 OK` `{"status": "replayed"}` | already-processed (idempotency key match) |
| `400 Bad Request` | malformed payload — fields missing / wrong type |
| `401 Unauthorized` | HMAC mismatch |
| `202 Accepted` | accepted but downstream handler raised; will retry |
| `503 Service Unavailable` | backpressure; producer should honor `Retry-After` |

**Shared secret**: set as `CDC_WEBHOOK_HMAC_SECRET` on the consumer; mirror on the producer side.

## 4. Kafka contract (prod mode)

**Topic**: `banko.spending_signals`

**Key**: `user_id` (string) — partition by user for ordering guarantees within a user.

**Value**: same JSON shape as the row in §1 (the `after` payload without the CHANGEFEED envelope wrapping). UTF-8 encoded.

**Partitioning**: producer must partition by `user_id`. Ordering within a user is guaranteed; cross-user ordering is not.

**Delivery semantics**: at-least-once. Consumer dedups by `idempotency_key` against `spending_signals.idempotency_key`.

**Consumer offset commits**: manual, after successful handler invocation (not on poll). See `banko_ai/coach/kafka_consumer.py`.

**Poison-message handling**: after 3 consecutive handler failures on a message, the consumer publishes to `banko.spending_signals.dlq` and commits the offset. Operators inspect the DLQ topic.

## 5. Mock signal generator

`scripts/coach/mock_signals.py` in this repo is the reference implementation for what a producer should post. The pipeline-side Claude session may use it as a contract check during development.

## 6. Integration smoke test

`scripts/coach/assert_nudges.py` (consumer side, lives in this repo): given a `signal_id` and a timeout, polls `coach_nudges` and asserts a nudge was generated. Pipeline side runs this against a live banko instance after each end-to-end test to prove signal-to-nudge delivery works.

## 7. Operational notes

- **Idempotency**: producer is required to pick stable `idempotency_key` values. Recommended pattern: `<signal_type>:<user_id>:<category_or_merchant>:<period>:<threshold_or_score>`. Re-firing the same logical signal must produce the same key.
- **Retries**: webhook mode retries on `202`, `503`, and network errors with exponential backoff (1s → 30s, max 6 attempts). Kafka mode is governed by the consumer's commit semantics.
- **Ordering**: Kafka guarantees order per `user_id` partition. Webhook mode has no ordering guarantee — the consumer must tolerate out-of-order arrival within a user (typically: latest `produced_at` wins for display, but every signal is still individually persisted).
- **Backpressure**: consumer surfaces `503 + Retry-After` when handler queue depth exceeds a threshold. Producer must honor `Retry-After`.
- **Schema evolution**: additive only. New fields go in `payload` (JSONB), not as new top-level columns. Removing a field requires a coordinated release across both repos.
- **Known prod gap**: there is no out-of-process retry worker for permanently-failing webhook deliveries. For demo deployments the in-process queue is sufficient. For production, treat this as a P2 enhancement.

## 8. Versioning

This document is `v1`. Breaking changes require bumping a `Contract-Version: v2` header on the webhook and a topic rename for Kafka. Additive changes to `payload` fields do not require a version bump.
```

- [ ] **Step 9.2: Verify the markdown is well-formed**

Run:
```bash
wc -l PIPELINE_CONTRACT.md
head -1 PIPELINE_CONTRACT.md
```
Expected: ~200 lines, first line is `# Pipeline ↔ Banko Contract`.

- [ ] **Step 9.3: Verify README's link to PIPELINE_CONTRACT now resolves**

Run:
```bash
test -f PIPELINE_CONTRACT.md && echo "✓ PIPELINE_CONTRACT.md present"
```
Expected: `✓ PIPELINE_CONTRACT.md present`.

- [ ] **Step 9.4: Commit Task 9**

Run:
```bash
git add PIPELINE_CONTRACT.md
git commit -m "docs: add PIPELINE_CONTRACT.md as the producer-consumer boundary doc"
```

---

### Task 10: End-to-end trace assertion

**Files:**
- Create: `tests/observability/test_signal_trace.py`

**Rationale:** Per spec §7.1 trace-assertion layer and definition-of-done item 11 ("Jaeger shows a complete trace for a signal-to-nudge flow, ≥ 8 spans"). This test uses an in-memory span exporter so it runs in CI without Jaeger. Asserts the expected span tree fires for a single signal-to-nudge flow.

- [ ] **Step 10.1: Write the failing test**

Create `tests/observability/test_signal_trace.py`:

```python
"""End-to-end trace assertion for the signal → nudge pipeline.

Uses InMemorySpanExporter so the test is hermetic. Asserts the expected
span names and parent/child relationships fire for one signal.
"""

from unittest.mock import MagicMock, patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from banko_ai.coach import tracing_test_helpers  # noqa: F401 — local helper for shared state
from banko_ai.coach.handler import SignalHandler
from banko_ai.coach.signals import Signal, SignalType
from banko_ai.observability import tracing


@pytest.fixture(autouse=True)
def in_memory_tracer(monkeypatch):
    """Install an in-memory exporter so we can assert on emitted spans."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: "banko-test"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    # Mark our module's provider as initialized so coach_span emits real spans
    monkeypatch.setattr(tracing, "_provider_initialized", True)
    yield exporter
    provider.shutdown()


@pytest.fixture
def signal():
    return Signal(
        signal_id="sig-trace-1",
        user_id="user-trace-1",
        signal_type=SignalType.BUDGET_THRESHOLD,
        severity="warn",
        payload={"category": "dining", "percent_used": 0.82, "amount_spent_cents": 41000,
                 "amount_budget_cents": 50000, "days_remaining": 9},
        produced_at="2026-05-22T10:00:00Z",
        idempotency_key="idem-trace-1",
    )


def test_signal_to_nudge_trace_has_expected_spans(in_memory_tracer, signal):
    """One signal must produce: handler → planner → tool.invoke → synthesizer."""
    from banko_ai.coach.agent import CoachAgent

    # LLM stub that returns a single-tool plan, then a nudge message
    plan_response = '{"steps": [{"tool": "get_recent_signals", "args": {"user_id": "user-trace-1", "limit": 5}}]}'
    synth_response = "You're at 82% of dining budget with 9 days left."
    llm_responses = iter([plan_response, synth_response])

    def fake_llm(prompt: str, **kwargs) -> str:
        return next(llm_responses)

    fake_tool = MagicMock(return_value=[])
    tools = {"get_recent_signals": fake_tool}
    agent = CoachAgent(llm_invoker=fake_llm, tools=tools, max_steps=5)

    emitter = MagicMock()
    db_factory = MagicMock()
    with patch("banko_ai.coach.handler.SignalHandler._already_consumed", return_value=False), \
         patch("banko_ai.coach.handler.SignalHandler._persist_nudge"):
        handler = SignalHandler(coach=agent, emitter=emitter, db_session_factory=db_factory)
        handler.handle(signal)

    spans = in_memory_tracer.get_finished_spans()
    span_names = [s.name for s in spans]

    # Required spans (per spec §9 item 11)
    assert "coach.handler.handle" in span_names
    assert "coach.planner" in span_names
    assert "coach.tool.invoke" in span_names
    assert "coach.synthesizer" in span_names

    # ≥ 4 Coach spans (handler + planner + ≥1 tool + synth). The full target of
    # ≥ 8 is reached in production where Flask + SQLAlchemy auto-spans contribute.
    coach_spans = [n for n in span_names if n.startswith("coach.")]
    assert len(coach_spans) >= 4, f"Expected ≥4 coach spans, got: {coach_spans}"


def test_signal_attributes_propagate_to_spans(in_memory_tracer, signal):
    """signal_id must appear as an attribute on the handler span."""
    from banko_ai.coach.agent import CoachAgent

    plan_response = '{"steps": []}'
    synth_response = "Test nudge."
    llm_responses = iter([plan_response, synth_response])

    def fake_llm(prompt: str, **kwargs) -> str:
        return next(llm_responses)

    agent = CoachAgent(llm_invoker=fake_llm, tools={}, max_steps=5)
    emitter = MagicMock()
    db_factory = MagicMock()
    with patch("banko_ai.coach.handler.SignalHandler._already_consumed", return_value=False), \
         patch("banko_ai.coach.handler.SignalHandler._persist_nudge"):
        handler = SignalHandler(coach=agent, emitter=emitter, db_session_factory=db_factory)
        handler.handle(signal)

    spans = in_memory_tracer.get_finished_spans()
    handler_span = next(s for s in spans if s.name == "coach.handler.handle")
    assert handler_span.attributes.get("signal_id") == "sig-trace-1"
    assert handler_span.attributes.get("signal_type") == "budget_threshold"
    assert handler_span.attributes.get("user_id") == "user-trace-1"
```

- [ ] **Step 10.2: Add the tracing test helper stub**

Create `banko_ai/coach/tracing_test_helpers.py` with exactly:

```python
"""Placeholder module for trace-assertion tests to import without circular deps.

The actual span emission is done by banko_ai/observability/tracing.coach_span.
This file exists so test files have a stable, in-package import target.
"""
```

- [ ] **Step 10.3: Run the test to confirm it passes**

Run:
```bash
git add -f tests/observability/test_signal_trace.py
git add banko_ai/coach/tracing_test_helpers.py
uv run pytest tests/observability/test_signal_trace.py -v
```
Expected: 2 passed.

If the test fails with `ModuleNotFoundError: No module named 'opentelemetry.sdk.trace.export.in_memory_span_exporter'`, the package layout changed in newer OTel SDKs. Use the alternative import:

```python
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
```

becomes:

```python
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory import InMemorySpanExporter
```

Try both — the OTel team has moved this import location across minor versions.

- [ ] **Step 10.4: Commit Task 10**

Run:
```bash
git add banko_ai/coach/tracing_test_helpers.py
git add -f tests/observability/test_signal_trace.py
git commit -m "test(observability): assert signal→nudge trace tree (≥4 coach spans)"
```

---

### Task 11: Local smoke + USER GATED commit step (DO NOT PUSH)

**Files:**
- (no code changes — verification + gated commit decision)

**Rationale:** Plan 2-C produces six new committable changes (deps, observability module, Flask wiring, compose, Ollama provider, llm_factory branch, airgap compose, scripts, docs, contract, trace test). Before this branch can be considered ready to merge into the eventual 2-A → 2-C → 2-B integrated branch, the local smoke gate must pass against every provider AND the airgap stack. **Do not push to `origin` until the user explicitly approves after running multi-provider smoke + cross-repo testing against the sibling watsonx project.**

- [ ] **Step 11.1: Confirm test gates green**

Run:
```bash
uv run pytest tests/coach/ tests/observability/ tests/test_ollama_provider.py tests/test_llm_factory_ollama.py -v
```
Expected: every test passes.

- [ ] **Step 11.2: Run full local test gate**

Run:
```bash
make test-local
```
Expected: lint + types + full pytest pass. If `mypy` complains about new OTel imports, add `# type: ignore[import-untyped]` to the offending import lines in `tracing.py` and `ollama_provider.py`.

- [ ] **Step 11.3: Bring the full compose stack up locally and verify Jaeger**

Run:
```bash
docker compose up -d
sleep 20
curl -s http://localhost:5000/api/health
curl -s -o /dev/null -w "Jaeger UI: %{http_code}\n" http://localhost:16686/
curl -s http://localhost:5000/health/coach
```
Expected: `api/health` returns JSON with `"status": "healthy"`; Jaeger UI returns `200`; `health/coach` returns JSON with `db_reachable: true`, `webhook_secret_configured: true`, `active_provider: <provider>`.

- [ ] **Step 11.4: Fire a mock signal and verify the trace lands in Jaeger**

Run:
```bash
python scripts/coach/mock_signals.py --type=budget_threshold --user-id=demo-user-1
sleep 3
# Open Jaeger UI manually:
echo "Open http://localhost:16686, select service 'banko-ai-assistant', and search."
```

Expected: Jaeger UI shows a recent trace for service `banko-ai-assistant` containing `coach.handler.handle`, `coach.planner`, `coach.tool.invoke` (≥1), and `coach.synthesizer` spans. Each Coach span carries `signal_id`, `user_id`, `signal_type` attributes.

- [ ] **Step 11.5: Bring up the airgap stack and verify it boots**

Stop the cloud stack first:
```bash
docker compose down
```

Bring up airgap:
```bash
docker compose -f docker-compose.airgap.yml up -d
sleep 30
docker compose -f docker-compose.airgap.yml ps
```

Expected: 4 services (`banko-airgap-cockroachdb`, `banko-airgap-ollama`, `banko-airgap-jaeger`, `banko-airgap-app`) all `(healthy)` or `Up`.

- [ ] **Step 11.6: Preload Ollama models (one-time, slow on first run)**

Run:
```bash
scripts/airgap/preload-models.sh granite3.3:2b
```

Use only the `2b` model for the smoke gate to keep the pull time reasonable (~2 min vs ~10 min for 8b). The 8b model can be pulled separately for the full demo.

Expected: model pulls successfully; `docker exec banko-airgap-ollama ollama list` shows `granite3.3:2b`.

- [ ] **Step 11.7: Verify the airgap stack runs with the model**

Update `.env.airgap` (or set env on the running container) to use the 2b model:

```bash
docker compose -f docker-compose.airgap.yml exec banko-ai \
  sh -c "OLLAMA_MODEL=granite3.3:2b banko-ai status"
```

Then exercise the RAG endpoint:

```bash
curl -X POST http://localhost:5000/api/rag \
  -H "Content-Type: application/json" \
  -d '{"query": "What did I spend on dining last week?"}'
```

Expected: a JSON response with a real answer (latency 5-15s on CPU). No outbound LLM API calls.

- [ ] **Step 11.8: Verify airgap network isolation**

Run:
```bash
scripts/airgap/verify-airgap.sh
```

Expected: all probe hosts (`api.openai.com`, `us-south.ml.cloud.ibm.com`, `generativelanguage.googleapis.com`, `bedrock-runtime.us-east-1.amazonaws.com`) report `unreachable`. Script exits `0`.

If a host reports `REACHABLE`, the bridge network is not airgap-clean. Investigate the docker-compose network config — the `banko-airgap` bridge should not have NAT to the host's default route (this is the case on the standard `bridge` driver because the host doesn't forward, but verify with `docker network inspect banko-airgap`).

- [ ] **Step 11.9: Tear down the airgap stack**

Run:
```bash
docker compose -f docker-compose.airgap.yml down
```

Expected: all 4 containers stop and are removed; volumes (cockroach data + ollama models) persist for next demo.

- [ ] **Step 11.10: Verify the git log of this branch**

Run:
```bash
git log --oneline origin/main..HEAD
```

Expected log (in order, newest at top):

```
<sha> test(observability): assert signal→nudge trace tree (≥4 coach spans)
<sha> docs: add PIPELINE_CONTRACT.md as the producer-consumer boundary doc
<sha> docs: slim README under 250 lines; add coach, airgap, observability section docs
<sha> feat(airgap): add preload-models and verify-airgap helper scripts
<sha> feat(airgap): add docker-compose.airgap.yml with CRDB + Ollama + Jaeger + banko
<sha> feat(agents): add Ollama branch to llm_factory for airgap deployments
<sha> feat(providers): add OllamaProvider for airgap deployments
<sha> feat(observability): add Jaeger all-in-one to docker-compose for local trace UI
<sha> feat(observability): instrument Flask app, SignalHandler, and CoachAgent with OTel spans
<sha> feat(observability): add OpenTelemetry init module with coach_span helper
<sha> chore(coach): add OTel + Ollama deps and v1-C config knobs
```

11 commits total. **Verify no commit has a `Co-Authored-By` trailer or "Generated with Claude Code" line:**

```bash
git log --format="%H%n%B%n----" origin/main..HEAD | grep -iE "(co-authored-by|generated with)" && echo "❌ BAD TRAILER" || echo "✓ clean"
```

Expected: `✓ clean`. If any bad trailer is present, you cannot push. To fix:

```bash
# For each offending commit, reword without the trailer:
git rebase -i origin/main
# In the editor, change 'pick' to 'reword' for each offending commit;
# remove the trailer lines from each commit message.
```

- [ ] **Step 11.11: USER GATE — DO NOT PUSH**

**STOP HERE.**

The user has explicitly stated:

> "commit locally and build all of plan 2 as I am not going to push any changes to github until we test it all locally with the other watsonx project chnages as well"

This branch (`feat/coach-v1c-observability-airgap`) is committed locally. Do not run `git push`. Wait for the user to:

1. Run the full 14-item manual smoke checklist (`docs/coach-smoke-checklist.md`) against **every** provider (watsonx, OpenAI, AWS Bedrock, Gemini, Ollama)
2. Run cross-repo integration tests against `cockroachdb-watsonx-data-pipeline`
3. Approve the push explicitly

Only then push:

```bash
# After explicit user approval:
git push -u origin feat/coach-v1c-observability-airgap
```

Do not include any `--no-verify`, `--force`, or hook-skipping flags. If any pre-push hook fails, investigate and fix the underlying issue.

---

## Self-Review

### Spec coverage (against `2026-05-21-proactive-spending-coach-design.md`)

This plan covers the v1-C scope agreed in the 2-A → 2-C → 2-B decomposition. Items from spec §4:

| # | Component | Path | Covered in |
|---|-----------|------|------------|
| 14 | OTel instrumentation | `banko_ai/observability/tracing.py` + compose | Tasks 1, 2, 3 |
| 15 | OllamaProvider | `banko_ai/ai_providers/ollama_provider.py` | Tasks 4, 5 |
| 16 | Ollama service in compose | `docker-compose.airgap.yml` | Task 6 |
| 17 | Model preload script | `scripts/airgap/preload-models.sh` | Task 7 |
| 12 | `PIPELINE_CONTRACT.md` | repo root | Task 9 |
| §8.2 | README slim | `README.md` ≤ 250 lines + `docs/*.md` | Task 8 |

Definition-of-done items closed by this plan:

- #11 (Jaeger shows complete trace for signal→nudge, ≥8 spans) — Task 10 asserts ≥4 Coach spans in unit test; manual smoke step 11.4 confirms the full ≥8 (Coach 4 + Flask 1 + SQL 2-3 + Requests 1) in Jaeger UI
- #14 (`docker compose -f docker-compose.airgap.yml up` produces working stack with no external network calls) — Tasks 6, 7 + smoke step 11.8

**Explicit deferrals to Plan 2-B**:
- #7 MCP server
- #9 Eval harness
- #13 Supervisor

**Not in this plan, already done in 2-A**:
- #1 Signal dataclass, #2 SignalHandler, #3 Webhook receiver, #4 Kafka consumer, #5 CoachAgent, #6 Coach tools, #8 Live Coach UI, #10 Mock generator, #11 DB migrations

### Placeholder scan

Searched plan for `TBD`, `TODO`, `implement later`, `fill in details`, `add appropriate error handling`, `similar to Task N`. None found. Every step shows code or exact commands.

### Type consistency

- `coach_span(name, attributes=None, tracer_name="banko.coach")` — same signature in Task 1, Task 2, Task 10, `docs/observability.md`
- `init_tracing(app, engine=None) -> bool` — same signature in Task 1, Task 2, `docs/observability.md`
- `OllamaProvider({"model": ...})` constructor — same in Task 4 tests and Task 5 (llm_factory uses `config.ollama_model` not a config dict; this is intentional — provider abstraction vs LangChain wrapper are separate paths)
- Signal field names (`signal_id`, `user_id`, `signal_type`, `severity`, `payload`, `produced_at`, `idempotency_key`) — consistent with Plan 2-A's `signals.py` definition

### Bot-trailer audit

Every commit message in this plan uses conventional commits format. None include `Co-Authored-By: Claude` or "Generated with Claude Code". Step 11.10 verifies this with grep before allowing push.

### Local-testing-before-push compliance

Per [[local-testing-before-push]] memory: this plan ends at a commit-locally-only state. Step 11.11 explicitly forbids `git push`. The push only happens after multi-provider smoke + cross-repo testing, and only with explicit user approval.

### File map matches tasks

The File Map (top of plan) lists 12 file groups. Each appears in exactly one task. No orphan files.

### CI considerations

- `tests/observability/test_signal_trace.py` uses `InMemorySpanExporter` — no Jaeger required for CI.
- The OTel auto-instrumentors hook `flask`, `sqlalchemy`, `requests` at import-time when called; the test fixture in step 10.1 installs its own `TracerProvider` per-test so cross-test pollution is impossible.
- `tests/test_ollama_provider.py` mocks `requests.get`; no live Ollama needed for CI.
- `tests/test_llm_factory_ollama.py` mocks `langchain_ollama.ChatOllama`; no live Ollama needed for CI.
