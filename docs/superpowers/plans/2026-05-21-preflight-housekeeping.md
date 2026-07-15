# Pre-flight Housekeeping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land all open dependabot updates, fix the one real SQL-identifier interpolation in `agent_schema.py`, harden `SECRET_KEY` handling, add a `Makefile` baseline, and correct CLAUDE.md's "Open bugs" section against verified reality — so the Coach / Ollama / OTel plans that follow start from a clean tree.

**Architecture:** Six focused tasks landing as separate commits on a single branch `chore/preflight-housekeeping`. Tasks 1-2 are documentation/tooling (no behavioral change). Task 3 fixes the SQL-identifier interpolation with a whitelist + safe quoting and adds a regression test. Task 4 hardens the production-mode `SECRET_KEY` path with a startup warning when running under gunicorn with no env-provided secret. Task 5 is the dependabot batch: bump `pyproject.toml` upper bounds + run `uv lock --upgrade`, lint, type-check, and unit-test the result. Task 6 is the gated multi-provider smoke (human-driven) and final push — explicit gate because none of the prior tasks are allowed to touch `origin/main` until this passes per [[local-testing-before-push]].

**Tech stack:** Python 3.10+, `uv` package manager, `pytest` / `ruff` / `mypy`, CockroachDB 25.4.0+ local single-node for integration tests, `gh` CLI for PR management.

---

## File Map

| Task | Files | Action |
|------|-------|--------|
| 1 | `Makefile` | Create |
| 2 | `CLAUDE.md` | Modify (lines 125-131) |
| 3 | `banko_ai/utils/agent_schema.py`, `tests/test_agent_schema_drop.py` | Modify line 266; create test |
| 4 | `banko_ai/web/app.py`, `banko_ai/config/settings.py` | Modify |
| 5 | `pyproject.toml`, `uv.lock`, `.github/workflows/release.yml` | Modify |
| 6 | (none — verification + push) | n/a |

---

## Pre-flight: branch and baseline

- [ ] **Step P.1: Confirm clean working tree and current branch**

Run:
```bash
git status
git branch --show-current
```
Expected: working tree clean (or only `docs/superpowers/` untracked), current branch is `main`.

If not clean, stop and reconcile before proceeding.

- [ ] **Step P.2: Create housekeeping branch off local main**

Run:
```bash
git fetch origin
git checkout -b chore/preflight-housekeeping
```
Expected: switched to a new branch `chore/preflight-housekeeping` starting from current HEAD (local `main`, which is ahead of `origin/main` by one docs commit; the eventual PR will carry that docs commit forward as well).

- [ ] **Step P.3: Verify CockroachDB is running locally**

Run:
```bash
cockroach sql --insecure --execute "SELECT version();"
```
Expected: a single row showing `CockroachDB CCL v25.4.0` or higher.

If not running, start it:
```bash
cockroach start-single-node --insecure --store=./cockroach-data \
  --listen-addr=localhost:26257 --http-addr=localhost:8080 --background
```

---

### Task 1: Add Makefile baseline

**Files:**
- Create: `Makefile`

**Rationale:** CLAUDE.md references `make test-local` but no `Makefile` exists. Every subsequent plan (Ollama, OTel, Coach) will want a single command for "run everything CI runs." Define it now.

- [ ] **Step 1.1: Create the Makefile**

Create `Makefile` with exactly this content:

```makefile
.PHONY: test test-local lint types fmt clean help

help:
	@echo "Targets:"
	@echo "  make test            - run full pytest suite"
	@echo "  make test-local      - lint + types + test (the gate before any push)"
	@echo "  make lint            - ruff check"
	@echo "  make types           - mypy"
	@echo "  make fmt             - ruff format"
	@echo "  make clean           - remove caches"

test:
	uv run pytest tests/ -v

test-local: lint types test
	@echo ""
	@echo "✓ Local test suite passed."
	@echo "  REMINDER: multi-provider smoke is still required before push."
	@echo "  See docs/coach-smoke-checklist.md once it exists, or run the app"
	@echo "  against each of watsonx, openai, aws, gemini, ollama manually."

lint:
	uv run ruff check banko_ai/ tests/

types:
	uv run mypy banko_ai/

fmt:
	uv run ruff format banko_ai/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache
```

