# Follow-up Plan: Receipt Validation + Dynamic Model Discovery

> **Status:** Local, uncommitted. Discovered during 2026-05-21 multi-provider smoke of the Pre-flight Housekeeping branch.
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close two pre-existing bugs surfaced by the watsonx smoke run: (1) the receipt OCR path INSERTs unvalidated LLM output and 500s on placeholder data; (2) provider model lists are hardcoded and stale (`ibm/granite-3-8b-instruct` disappeared from IBM's env without our list noticing).

**Architecture:** Two independent fixes on a single branch `chore/receipt-validation-and-dynamic-models`. Task 1 adds a Pydantic schema between LLM extraction and DB INSERT. Task 2 swaps the hardcoded watsonx list for a one-shot discovery call cached at startup, applies the same pattern to other providers where the SDK supports it, and falls back to a stub list only on discovery failure.

**Tech Stack:** Pydantic v2 (already in tree via langchain), `ibm_watsonx_ai.foundation_models.utils.get_model_specs()`, `openai.models.list()`, `google.cloud.aiplatform`'s model registry, AWS Bedrock `list_foundation_models`.

---

## Repro for Task 1 (date parsing 500)

1. Switch `WATSONX_MODEL` to `ibm/granite-8b-code-instruct` (or any non-instruct model).
2. Upload any receipt PDF via the UI.
3. Observe LLM response:
   ```json
   {"merchant": "store name", "amount": 0.00, "date": "YYYY-MM-DD", ...}
   ```
4. Observe `psycopg2.errors.InvalidDatetimeFormat: could not parse "YYYY-MM-DD"` and HTTP 500.

The LLM echoed the prompt template instead of extracting — `app.py:715` should never have tried to INSERT this.

## Repro for Task 2 (stale model list)

1. Open the UI settings page, watsonx provider.
2. Dropdown lists `ibm/granite-3-8b-instruct`.
3. Pick it.
4. Any request fails:
   ```
   WMLClientError: Model 'ibm/granite-3-8b-instruct' is not supported for this
   environment. Supported models: [<long actual list from IBM>]
   ```

The dropdown is from `banko_ai/config/settings.py:155-209`, hardcoded at module-load time. IBM's actual supported list is whatever `get_model_specs()` returns at request time.

---

### Task 1: Validate receipt OCR output before persistence

**Files:**
- Create: `banko_ai/agents/receipt_extraction_schema.py`
- Modify: `banko_ai/web/app.py` (the receipt upload handler — find the block around line 700-720 that builds the INSERT)
- Create: `tests/test_receipt_extraction_schema.py`

- [ ] **Step 1.1: Write the failing test for the schema**

Create `tests/test_receipt_extraction_schema.py`:

```python
"""Tests for the ReceiptExtraction Pydantic schema that gates LLM output
before it reaches the DB."""
import datetime

import pytest
from pydantic import ValidationError

from banko_ai.agents.receipt_extraction_schema import (
    ReceiptExtraction,
    is_placeholder_payload,
)


def test_valid_extraction_parses():
    rx = ReceiptExtraction(
        merchant="Whole Foods Market",
        amount=42.17,
        date=datetime.date(2026, 5, 21),
        category="food",
        items=["organic bananas", "almond milk"],
        payment_method="credit card",
    )
    assert rx.amount == 42.17
    assert rx.date.year == 2026


def test_placeholder_date_rejected():
    """The 'YYYY-MM-DD' placeholder from prompt templates must not slip past."""
    with pytest.raises(ValidationError):
        ReceiptExtraction(
            merchant="store",
            amount=10.0,
            date="YYYY-MM-DD",  # placeholder string
            category="food",
            items=["item1"],
            payment_method="credit card",
        )


def test_zero_amount_rejected():
    """Receipts with $0.00 are almost certainly extraction failures."""
    with pytest.raises(ValidationError):
        ReceiptExtraction(
            merchant="store",
            amount=0.0,
            date=datetime.date(2026, 5, 21),
            category="food",
            items=["item1"],
            payment_method="credit card",
        )


def test_placeholder_merchant_rejected_by_helper():
    """is_placeholder_payload() catches the wider 'whole-response-is-template'
    case where every field looks like prompt scaffolding."""
    payload = {
        "merchant": "store name",
        "amount": 0.0,
        "date": "YYYY-MM-DD",
        "category": "food or transportation or entertainment or shopping or services or other",
        "items": ["item1", "item2"],
        "payment_method": "credit card or debit card or cash or other",
    }
    assert is_placeholder_payload(payload) is True


def test_real_payload_not_flagged_as_placeholder():
    payload = {
        "merchant": "Whole Foods",
        "amount": 42.17,
        "date": "2026-05-21",
        "category": "food",
        "items": ["bananas"],
        "payment_method": "credit card",
    }
    assert is_placeholder_payload(payload) is False
```

- [ ] **Step 1.2: Run the test to verify it fails**

```bash
uv run pytest tests/test_receipt_extraction_schema.py -v
```
Expected: collection error (module doesn't exist yet).

- [ ] **Step 1.3: Create the schema module**

Create `banko_ai/agents/receipt_extraction_schema.py`:

```python
"""Validation layer for LLM-extracted receipt fields.

Sits between the receipt agent's LLM response and any DB persistence.
Catches the common failure mode where a code-tuned or otherwise unsuitable
model echoes the prompt template back instead of extracting real values.
"""
from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

_PLACEHOLDER_DATE_STRINGS = frozenset({"YYYY-MM-DD", "yyyy-mm-dd", "2024-01-01"})
_PLACEHOLDER_MERCHANTS = frozenset({"store name", "merchant", "store", "unknown"})
_PLACEHOLDER_CATEGORY_FRAGMENTS = ("or transportation or", "category1", "categoryname")
_PLACEHOLDER_PAYMENT_FRAGMENTS = ("or debit card or cash or", "paymentmethod")
_PLACEHOLDER_ITEMS = frozenset({"item1", "item2", "itemname"})


class ReceiptExtraction(BaseModel):
    merchant: str = Field(min_length=1)
    amount: float = Field(gt=0)
    date: datetime.date
    category: str = Field(min_length=1)
    items: list[str] = Field(min_length=1)
    payment_method: str = Field(min_length=1)

    @field_validator("date", mode="before")
    @classmethod
    def reject_placeholder_date(cls, v: Any) -> Any:
        if isinstance(v, str) and v in _PLACEHOLDER_DATE_STRINGS:
            raise ValueError(f"date {v!r} is a prompt-template placeholder")
        return v

    @field_validator("merchant")
    @classmethod
    def reject_placeholder_merchant(cls, v: str) -> str:
        if v.strip().lower() in _PLACEHOLDER_MERCHANTS:
            raise ValueError(f"merchant {v!r} is a prompt-template placeholder")
        return v


def is_placeholder_payload(payload: dict[str, Any]) -> bool:
    """Heuristic: does this whole payload look like the LLM regurgitated the
    prompt scaffold? True if multiple fields match placeholder signatures.
    Cheaper than catching ValidationError and lets the caller log a single
    clean diagnostic instead of a stack trace per field."""
    hits = 0
    if str(payload.get("date", "")).strip() in _PLACEHOLDER_DATE_STRINGS:
        hits += 1
    if str(payload.get("merchant", "")).strip().lower() in _PLACEHOLDER_MERCHANTS:
        hits += 1
    cat = str(payload.get("category", "")).lower()
    if any(f in cat for f in _PLACEHOLDER_CATEGORY_FRAGMENTS):
        hits += 1
    pm = str(payload.get("payment_method", "")).lower()
    if any(f in pm for f in _PLACEHOLDER_PAYMENT_FRAGMENTS):
        hits += 1
    items = payload.get("items") or []
    if isinstance(items, list) and any(
        str(i).strip().lower() in _PLACEHOLDER_ITEMS for i in items
    ):
        hits += 1
    return hits >= 2
```

- [ ] **Step 1.4: Run the test to verify it passes**

```bash
uv run pytest tests/test_receipt_extraction_schema.py -v
```
Expected: 5 PASS.

- [ ] **Step 1.5: Wire the schema into the receipt upload handler**

In `banko_ai/web/app.py`, find the receipt upload handler (search for the INSERT into `expenses` near line 715). Before the INSERT, parse the LLM's extracted fields through `ReceiptExtraction` and short-circuit on failure:

```python
from banko_ai.agents.receipt_extraction_schema import (
    ReceiptExtraction,
    is_placeholder_payload,
)

# ... after the LLM returns `extracted_fields` dict, BEFORE the INSERT:

if is_placeholder_payload(extracted_fields):
    return jsonify({
        "success": False,
        "error": "Receipt extraction failed: the model returned prompt-template "
                 "placeholders instead of real values. Try switching to a more "
                 "capable instruction-tuned model.",
        "extracted": extracted_fields,
    }), 422

try:
    validated = ReceiptExtraction(**extracted_fields)
except ValidationError as e:
    return jsonify({
        "success": False,
        "error": f"Receipt extraction validation failed: {e.errors()}",
        "extracted": extracted_fields,
    }), 422

# Then use validated.date, validated.amount, etc. in the INSERT instead of
# raw dict lookups.
```

(Adjust the exact integration to match the surrounding handler — read the actual lines 690-730 of `app.py` to confirm the variable names and response format.)

- [ ] **Step 1.6: Smoke the integrated path**

Manual smoke (no automated integration test possible without a live model):
1. Switch `WATSONX_MODEL=ibm/granite-8b-code-instruct`.
2. Upload a receipt.
3. Expected: HTTP 422 with the helpful error message, NOT 500 + stack trace.
4. Switch to `WATSONX_MODEL=meta-llama/llama-3-3-70b-instruct`.
5. Upload same receipt.
6. Expected: 200, expense row inserted with real values.

- [ ] **Step 1.7: Commit**

```bash
git add banko_ai/agents/receipt_extraction_schema.py banko_ai/web/app.py
git add -f tests/test_receipt_extraction_schema.py
git commit -m "$(cat <<'EOF'
fix: validate receipt OCR output before persisting

The receipt upload handler INSERTed whatever JSON the LLM returned,
which 500s with InvalidDatetimeFormat when the model echoes prompt
placeholders ("date": "YYYY-MM-DD") instead of extracting. Adds a
Pydantic ReceiptExtraction schema (date must parse, amount > 0,
merchant != "store name") and a cheap is_placeholder_payload()
pre-check, returning HTTP 422 with a useful error before touching
the DB. Triggered by ibm/granite-8b-code-instruct during the
2026-05-21 watsonx smoke; same defense protects any future
model/prompt mismatch.
EOF
)"
```

---

### Task 2: Dynamic model discovery (watsonx first, others if cheap)

**Files:**
- Modify: `banko_ai/ai_providers/watsonx_provider.py` (add `list_models()` if not present)
- Modify: `banko_ai/config/settings.py` (remove the hardcoded `available_models` dict for watsonx; replace with a lazy call to the provider abstraction)
- Modify: `banko_ai/web/app.py` (the `/api/models` route — read from the provider abstraction)
- Create: `tests/test_dynamic_model_discovery.py`

**Rationale:** `memory/project_provider_abstraction_invariant.md` already forbids direct SDK imports outside `ai_providers/`. The hardcoded list in `settings.py` is the same anti-pattern in dropdown form — it assumes a static set of supported models that IBM has just disproven. Move the source of truth to the provider, cache at process start, and fall back to a frozen stub only when discovery fails.

- [ ] **Step 2.1: Verify the current list_models surface**

```bash
grep -n "def list_models\|def available_models\|get_model_specs\|ModelInference" banko_ai/ai_providers/watsonx_provider.py
```

If `list_models()` already exists, skip 2.2 and use it. If not, add it.

- [ ] **Step 2.2: Add list_models() to WatsonxProvider**

In `banko_ai/ai_providers/watsonx_provider.py`, add:

```python
from functools import lru_cache

@lru_cache(maxsize=1)
def list_models(self) -> list[str]:
    """Return the model IDs that the current watsonx environment actually
    supports. Cached for the lifetime of the provider instance — IBM
    changes the list rarely, and a fresh process pick up changes."""
    from ibm_watsonx_ai.foundation_models import get_model_specs

    try:
        specs = get_model_specs(url=self._watsonx_url, api_key=self._api_key)
        return sorted({s["model_id"] for s in specs if "model_id" in s})
    except Exception as e:
        # Fall back to a tiny safe stub. Logged so operators see they're
        # in degraded mode.
        print(f"⚠️ watsonx list_models failed ({e}); using fallback stub")
        return [
            "meta-llama/llama-3-3-70b-instruct",
            "mistralai/mistral-small-3-1-24b-instruct-2503",
            "ibm/granite-3-1-8b-base",
        ]
```

(Adjust `self._watsonx_url` / `self._api_key` to whatever the existing provider stores.)

- [ ] **Step 2.3: Add a base-class hook + replace settings.py hardcoding**

In `banko_ai/ai_providers/base.py` (or wherever `AIProvider` lives), declare an abstract `list_models() -> list[str]`. Provide a stub default in providers that don't yet have discovery (returns the same stub list they hardcoded before, but as a single source of truth).

In `banko_ai/config/settings.py`, find the `available_models` dict (~line 155-209) and replace usages with a call to `get_ai_provider().list_models()` at the request site. Delete the dict body but leave a one-line stub returning `{}` if any code still imports the name (then file a follow-up to remove that too).

- [ ] **Step 2.4: Write the test**

Create `tests/test_dynamic_model_discovery.py`:

```python
"""Verify each provider exposes list_models() and that the watsonx
implementation handles SDK failure by returning a non-empty fallback."""
import pytest

from banko_ai.ai_providers.watsonx_provider import WatsonxProvider


def test_watsonx_list_models_fallback_on_sdk_error(monkeypatch):
    """If get_model_specs raises, list_models must still return a
    non-empty stub so the UI dropdown isn't blank."""
    def _boom(*a, **kw):
        raise RuntimeError("simulated SDK failure")

    monkeypatch.setattr(
        "ibm_watsonx_ai.foundation_models.get_model_specs",
        _boom,
    )
    provider = WatsonxProvider(api_key="fake", url="https://fake")
    models = provider.list_models()
    assert isinstance(models, list)
    assert len(models) > 0
    assert all(isinstance(m, str) for m in models)


def test_all_providers_implement_list_models():
    """The abstraction contract: every concrete provider can answer
    'what can I run?'."""
    from banko_ai.ai_providers import (
        WatsonxProvider, OpenAIProvider, AWSProvider, GeminiProvider,
    )
    for cls in (WatsonxProvider, OpenAIProvider, AWSProvider, GeminiProvider):
        assert hasattr(cls, "list_models"), f"{cls.__name__} missing list_models()"
```

- [ ] **Step 2.5: Run the test**

```bash
uv run pytest tests/test_dynamic_model_discovery.py -v
```
Expected: both PASS. If the second fails because some provider lacks `list_models`, add a stub for that provider before continuing.

- [ ] **Step 2.6: Manual UI smoke**

1. Restart the app.
2. Open Settings → watsonx.
3. Expected: dropdown populated from IBM's live list (no `ibm/granite-3-8b-instruct`).
4. Pick `meta-llama/llama-3-3-70b-instruct`.
5. Receipt upload works end to end (combined with Task 1 fix).

- [ ] **Step 2.7: Commit**

```bash
git add banko_ai/ai_providers/watsonx_provider.py banko_ai/ai_providers/base.py banko_ai/config/settings.py banko_ai/web/app.py
git add -f tests/test_dynamic_model_discovery.py
git commit -m "$(cat <<'EOF'
fix: replace hardcoded watsonx model list with dynamic discovery

settings.py shipped a frozen list of watsonx models that IBM has
since culled — `ibm/granite-3-8b-instruct` disappeared from the
environment without notice, but the UI still offered it and every
request 500s with WMLClientError. Moves the source of truth into
WatsonxProvider.list_models(), backed by ibm_watsonx_ai.get_model_specs()
with an lru_cache and a safe fallback stub. settings.py keeps a thin
shim for backward compat. Same provider-abstraction pattern stubbed
for openai/aws/gemini for follow-up.
EOF
)"
```

---

## Self-review checklist (post-write)

1. **Spec coverage**: Both Task 1 (validation) and Task 2 (dynamic discovery) trace back to today's repro. ✓
2. **Placeholder scan**: No TBDs except deliberate "adjust to match surrounding handler" notes in Step 1.5 and 2.2-2.3 — those are flagged for the implementer to verify against actual file state. ✓
3. **Type consistency**: `ReceiptExtraction` and `is_placeholder_payload` are defined in Task 1 Step 1.3 and used unchanged in Step 1.5. `list_models` signature is the same across base class, provider, and test. ✓

## Notes

- Both tasks are independent — Task 2 doesn't depend on Task 1 and vice versa. Implement in either order, or in parallel branches if convenient.
- The placeholder-detection denylists in Task 1 are intentionally conservative; expand if/when new prompt templates leak through.
- Task 2's `lru_cache` means a `kill -HUP` (or process restart) is needed to pick up an IBM-side change to the supported list. That's the right trade — the alternative is a network round-trip per UI page load.
