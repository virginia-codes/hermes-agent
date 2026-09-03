"""Policy tests for the PRC-operated endpoint deny-list.

Covers the three properties the policy depends on:
  1. Removed services are blocked on their real hosts and subdomains.
  2. Lookalike hosts and path-segment spoofs are NOT blocked (and, just as
     importantly, legitimate providers are not caught by substring matching).
  3. The documented ``HERMES_ALLOW_PRC_ENDPOINTS`` opt-out actually disables
     enforcement.
"""

import pytest

from agent.blocked_endpoints import (
    BlockedEndpointError,
    assert_endpoint_allowed,
    blocked_domain_for,
    is_blocked_endpoint,
)


BLOCKED_URLS = [
    "https://api.deepseek.com/v1",
    "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
    "https://api.moonshot.ai/v1",
    "https://api.moonshot.cn/v1",
    "https://api.kimi.com/coding",
    "https://api.minimax.io/anthropic",
    "https://api.minimaxi.com/anthropic",
    "https://api.z.ai/api/paas/v4",
    "https://open.bigmodel.cn/api/coding/paas/v4",
    "https://api.stepfun.ai/step_plan/v1",
    "https://api.xiaomimimo.com/v1",
    "https://portal.qwen.ai/v1",
    "https://tokenhub.tencentmaas.com/v1",
    "https://api.lkeap.cloud.tencent.com/plan/anthropic",
    "https://qyapi.weixin.qq.com",
    "https://yuanbao.tencent.com/",
    "https://open.feishu.cn/",
    "https://oapi.dingtalk.com",
    "https://api.vikingdb.cn-beijing.volces.com/openviking",
]

ALLOWED_URLS = [
    "https://api.openai.com/v1",
    "https://api.anthropic.com",
    "https://openrouter.ai/api/v1",
    "https://api.deepinfra.com/v1/openai",
    "https://router.huggingface.co/v1",
    "https://api.x.ai/v1",
    "https://api.novita.ai/openai/v1",
    "https://api.gmi-serving.com/v1",
    "http://127.0.0.1:1234/v1",
    # Lookalikes and spoofs — hostname matching must not fire on these.
    "https://api.deepseek.com.attacker.test/v1",
    "https://proxy.test/api.z.ai/v1",
    "https://notqq.com/v1",
    "https://example.test/?q=moonshot.ai",
]


@pytest.mark.parametrize("url", BLOCKED_URLS)
def test_removed_services_are_blocked(url):
    assert is_blocked_endpoint(url) is True
    assert blocked_domain_for(url)


@pytest.mark.parametrize("url", ALLOWED_URLS)
def test_permitted_endpoints_are_not_blocked(url):
    assert is_blocked_endpoint(url) is False
    assert blocked_domain_for(url) is None


def test_empty_url_is_not_blocked():
    assert is_blocked_endpoint("") is False
    assert blocked_domain_for(None) is None


def test_assert_endpoint_allowed_raises_with_context():
    with pytest.raises(BlockedEndpointError) as excinfo:
        assert_endpoint_allowed("https://api.deepseek.com/v1", context="model.base_url")
    message = str(excinfo.value)
    assert "model.base_url" in message
    assert "deepseek.com" in message


def test_assert_endpoint_allowed_passes_for_permitted_url():
    assert_endpoint_allowed("https://api.openai.com/v1", context="model.base_url") is None


def test_env_opt_out_disables_enforcement(monkeypatch):
    monkeypatch.setenv("HERMES_ALLOW_PRC_ENDPOINTS", "1")
    assert is_blocked_endpoint("https://api.deepseek.com/v1") is False
    assert_endpoint_allowed("https://api.deepseek.com/v1", context="model.base_url")


def test_url_safety_blocks_removed_services():
    from tools.url_safety import is_safe_url

    assert is_safe_url("https://api.z.ai/api/paas/v4") is False
    assert is_safe_url("https://api.anthropic.com/v1") is True


def test_custom_provider_entry_pointing_at_blocked_host_is_ignored():
    from hermes_cli.providers import resolve_user_provider

    blocked = resolve_user_provider("mine", {"mine": {"url": "https://api.deepseek.com/v1"}})
    assert blocked is None

    allowed = resolve_user_provider("mine", {"mine": {"url": "https://api.openai.com/v1"}})
    assert allowed is not None
    assert allowed.base_url == "https://api.openai.com/v1"


