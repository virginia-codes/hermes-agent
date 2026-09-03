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