- [ ] **Step 1.2: Verify each target parses**

Run:
```bash
make help
```
Expected: the help text printed above.

Run:
```bash
make lint
```
Expected: ruff completes; any lint errors are pre-existing and noted (do not fix in this task — Task 5 may resolve them via dep bumps).

- [ ] **Step 1.3: Commit**

```bash
git add Makefile
git commit -m "$(cat <<'EOF'
chore: add Makefile baseline (test/lint/types/fmt targets)

CLAUDE.md references make test-local; this provides the gate.
Subsequent plans (Ollama, OTel, Coach) will rely on it.
EOF
)"
```

---

### Task 2: Correct CLAUDE.md "Open bugs" section

**Files:**
- Modify: `CLAUDE.md` (lines 125-131, "Open bugs flagged but not yet fixed")

**Rationale:** Three of the five claims under "Open bugs" are wrong after a real audit:
- "4 SQL-injection f-strings in `agent_schema.py`" — only 1 exists (line 266).
- "Hardcoded Flask secret in `web/app.py`" — not hardcoded; `settings.py:216-217` falls back to `secrets.token_hex(32)`. The real concern is multi-worker gunicorn where each worker generates a different random secret, invalidating sessions across workers.
- The L2-vector cleanup language elsewhere in CLAUDE.md is fine (no remnants found), but the open-bugs list shouldn't perpetuate ghosts.

Document reality so future Claude sessions don't chase nonexistent bugs.

- [ ] **Step 2.1: Edit the Open bugs section**

In `CLAUDE.md`, replace the entire "Open bugs flagged but not yet fixed" section (currently lines 125-131) with:

```markdown
### Open bugs flagged but not yet fixed

- One unsafe SQL identifier interpolation at `banko_ai/utils/agent_schema.py:266` (`DROP TABLE IF EXISTS {table} CASCADE` — table comes from a hardcoded list, so not currently exploitable, but should be parameterized with a whitelist).
- Multi-worker `SECRET_KEY` drift: when `SECRET_KEY` env is unset and gunicorn forks multiple workers, each worker calls `secrets.token_hex(32)` independently, so Flask sessions break across workers. Single-process dev is fine. Fix: warn-and-fail at startup in prod mode if `SECRET_KEY` is unset.
- `agent_memory.access_count` never incremented on read (defer to memory-system v2).
- `SentenceTransformer` re-instantiated per call in `base_agent.py` (perf bug; fixing risks regression — defer).
- `documents` table schema drift between `database.py` and `agent_schema.py` (both create it; reconcile when next touching either).
```

- [ ] **Step 2.2: Verify the edit**

Run:
```bash
grep -A 6 "Open bugs flagged" CLAUDE.md
```
Expected: the new five-bullet list above.

- [ ] **Step 2.3: Commit**

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: correct CLAUDE.md "Open bugs" against actual code

The previous list overcounted SQL f-strings (1, not 4) and mischaracterized
the SECRET_KEY situation (it's a multi-worker drift bug, not a hardcoded
value). Tasks 3 and 4 fix what remains real.
EOF
)"
```

---

### Task 3: Fix SQL identifier interpolation in agent_schema.py

**Files:**
- Modify: `banko_ai/utils/agent_schema.py:259-272` (the `with engine.connect()` block inside the drop function)
- Create: `tests/test_agent_schema_drop.py`

**Rationale:** The drop loop interpolates `{table}` directly into a DDL statement. Today it's safe because `tables` is a hardcoded literal, but the pattern is fragile — any future maintainer copying it for user-provided input introduces a real injection. Replace with an explicit whitelist check + safe quoting via `sqlalchemy.sql.quoted_name`.

- [ ] **Step 3.1: Write the failing test**

Create `tests/test_agent_schema_drop.py` with:

```python
"""Regression test for agent_schema drop_agent_schema identifier safety."""
import pytest
from banko_ai.utils.agent_schema import _ALLOWED_DROP_TABLES, drop_agent_schema


