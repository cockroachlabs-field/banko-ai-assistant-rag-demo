"""Tests for AWSProvider.get_available_models() — Bedrock Legacy filtering
and fallback when the AWS API is unreachable.

Background: on 2026-05-22 the AWS smoke surfaced
`ResourceNotFoundException("This Model is marked by provider as Legacy and
you have not been actively using the model in the last 30 days. Please
upgrade to an active model on Amazon Bedrock")` against Claude 3.x
inference profiles. Bedrock's `list_inference_profiles` API still reports
those profiles as lifecycle=ACTIVE, so we have to filter them by ID
pattern. This test pins both the filter and the strengthened fallback so
the dropdown can never quietly regress to Claude 3.x defaults.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from banko_ai.ai_providers.aws_provider import AWSProvider


@pytest.fixture
def provider(monkeypatch):
    """An AWSProvider whose Bedrock client is never actually built — the
    discovery path mocks boto3.client directly, so __init__ just needs to
    finish without trying to authenticate."""
    monkeypatch.delenv("AWS_MODELS", raising=False)
    p = AWSProvider({
        "access_key_id": "fake-key",
        "secret_access_key": "fake-secret",
        "region": "us-east-1",
        "model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    })
    return p


def test_dynamic_discovery_filters_legacy_claude_3(provider):
    """Live Bedrock returns Claude 3.x as lifecycle=ACTIVE even when the
    account would get a Legacy denial on invocation. The filter must drop
    them from the dropdown so operators don't get a runtime
    ResourceNotFoundException."""
    fake_bedrock = MagicMock()
    fake_bedrock.list_foundation_models.return_value = {"modelSummaries": []}
    fake_bedrock.list_inference_profiles.return_value = {
        "inferenceProfileSummaries": [
            {"inferenceProfileId": "us.anthropic.claude-3-sonnet-20240229-v1:0",
             "status": "ACTIVE"},
            {"inferenceProfileId": "us.anthropic.claude-3-haiku-20240307-v1:0",
             "status": "ACTIVE"},
            {"inferenceProfileId": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
             "status": "ACTIVE"},
            {"inferenceProfileId": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
             "status": "ACTIVE"},
            {"inferenceProfileId": "us.anthropic.claude-sonnet-4-6",
             "status": "ACTIVE"},
        ],
    }
    with patch("banko_ai.ai_providers.aws_provider.boto3.client",
               return_value=fake_bedrock):
        models = provider.get_available_models()

    assert "us.anthropic.claude-haiku-4-5-20251001-v1:0" in models
    assert "us.anthropic.claude-sonnet-4-6" in models
    assert not any("claude-3-" in m for m in models), (
        f"Claude 3.x must be filtered out (Bedrock Legacy denial); got {models}"
    )


def test_fallback_stub_is_all_claude_4(provider):
    """If Bedrock is unreachable, the dropdown still has to offer current
    inference profiles so the user can pick one that will actually invoke."""
    with patch("banko_ai.ai_providers.aws_provider.boto3.client",
               side_effect=RuntimeError("simulated bedrock outage")):
        models = provider.get_available_models()

    assert isinstance(models, list)
    assert len(models) >= 2, f"Fallback must offer multiple models; got {models}"
    assert not any("claude-3-" in m for m in models), (
        f"Fallback must not seed the dropdown with Claude 3.x (Legacy on "
        f"Bedrock after 30 days idle); got {models}"
    )
    # At least one Haiku tier (cheap default) must be present
    assert any("haiku" in m.lower() for m in models), (
        "Fallback should include a Haiku-tier inference profile as the "
        "demo-friendly default"
    )


def test_default_model_is_not_legacy(provider):
    """get_default_model() seeds the very first request before discovery
    runs — if it returns a Legacy ID, the cold-start request 500s before
    the user can pick a different model from the dropdown."""
    default = provider.get_default_model()
    assert "claude-3-" not in default.lower(), (
        f"Default model must not be Claude 3.x (Legacy on Bedrock); got {default}"
    )
    assert default.startswith(("us.", "global.")), (
        f"Default must be a cross-region inference profile, not a bare "
        f"foundation model ID; got {default}"
    )


def test_env_override_skips_discovery_and_filter(monkeypatch):
    """AWS_MODELS env var must short-circuit the API call AND the Legacy
    filter — operators may need to pin a Claude 3.x profile in airgap or
    locked-down accounts that haven't been migrated. Pinning is an explicit
    operator override; we don't second-guess it."""
    monkeypatch.setenv(
        "AWS_MODELS",
        "us.anthropic.claude-3-5-haiku-20241022-v1:0, us.anthropic.claude-haiku-4-5-20251001-v1:0",
    )
    p = AWSProvider({
        "access_key_id": "k",
        "secret_access_key": "s",
        "region": "us-east-1",
        "model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    })
    with patch("banko_ai.ai_providers.aws_provider.boto3.client") as mock_client:
        models = p.get_available_models()

    assert models == [
        "us.anthropic.claude-3-5-haiku-20241022-v1:0",
        "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    ]
    assert mock_client.call_count == 0, (
        "Env override must bypass the boto3 call entirely"
    )


def test_is_legacy_claude_helper_covers_inference_profile_prefixes():
    """The legacy check has to catch both bare foundation IDs and the
    us./global. inference-profile prefixes Bedrock uses."""
    assert AWSProvider._is_legacy_claude("anthropic.claude-3-haiku-20240307-v1:0")
    assert AWSProvider._is_legacy_claude("us.anthropic.claude-3-5-sonnet-20241022-v2:0")
    assert AWSProvider._is_legacy_claude("global.anthropic.claude-3-opus-20240229-v1:0")
    assert not AWSProvider._is_legacy_claude("us.anthropic.claude-haiku-4-5-20251001-v1:0")
    assert not AWSProvider._is_legacy_claude("us.anthropic.claude-sonnet-4-6")
    assert not AWSProvider._is_legacy_claude("us.anthropic.claude-opus-4-7")
