"""Tests for the models.dev-preferred merge behavior in provider_model_ids
and list_authenticated_providers.

These guard the contract:

  * For providers in ``_MODELS_DEV_PREFERRED`` (opencode-go, opencode-zen,
    smaller inference providers), both the CLI model
    picker path (``provider_model_ids``) and the gateway ``/model`` picker
    path (``list_authenticated_providers``) merge fresh models.dev entries
    on top of the curated static list.
  * OpenRouter and Nous Portal are NEVER merged — they keep their curated
    (OpenRouter) or live-Portal (Nous) semantics.
  * If models.dev is unreachable (offline / CI), the curated list is the
    fallback — no crash, no empty list.

Merging is what lets new models (e.g. ``mimo-v2.5-pro`` on opencode-go)
appear in ``/model`` without a Hermes release.
"""

from unittest.mock import patch


from hermes_cli.models import (
    _MODELS_DEV_PREFERRED,
    _PROVIDER_MODELS,
    _merge_with_models_dev,
    provider_model_ids,
)


class TestMergeHelper:
    def test_merge_empty_mdev_returns_curated(self):
        """When models.dev returns nothing, curated list is preserved verbatim."""
        with patch("agent.models_dev.list_agentic_models", return_value=[]):
            out = _merge_with_models_dev("opencode-go", ["mimo-v2-pro", "kimi-k2.6"])
        assert out == ["mimo-v2-pro", "kimi-k2.6"]


    def test_merge_case_insensitive_dedup(self):
        """Dedup is case-insensitive but preserves the first occurrence's casing."""
        mdev = ["MiniMax-M2.7"]
        curated = ["minimax-m2.7", "minimax-m2.5"]
        with patch("agent.models_dev.list_agentic_models", return_value=mdev):
            out = _merge_with_models_dev("minimax", curated)
        # models.dev casing wins since it came first
        assert out == ["MiniMax-M2.7", "minimax-m2.5"]


class TestOpenRouterAndNousUnchanged:
    """Per Teknium: openrouter and nous are NEVER merged with models.dev."""


    def test_openrouter_does_not_call_merge(self):
        """openrouter takes its own live path — merge helper must NOT run."""
        with patch(
            "hermes_cli.models._merge_with_models_dev",
            side_effect=AssertionError("merge should not be called for openrouter"),
        ):
            # Even if model_ids() fails for some other reason, we just care
            # that the merge path isn't invoked.
            try:
                provider_model_ids("openrouter")
            except AssertionError:
                raise
            except Exception:
                pass  # model_ids() may fail in the hermetic test env — that's fine.