def test_allowed_drop_tables_is_a_frozenset_of_known_names():
    """Whitelist must be immutable and contain the five agent tables."""
    assert isinstance(_ALLOWED_DROP_TABLES, frozenset)
    assert _ALLOWED_DROP_TABLES == frozenset({
        "documents",
        "agent_decisions",
        "agent_tasks",
        "agent_memory",
        "agent_state",
    })


def test_drop_agent_schema_requires_confirm():
    """Calling without confirm=True must be a no-op returning False."""
    assert drop_agent_schema("postgresql://nowhere/db", confirm=False) is False


def test_drop_agent_schema_rejects_unknown_table(monkeypatch):
    """If someone monkey-patches the table list with a hostile value, the call
    must refuse rather than interpolating arbitrary strings into DDL."""
    hostile = ["documents; DROP DATABASE defaultdb;--"]
    monkeypatch.setattr(
        "banko_ai.utils.agent_schema._tables_to_drop",
        lambda: hostile,
    )
    # We deliberately do not pass a real DB URL — the safety check should
    # fire before any connect attempt. Using a clearly-invalid URL would
    # raise on connect; the function must raise ValueError first.
    with pytest.raises(ValueError, match="not in the allowed drop set"):
        drop_agent_schema("postgresql://invalid/db", confirm=True)
```

- [ ] **Step 3.2: Run the test to verify it fails**

Run:
```bash
uv run pytest tests/test_agent_schema_drop.py -v
```
Expected: tests fail with `ImportError: cannot import name '_ALLOWED_DROP_TABLES'` and/or `AttributeError`.

- [ ] **Step 3.3: Implement the whitelist + safe quoting**

Open `banko_ai/utils/agent_schema.py`. At the top of the file, after the existing imports, add (or extend if already present) a `frozenset` constant and a helper:

```python
from sqlalchemy.sql import quoted_name

# Whitelist of tables that drop_agent_schema is allowed to drop.
# Adding to this list is a deliberate code change reviewed in PR.
_ALLOWED_DROP_TABLES: frozenset[str] = frozenset({
    "documents",
    "agent_decisions",
    "agent_tasks",
    "agent_memory",
    "agent_state",
})


def _tables_to_drop() -> list[str]:
    """Return the ordered list of tables to drop. Indirection exists so tests
    can monkeypatch and verify the safety check refuses unknown names."""
    # Reverse FK order matters: documents -> agent_decisions -> tasks/memory -> state
    return [
        "documents",
        "agent_decisions",
        "agent_tasks",
        "agent_memory",
        "agent_state",
    ]
```

Then replace the existing block at lines 259-272 (the `with engine.connect()` ... `engine.dispose()` section inside `drop_agent_schema`) with:

```python
        with engine.connect() as conn:
            tables = _tables_to_drop()

            # Defense-in-depth: even though the list is hardcoded, validate
            # every name against the whitelist before interpolating it into DDL.
            for table in tables:
                if table not in _ALLOWED_DROP_TABLES:
                    raise ValueError(
                        f"Refusing to drop {table!r}: not in the allowed drop set "
                        f"{sorted(_ALLOWED_DROP_TABLES)}"
                    )

            for table in tables:
                safe_name = quoted_name(table, quote=True)
                print(f"  Dropping table: {safe_name}")
                conn.execute(text(f"DROP TABLE IF EXISTS {safe_name} CASCADE"))

            conn.commit()

        engine.dispose()
```

(`quoted_name(table, quote=True)` produces a SQLAlchemy identifier that will be properly quoted by the dialect. Because the value originates from a checked whitelist, this is now defense-in-depth — both the whitelist and the safe-quoting must fail before bad SQL is possible.)

- [ ] **Step 3.4: Run the test to verify it passes**

Run:
```bash
uv run pytest tests/test_agent_schema_drop.py -v
```
Expected: all three tests pass.

- [ ] **Step 3.5: Run lint and type check on the touched file**

Run:
```bash
uv run ruff check banko_ai/utils/agent_schema.py tests/test_agent_schema_drop.py
uv run mypy banko_ai/utils/agent_schema.py
```
Expected: ruff clean; mypy clean (or no new errors compared to baseline).

- [ ] **Step 3.6: Commit**

```bash
git add banko_ai/utils/agent_schema.py tests/test_agent_schema_drop.py
git commit -m "$(cat <<'EOF'
fix: parameterize DROP TABLE in agent_schema with whitelist

