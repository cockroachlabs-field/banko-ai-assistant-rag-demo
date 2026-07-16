"""Automated end to end smoke for the Coach signal path.

Fires one signal of each type, then polls coach_nudges until a nudge exists
for every fired signal (or times out). Exit code 0 on success, 1 on failure,
so it can gate a push or run in a demo preflight.

Two ways to fire:
  --via webhook   POST HMAC-signed changefeed envelopes at /api/cdc/signals
                  (needs CDC_WEBHOOK_HMAC_SECRET, same as the app)
  --via sql       INSERT rows into spending_signals and let the real CDC
                  pipeline deliver them (needs the cdc-demo stack up and the
                  app running with COACH_KAFKA_ENABLED=true)

Both need DATABASE_URL to check results.

Usage:
    uv run python scripts/coach/assert_nudges.py
    uv run python scripts/coach/assert_nudges.py --via sql --timeout 120
"""

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from typing import Any

import requests
from sqlalchemy import create_engine, text

DEFAULT_URL = "http://localhost:5000/api/cdc/signals"
DEFAULT_USER = os.getenv("COACH_DEFAULT_USER_ID",
                         "00000000-0000-0000-0000-000000000001")

PAYLOADS: dict[str, tuple[str, dict[str, Any]]] = {
    "budget_threshold": ("warn", {
        "category": "dining", "pct_used": 0.82, "monthly_budget": 400.0,
        "spent_so_far": 328.0, "days_remaining": 9}),
    "anomaly": ("critical", {
        "merchant": "Uber", "amount": 850.0, "expected_max": 75.0,
        "z_score": 4.2, "transaction_id": str(uuid.uuid4())}),
    "recurring_drift": ("info", {
        "subscription": "Netflix", "old_amount": 15.99, "new_amount": 22.99,
        "pct_change": 0.44, "merchant_id": str(uuid.uuid4())}),
}


def _fire_webhook(url: str, user_id: str) -> list[str]:
    secret = os.getenv("CDC_WEBHOOK_HMAC_SECRET", "")
    if not secret:
        sys.exit("CDC_WEBHOOK_HMAC_SECRET not set")
    signal_ids = []
    for sig_type, (severity, payload) in PAYLOADS.items():
        signal_id = str(uuid.uuid4())
        envelope = {"payload": [{
            "after": {
                "signal_id": signal_id,
                "user_id": user_id,
                "signal_type": sig_type,
                "severity": severity,
                "payload": payload,
                "idempotency_key": f"assert:{uuid.uuid4()}",
            },
            "updated": f"{time.time():.10f}",
        }]}
        body = json.dumps(envelope).encode()
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        r = requests.post(url, data=body, timeout=30, headers={
            "Content-Type": "application/json",
            "X-Banko-Signature": sig})
        if r.status_code not in (200, 202):
            sys.exit(f"webhook rejected {sig_type}: {r.status_code} {r.text[:200]}")
        signal_ids.append(signal_id)
        print(f"fired {sig_type} via webhook -> {r.status_code}")
    return signal_ids


def _fire_sql(db_url: str, user_id: str) -> list[str]:
    eng = create_engine(db_url)
    signal_ids = []
    with eng.begin() as conn:
        for sig_type, (severity, payload) in PAYLOADS.items():
            signal_id = str(uuid.uuid4())
            conn.execute(text("""
                INSERT INTO spending_signals
                  (signal_id, user_id, signal_type, severity, payload,
                   idempotency_key)
                VALUES (:sid, :u, :t, :sev, CAST(:p AS JSONB), :idem)
            """), {"sid": signal_id, "u": user_id, "t": sig_type,
                   "sev": severity, "p": json.dumps(payload),
                   "idem": f"assert:{uuid.uuid4()}"})
            signal_ids.append(signal_id)
            print(f"inserted {sig_type} row -> {signal_id[:8]}")
    eng.dispose()
    return signal_ids


def _await_nudges(db_url: str, signal_ids: list[str], timeout: int) -> bool:
    eng = create_engine(db_url)
    deadline = time.time() + timeout
    found: dict[str, str] = {}
    while time.time() < deadline and len(found) < len(signal_ids):
        with eng.connect() as conn:
            rows = conn.execute(text("""
                SELECT signal_id::STRING, provider_used, left(message, 90)
                FROM coach_nudges
                WHERE signal_id::STRING = ANY(:ids)
            """), {"ids": signal_ids}).fetchall()
        for sid, provider, msg in rows:
            if sid not in found:
                found[sid] = provider
                print(f"nudge for {sid[:8]} [{provider}]: {msg}...")
        if len(found) < len(signal_ids):
            time.sleep(3)
    eng.dispose()
    missing = [s for s in signal_ids if s not in found]
    for m in missing:
        print(f"NO NUDGE for signal {m}")
    return not missing


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--via", choices=["webhook", "sql"], default="webhook")
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--user-id", default=DEFAULT_USER)
    ap.add_argument("--timeout", type=int, default=90,
                    help="seconds to wait for all nudges")
    args = ap.parse_args()

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        sys.exit("DATABASE_URL not set")

    if args.via == "webhook":
        signal_ids = _fire_webhook(args.url, args.user_id)
    else:
        signal_ids = _fire_sql(db_url, args.user_id)

    ok = _await_nudges(db_url, signal_ids, args.timeout)
    print("PASS: all signals produced nudges" if ok
          else "FAIL: missing nudges, see above")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