# ---------------------------------------------------------------------------
# Surface coverage: a removed provider must not reappear in any user-facing list
# ---------------------------------------------------------------------------
#
# Deleting plugins/model-providers/<name>/ unregisters a provider from the
# plugin registry, but the setup wizard and `hermes model` picker render
# hermes_cli.models.CANONICAL_PROVIDERS — a hand-maintained list that is NOT
# derived from that registry. A removal that misses it leaves DeepSeek, Kimi,
# GLM et al. offered on a blank-slate install even though nothing can serve
# them. This test pins every list a user actually sees.

_PRC_PROVIDER_SLUGS = frozenset({
    "alibaba", "alibaba-cn", "alibaba-coding-plan", "alibaba-coding-plan-cn",
    "alibaba-token-plan", "alibaba-token-plan-cn", "qwen-oauth",
    "deepseek", "zai", "kimi-coding", "kimi-coding-cn", "stepfun",
    "minimax", "minimax-cn", "minimax-oauth", "xiaomi",
    "tencent-tokenhub", "tencent-tokenplan",
})


def test_picker_provider_list_has_no_prc_providers():
    """CANONICAL_PROVIDERS drives `hermes model` and the setup wizard."""
    from hermes_cli.models import CANONICAL_PROVIDERS

    listed = {p.slug for p in CANONICAL_PROVIDERS}
    assert not (listed & _PRC_PROVIDER_SLUGS), (
        f"removed providers still offered in the picker: "
        f"{sorted(listed & _PRC_PROVIDER_SLUGS)}"
    )


def test_provider_groups_have_no_prc_members():
    """Grouped picker rows (Kimi, MiniMax, Qwen, Tencent) must be gone too."""
    from hermes_cli.models import PROVIDER_GROUPS

    members = {slug for _l, _d, slugs in PROVIDER_GROUPS.values() for slug in slugs}
    assert not (members & _PRC_PROVIDER_SLUGS), (
        f"removed providers still grouped in the picker: "
        f"{sorted(members & _PRC_PROVIDER_SLUGS)}"
    )


def test_model_catalogs_and_aliases_have_no_prc_providers():
    """A stale alias would resolve a user's `--provider glm` to a dead slug."""
    from hermes_cli.models import _PROVIDER_ALIASES, _PROVIDER_MODELS

    assert not (set(_PROVIDER_MODELS) & _PRC_PROVIDER_SLUGS)
    assert not (set(_PROVIDER_ALIASES.values()) & _PRC_PROVIDER_SLUGS)


def test_auth_registry_has_no_prc_providers():
    """PROVIDER_REGISTRY backs `hermes auth add` and credential resolution."""
    from hermes_cli.auth import PROVIDER_REGISTRY

    assert not (set(PROVIDER_REGISTRY) & _PRC_PROVIDER_SLUGS)


def test_plugin_registry_has_no_prc_providers():
    """providers/ discovery — the plugins/model-providers/<name>/ dirs."""
    import providers

    assert not ({p.name for p in providers.list_providers()} & _PRC_PROVIDER_SLUGS)


def test_gateway_platform_enum_has_no_prc_platforms():
    """Platform members back the gateway, setup wizard, and dashboard cards."""
    from gateway.config import Platform

    prc_platforms = {"qqbot", "weixin", "yuanbao", "wecom", "wecom_callback",
                     "feishu", "dingtalk"}
    assert not ({p.value for p in Platform} & prc_platforms)


# ---------------------------------------------------------------------------
# The dashboard / desktop custom-endpoint API
# ---------------------------------------------------------------------------
#
# The web UI lets a user type an arbitrary base URL, which is the same trust
# boundary as `providers:` in config.yaml. Both the save path and the two
# live-probe routes must refuse a blocked host — the probes especially, since
# they send the user's API key to whatever URL was entered.


def test_custom_endpoint_write_rejects_blocked_base_url():
    from fastapi import HTTPException

    from hermes_cli.web_server import _reject_blocked_base_url

    with pytest.raises(HTTPException) as excinfo:
        _reject_blocked_base_url("https://api.deepseek.com/v1")
    assert excinfo.value.status_code == 400
    assert "deepseek.com" in str(excinfo.value.detail)


def test_custom_endpoint_write_allows_permitted_base_url():
    from hermes_cli.web_server import _reject_blocked_base_url

    assert _reject_blocked_base_url("https://api.openai.com/v1") is None


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://api.deepseek.com/v1", "deepseek.com"),
        ("https://open.bigmodel.cn/api/paas/v4", "bigmodel.cn"),
        ("https://api.openai.com/v1", None),
        ("https://api.deepseek.com.attacker.test/v1", None),
        ("", None),
    ],
)
def test_dashboard_blocked_domain_helper(url, expected):
    """Probe routes gate on this before sending the API key anywhere."""
    from hermes_cli.web_server import _blocked_base_url_domain

    assert _blocked_base_url_domain(url) == expected