agent_schema.py:266 interpolated table names directly into DDL. The list
was hardcoded so not exploitable today, but the pattern is fragile. Add
a frozenset whitelist, validate every name before interpolation, and use
sqlalchemy.sql.quoted_name for safe identifier quoting. Regression test
covers the whitelist refusal path.
EOF
)"
```

---

### Task 4: Harden SECRET_KEY for multi-worker production

**Files:**
- Modify: `banko_ai/config/settings.py` (around lines 216-217)
- Modify: `banko_ai/web/app.py` (around the SECRET_KEY assignment at line 204)

**Rationale:** Today, when `SECRET_KEY` env is unset, each gunicorn worker generates an independent `secrets.token_hex(32)`. Flask sessions then break across workers (a cookie signed by worker A fails verification on worker B). Single-process dev is fine and we want to keep that ergonomics. Fix: detect production mode (`FLASK_ENV=production` or running under gunicorn) and fail loudly at startup if `SECRET_KEY` is unset.

- [ ] **Step 4.1: Write the failing test**

Append to `tests/test_env_config.py` (existing file) — find a sensible place near other config tests and add:

```python
def test_settings_warns_in_prod_when_secret_key_missing(monkeypatch, caplog):
    """In prod-like environments (FLASK_ENV=production), an unset SECRET_KEY
    must raise a clear startup error rather than silently generating a
    per-worker random value."""
    import logging
    import pytest
    from banko_ai.config.settings import load_settings

    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("FLASK_ENV", "production")

    with pytest.raises(RuntimeError, match="SECRET_KEY must be set"):
        load_settings()


def test_settings_generates_random_secret_in_dev(monkeypatch):
    """In dev mode, missing SECRET_KEY falls back to random — same behavior
    as before; this test pins it so we don't regress dev ergonomics."""
    from banko_ai.config.settings import load_settings

    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)

    settings = load_settings()
    assert settings.secret_key
    assert len(settings.secret_key) >= 32
```

(If `load_settings` isn't the actual entry-point name, substitute the real function — it's the one called by `app.py` at startup. Read `banko_ai/config/settings.py:124` to confirm the function name before writing the test.)

- [ ] **Step 4.2: Run the test to verify it fails**

Run:
```bash
uv run pytest tests/test_env_config.py::test_settings_warns_in_prod_when_secret_key_missing -v
```
Expected: FAIL (no RuntimeError raised — current code silently generates a random secret).

- [ ] **Step 4.3: Update settings.py to fail loudly in prod**

In `banko_ai/config/settings.py`, find the existing block (currently at lines 215-217):

```python
        if not self.secret_key:
            self.secret_key = secrets.token_hex(32)
```

Replace with:

```python
        if not self.secret_key:
            flask_env = os.getenv("FLASK_ENV", "development").lower()
            running_under_gunicorn = "gunicorn" in os.getenv("SERVER_SOFTWARE", "").lower()
            if flask_env == "production" or running_under_gunicorn:
                raise RuntimeError(
                    "SECRET_KEY must be set in production. "
                    "Multi-worker deployments require a stable secret so Flask "
                    "session cookies validate across workers. Set SECRET_KEY in "
                    "the environment (e.g., `export SECRET_KEY=$(python -c "
                    "'import secrets; print(secrets.token_hex(32))')`)."
                )
            self.secret_key = secrets.token_hex(32)
```

- [ ] **Step 4.4: Run the test to verify it passes**

Run:
```bash
uv run pytest tests/test_env_config.py::test_settings_warns_in_prod_when_secret_key_missing \
              tests/test_env_config.py::test_settings_generates_random_secret_in_dev -v
```
Expected: both PASS.

- [ ] **Step 4.5: Run the full env_config suite to ensure no regressions**

Run:
```bash
uv run pytest tests/test_env_config.py -v
```
Expected: all tests pass (or pre-existing failures unchanged — note them).

- [ ] **Step 4.6: Commit**

```bash
git add banko_ai/config/settings.py tests/test_env_config.py
git commit -m "$(cat <<'EOF'
fix: require SECRET_KEY in production to prevent per-worker drift

