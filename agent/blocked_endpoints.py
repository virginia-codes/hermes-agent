"""Deny-list for PRC-operated service endpoints.

Hermes no longer ships any first-party integration with a service operated
from the People's Republic of China: the model-provider plugins, gateway
platform adapters, memory provider, and TTS backend for those services were
removed (see ``docs/removed-prc-integrations.md``).

Removing the integrations is necessary but not sufficient. Several code paths
accept a user-supplied endpoint — ``model.base_url``, the ``custom`` provider,
``custom_providers`` config entries, ``*_BASE_URL`` env overrides, MCP server
URLs — and would happily talk to a removed service's API if pointed at it.
This module is the single place that says "no" to those hosts, so the policy
is enforced at the connection boundary rather than merely by the absence of a
bundled plugin.

Matching is on the **hostname**, exact or as a parent domain, via
``utils.base_url_host_matches``. Substring matching on the raw URL is never
used: it would both miss ``https://API.Z.AI/v1`` and false-positive on
``https://example.test/notes/about-z.ai``.

The list is deliberately about *service operators*, not model weights. An
open-weight model of Chinese origin served by a non-PRC provider (OpenRouter,
DeepInfra, Fireworks, Novita, Hugging Face, AWS Bedrock) is not blocked —
that connection terminates at the non-PRC provider.

Escape hatch: set ``HERMES_ALLOW_PRC_ENDPOINTS=1`` to disable enforcement.
It exists so an operator in a different jurisdiction can re-enable these
services deliberately; it is off by default and never set by Hermes itself.
"""

from __future__ import annotations

import logging
import os

from utils import base_url_host_matches, is_truthy_value

logger = logging.getLogger(__name__)


# Parent domains of PRC-operated services that Hermes used to integrate with,
# plus the sibling hosts of those same operators. Each entry is matched as the
# domain itself or any subdomain of it.
BLOCKED_ENDPOINT_DOMAINS: tuple[str, ...] = (
    # Alibaba — Qwen / DashScope / Model Studio / Aliyun
    "aliyuncs.com",
    "aliyun.com",
    "dashscope.cn",
    "qwen.ai",
    "tongyi.aliyun.com",
    # DeepSeek
    "deepseek.com",
    # Moonshot AI — Kimi
    "moonshot.ai",
    "moonshot.cn",
    "kimi.com",
    # MiniMax
    "minimax.io",
    "minimax.chat",
    "minimaxi.com",
    "minimax.com.cn",
    # Zhipu AI — Z.ai / GLM / BigModel
    "z.ai",
    "bigmodel.cn",
    "zhipuai.cn",
    # StepFun
    "stepfun.ai",
    "stepfun.com",
    # Xiaomi — MiMo
    "xiaomimimo.com",
    # Tencent — TokenHub, LKEAP, Yuanbao, WeChat, WeCom, QQ
    "tencentmaas.com",
    "lkeap.cloud.tencent.com",
    "tencentcloudapi.com",
    "yuanbao.tencent.com",
    "weixin.qq.com",
    "work.weixin.qq.com",
    "qq.com",
    # ByteDance — Volcano Engine / Ark / VikingDB / Feishu
    "volces.com",
    "volcengineapi.com",
    "feishu.cn",
    # Alibaba — DingTalk
    "dingtalk.com",
    # Baidu
    "baidubce.com",
    "baidu.com",
    # Other PRC model hosts previously reachable via custom endpoints
    "siliconflow.cn",
    "sensenova.cn",
    "sensetime.com",
    "01.ai",
    "baichuan-ai.com",
    "infini-ai.com",
    "ppinfra.com",
    "modelscope.cn",
)

_ALLOW_ENV_VAR = "HERMES_ALLOW_PRC_ENDPOINTS"


class BlockedEndpointError(ValueError):
    """Raised when a URL points at a blocked PRC-operated service."""


def enforcement_disabled() -> bool:
    """Return True when the operator has opted out via env var."""
    return is_truthy_value(os.environ.get(_ALLOW_ENV_VAR), default=False)


def blocked_domain_for(url: str) -> str | None:
    """Return the blocked parent domain *url* resolves to, or ``None``.

    Returns ``None`` for empty URLs and for every host not on the list, so
    callers can use it as a plain predicate. Enforcement opt-out is honored
    here so a single check covers every call site.
    """
    if not url or enforcement_disabled():
        return None
    for domain in BLOCKED_ENDPOINT_DOMAINS:
        if base_url_host_matches(url, domain):
            return domain
    return None


def is_blocked_endpoint(url: str) -> bool:
    """Return True when *url*'s host is a blocked PRC-operated service."""
    return blocked_domain_for(url) is not None


def assert_endpoint_allowed(url: str, *, context: str = "endpoint") -> None:
    """Raise :class:`BlockedEndpointError` when *url* is blocked.

    *context* names the caller's surface (``"model.base_url"``, ``"MCP
    server"``, …) so the error tells the user which setting to change.
    """
    domain = blocked_domain_for(url)
    if domain is None:
        return
    raise BlockedEndpointError(
        f"{context} points at {domain}, a service operated from the PRC. "
        f"Hermes no longer ships integrations with these services; see "
        f"docs/removed-prc-integrations.md. Set {_ALLOW_ENV_VAR}=1 to "
        f"override this policy deliberately."
    )
