"""Mock signal generator — fires a synthetic spending signal at the local
webhook receiver. Used by the manual smoke checklist and by anyone
demoing without the sibling pipeline repo running.

Usage:
    python scripts/coach/mock_signals.py --type=budget_threshold
    python scripts/coach/mock_signals.py --type=anomaly --user-id=<uuid>
    python scripts/coach/mock_signals.py --type=recurring_drift --count=3

Auth: reads CDC_WEBHOOK_HMAC_SECRET from env (same as the receiver).
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


DEFAULT_URL = "http://localhost:5000/api/cdc/signals"
DEFAULT_USER = os.getenv("COACH_DEFAULT_USER_ID",
                          "00000000-0000-0000-0000-000000000001")


def _payload_for(signal_type: str) -> dict[str, Any]:
    if signal_type == "budget_threshold":
        return {"category": "dining", "pct_used": 0.82,
                "monthly_budget": 400.0, "spent_so_far": 328.0,
                "days_remaining": 9}
    if signal_type == "anomaly":
        return {"merchant": "Uber", "amount": 850.0,
                "expected_max": 75.0, "z_score": 4.2,
                "transaction_id": str(uuid.uuid4())}
    if signal_type == "recurring_drift":
        return {"subscription": "Netflix", "old_amount": 15.99,
                "new_amount": 22.99, "pct_change": 0.44,
                "merchant_id": str(uuid.uuid4())}
    raise SystemExit(f"unknown signal_type: {signal_type}")


def _build_envelope(signal_type: str, user_id: str,
                    idem: str) -> dict[str, Any]:
    return {"payload": [{
        "after": {
            "signal_id": str(uuid.uuid4()),
            "user_id": user_id,
            "signal_type": signal_type,
            "severity": "warn" if signal_type == "budget_threshold"
                       else "critical" if signal_type == "anomaly"
                       else "info",
            "payload": _payload_for(signal_type),
            "idempotency_key": idem,
        },
        "updated": f"{time.time():.10f}"
    }]}


def _sign(body: bytes) -> str:
    secret = os.getenv("CDC_WEBHOOK_HMAC_SECRET", "")
    if not secret:
        raise SystemExit(
            "CDC_WEBHOOK_HMAC_SECRET not set. Export it before running:\n"
            "  export CDC_WEBHOOK_HMAC_SECRET='your-secret'"
        )
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--type", required=True,
                        choices=["budget_threshold", "anomaly",
                                 "recurring_drift"])
    parser.add_argument("--user-id", default=DEFAULT_USER)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--count", type=int, default=1,
                        help="Send N signals back-to-back (unique idem keys)")
    parser.add_argument("--idempotency-key",
                        help="Override idempotency key (useful for dedup testing)")
    args = parser.parse_args()

    for i in range(args.count):
        idem = args.idempotency_key or f"mock-{args.type}-{uuid.uuid4()}"
        envelope = _build_envelope(args.type, args.user_id, idem)
        body = json.dumps(envelope).encode()
        headers = {
            "Content-Type": "application/json",
            "X-Banko-Signature": _sign(body),
            "X-Idempotency-Key": idem,
        }
        resp = requests.post(args.url, data=body, headers=headers, timeout=10)
        print(f"[{i+1}/{args.count}] {args.type} -> "
              f"{resp.status_code} {resp.text[:200]}")
        if resp.status_code >= 400:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