When FLASK_ENV=production or running under gunicorn, an unset SECRET_KEY
now raises at startup instead of silently generating a per-worker random
value that breaks Flask sessions across workers. Dev mode keeps the
random-fallback ergonomics.
EOF
)"
```

---

### Task 5: Dependabot batch — bump everything in one branch

**Files:**
- Modify: `pyproject.toml` (gunicorn upper bound, sentence-transformers upper bound, langchain-core floor)
- Modify: `uv.lock` (regenerated)
- Modify: `.github/workflows/release.yml` (softprops/action-gh-release v2 → v3)

**Rationale:** 11 open dependabot PRs, 16+ open security alerts. Per the user's no-push-until-tested rule, we can't merge them one-by-one — each merge would require a separate multi-provider smoke. Instead, bump everything locally on this branch, run the full local gate, then push once. Superseded dependabot PRs will auto-close.

The target versions come from the open dependabot PRs at time of writing (2026-05-21):

| Package | Current floor | New floor (or upper) | Source |
|---------|---------------|----------------------|--------|
| `idna` | 3.11 (lock) | 3.15 (lock-only bump) | PR #50, security alert #109 |
| `langsmith` | 0.7.26 (lock) | 0.8.0 (lock-only bump) | PR #49, alerts #108, #98 |
| `langchain-classic` | 1.0.3 (lock) | 1.0.7 (lock-only bump) | PR #48, alert #107 |
| `urllib3` | >=2.6.3 (pyproject) | lock to 2.7.0 | PR #47, alerts #106, #105 |
| `gunicorn` | <24.0.0 (pyproject) | <27.0.0 (pyproject) | PR #46 |
| `langchain-core` | >=1.2.22 (pyproject) | >=1.3.3 (pyproject) | PR #45, alert #104 |
| `langchain-text-splitters` | (lock) | 1.1.2 | PR #44, alert #102 |
| `langchain-openai` | >=1.0.0 (pyproject) | lock to 1.1.14 | PR #43, alert #103 |
| `pypdf` | >=6.9.2 (pyproject) | lock to 6.10.2 | PR #42, alerts #101, #100, #99, #97, #96 |
| `sentence-transformers` | <4.0.0 (pyproject) | <6.0.0 (pyproject) | PR #39 |
| `softprops/action-gh-release` | v2 (workflow) | v3 (workflow) | PR #38 |

- [ ] **Step 5.1: Update pyproject.toml floors and upper bounds**

In `pyproject.toml`, make these exact edits:

Line 43 — relax `sentence-transformers` upper bound:
```
    "sentence-transformers>=3.1.0,<6.0.0",
```

Line 62 — raise `langchain-core` floor:
```
    "langchain-core>=1.3.3",
```

Line 81 — relax `gunicorn` upper bound:
```
    "gunicorn>=23.0.0,<27.0.0",
```

- [ ] **Step 5.2: Regenerate the lockfile against the new constraints**

Run:
```bash
uv lock --upgrade
```
Expected: `uv` resolves a new lockfile. If it errors with a conflict, read the error — it usually names two packages that disagree on a transitive. Resolve by relaxing one upper bound; do not pin tighter than necessary.

- [ ] **Step 5.3: Verify the upgraded versions are in the new lockfile**

Run:
```bash
for pkg in idna langsmith langchain-classic urllib3 gunicorn langchain-core langchain-text-splitters langchain-openai pypdf sentence-transformers; do
  echo -n "$pkg: "
  grep -A1 "name = \"$pkg\"" uv.lock | grep version | head -1
done
```
Expected: each package shows a version at or above the target in the table above. If any are below target, `uv lock --upgrade` couldn't reach them — re-check `pyproject.toml` bounds.

- [ ] **Step 5.4: Bump the GitHub Action**

Open `.github/workflows/release.yml`. Find the line referencing `softprops/action-gh-release@v2` (there should be exactly one) and change it to `@v3`.

Verify with:
```bash
grep -n "softprops/action-gh-release" .github/workflows/*.yml
```
Expected: a single match showing `@v3`.

- [ ] **Step 5.5: Sync the environment**

Run:
```bash
uv sync --all-extras
```
Expected: packages install successfully.

- [ ] **Step 5.6: Run lint, type check, and the full unit suite**

Run:
```bash
make lint
```
Expected: ruff completes. If new errors appear (e.g., from langchain-core 1.3 deprecating an import), fix them — those are real breakage we need to address.

Run:
```bash
make types
```
Expected: mypy completes. New errors from type changes in updated libs may need narrow fixes.

Run:
```bash
uv run pytest tests/ -v --ignore=tests/test_full_system.py
```
Expected: all unit + integration tests pass. (We exclude `test_full_system.py` here only if it depends on external network — re-include if it's local.)

If any test fails because an updated library changed behavior, fix the test or the calling code. Do not skip without a recorded reason.

- [ ] **Step 5.7: Commit**

```bash
git add pyproject.toml uv.lock .github/workflows/release.yml
git commit -m "$(cat <<'EOF'
chore(deps): batch bump for security advisories (11 dependabot PRs)

Bumps applied:
  idna 3.11 -> 3.15                     (alert #109)
  langsmith 0.7.26 -> 0.8.0             (alerts #108, #98)
  langchain-classic 1.0.3 -> 1.0.7      (alert #107)
  urllib3 -> 2.7.0                      (alerts #106, #105)
  gunicorn upper bound -> <27.0.0
  langchain-core 1.2.22 -> >=1.3.3      (alert #104)
  langchain-text-splitters -> 1.1.2     (alert #102)
  langchain-openai -> 1.1.14            (alert #103)
  pypdf -> 6.10.2                       (alerts #101, #100, #99, #97, #96)
  sentence-transformers upper bound -> <6.0.0
  softprops/action-gh-release v2 -> v3

Local gate: lint + types + pytest all pass. Multi-provider smoke pending
in Task 6.
EOF
)"
```

---

### Task 6: Multi-provider smoke and push gate

**Files:** none (verification + push)

**Rationale:** The user's strict rule: never push until tested locally against every relevant LLM provider. This task is a gated checklist. Skipping or short-circuiting it violates [[local-testing-before-push]].

- [ ] **Step 6.1: Pre-smoke sanity**

Run:
```bash
make test-local
```
Expected: all of lint, types, and pytest succeed. If this fails, do NOT proceed — return to whichever task introduced the failure.

- [ ] **Step 6.2: Start the app against watsonx**

In one terminal:
```bash
export AI_SERVICE="watsonx"
export WATSONX_API_KEY="..."          # use the user's real key
export WATSONX_PROJECT_ID="..."
export DATABASE_URL="cockroachdb://root@localhost:26257/defaultdb?sslmode=disable"
banko-ai run --port 5000
```

In another terminal, verify:
```bash
curl -s http://localhost:5000/api/health | jq .
curl -s -X POST http://localhost:5000/api/rag \
  -H "Content-Type: application/json" \
  -d '{"query":"What did I spend on dining last month?"}' | jq .
```
Expected: `/api/health` reports `db: ok, ai: ok`; `/api/rag` returns a coherent response naming a dollar amount and category. Note response time and any warnings in the app logs.

Stop the app (`Ctrl-C`) and record PASS or FAIL with one-line notes.

- [ ] **Step 6.3: Repeat the smoke against OpenAI**

```bash
export AI_SERVICE="openai"
export OPENAI_API_KEY="..."
banko-ai run --port 5000
```
Same two curl commands. Record PASS/FAIL.

- [ ] **Step 6.4: Repeat against AWS Bedrock**

```bash
export AI_SERVICE="aws"
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_REGION="us-east-1"
banko-ai run --port 5000
```
Same two curl commands. Record PASS/FAIL.

- [ ] **Step 6.5: Repeat against Google Gemini**

```bash
export AI_SERVICE="gemini"
# Either service-account path:
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/sa.json"
export GOOGLE_PROJECT_ID="..."
# Or API key:
# export GOOGLE_API_KEY="..."
banko-ai run --port 5000
```
Same two curl commands. Record PASS/FAIL.

(Ollama is not yet wired — that's Plan 2. Skip it here.)

- [ ] **Step 6.6: Receipt OCR sanity (one provider is enough)**

Pick any provider you've already verified above and exercise the agent pipeline end to end:

```bash
curl -X POST http://localhost:5000/api/upload-receipt -F "receipt=@tests/fixtures/sample_receipt.png"
```
Expected: returns a JSON receipt extraction + a follow-up agent decision (fraud screen + budget impact). If the fixture file doesn't exist at that path, use any receipt image — the point is to exercise `Receipt → Fraud → Budget` workflow under updated LangGraph/langchain libs.

- [ ] **Step 6.7: Gate check**

All four cloud providers must report PASS in Steps 6.2-6.5. The receipt pipeline must report PASS in Step 6.6. If any failed:
- Do not push.
- Investigate the failure (likely an updated library changed behavior).
- Add the fix as a new commit on this branch and re-run from Step 6.1.

- [ ] **Step 6.8: Push the branch and open a PR**

```bash
git push -u origin chore/preflight-housekeeping
gh pr create --title "chore: pre-flight housekeeping (deps batch + SQL fix + SECRET_KEY hardening)" \
  --body "$(cat <<'EOF'
## Summary

Pre-flight housekeeping in preparation for the Spending Coach work:

- Batched 11 open dependabot PRs / 16+ security advisories into one upgrade.
- Parameterized the one unsafe SQL identifier interpolation in `agent_schema.py` (whitelist + `sqlalchemy.sql.quoted_name`).
- Hardened `SECRET_KEY` handling so multi-worker prod fails loud instead of silently breaking sessions.
- Added a `Makefile` baseline.
- Corrected CLAUDE.md "Open bugs" against actual repo state.

## Test plan

- [x] `make test-local` (lint + types + pytest)
- [x] Multi-provider smoke: watsonx, OpenAI, AWS Bedrock, Gemini
- [x] Receipt OCR end-to-end (Receipt → Fraud → Budget)
- [ ] Reviewer eyeball on Makefile + the SECRET_KEY change

This PR supersedes:
  #50, #49, #48, #47, #46, #45, #44, #43, #42, #39, #38

Closes the corresponding dependabot security alerts: #109, #108, #107, #106, #105, #104, #103, #102, #101, #100, #99, #98, #97, #96.
EOF
)"
```

- [ ] **Step 6.9: Close superseded dependabot PRs**

After the PR is created, post a comment on each superseded dependabot PR pointing at our PR, then close it. The dependabot bot will recognize the merged commits and stop reopening:

```bash
PR_URL="$(gh pr view --json url -q .url)"
for n in 50 49 48 47 46 45 44 43 42 39 38; do
  gh pr comment "$n" --body "Superseded by $PR_URL (batched upgrade)."
  gh pr close "$n"
done
```

Expected: each command prints success. Re-check with `gh pr list --author "app/dependabot"` — list should be empty (or only show PRs opened after the batch).

- [ ] **Step 6.10: Done — leave the PR for review/merge**

The user reviews and merges the PR through GitHub's UI. We do not self-merge.

---

## Self-Review (run before handing the plan off)

- **Spec coverage:** Plan 1 covers the spec's §8 (housekeeping) plus the dependabot batch and the corrected open-bugs list. It does NOT cover Coach, Ollama, OTel, Supervisor, MCP, or Eval — those are Plans 2-7.
- **Placeholder scan:** No "TBD" or "implement later." Every code change shows the actual code. Every command shows expected output.
- **Type consistency:** `_ALLOWED_DROP_TABLES` and `_tables_to_drop()` are introduced in Task 3 and referenced in the same task. `load_settings` in Task 4 is referenced as the entry-point — Step 4.1 instructs verification before writing the test (because the exact name was not confirmed during plan-writing).
- **Branch hygiene:** All work lands on `chore/preflight-housekeeping`. Six commits. Push is gated behind Task 6's multi-provider smoke.
- **Reversibility:** Every commit is independent and revertable. The dependabot batch is the largest blast radius — if it breaks production behavior the Task 6 smoke catches it before push.
