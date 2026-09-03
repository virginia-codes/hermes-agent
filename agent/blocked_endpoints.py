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

# ---------------------------------------------------------------------------
# Tier 2: the general PRC web, not just AI-service endpoints
# ---------------------------------------------------------------------------
#
# The list above stops Hermes CONNECTING to a PRC-operated model/messaging
# service. It does not stop the agent BROWSING to a PRC site — `web_fetch`,
# the browser tools and image/vision fetches would happily load
# ``https://www.people.com.cn``. This tier closes that.
#
# Two rules, because neither alone is sufficient:
#
#   * ``cn`` matches the ccTLD. ``base_url_host_matches`` tests
#     ``host == rule or host.endswith("." + rule)``, so a bare ``cn`` covers
#     every ``*.cn``, ``*.com.cn``, ``*.gov.cn`` — and does NOT match
#     lookalikes like ``notcn.com``.
#   * The largest PRC companies serve from ``.com``, so a ccTLD rule alone
#     misses Alibaba, Tencent, ByteDance, Baidu, Huawei et al. entirely.
#     Those are named explicitly.
#
# This is a deny-list, so it is inherently incomplete — it cannot enumerate
# the PRC web. It raises the floor; it is not a jurisdictional guarantee. The
# terminal tool bypasses it entirely (a subprocess running ``curl`` never
# reaches Hermes' HTTP clients); only a network-level control covers that.
BLOCKED_WEB_DOMAINS: tuple[str, ...] = (
    # The ccTLD itself.
    "cn",
    # Alibaba
    "alibaba.com", "alibabagroup.com", "taobao.com", "tmall.com",
    "aliexpress.com", "alipay.com", "1688.com", "cainiao.com",
    # Tencent
    "tencent.com", "wechat.com", "qcloud.com",
    # ByteDance. NOTE: tiktok.com is deliberately included as ByteDance-
    # operated; if you treat TikTok as a US/SG-operated entity, drop this
    # one line — nothing else depends on it.
    "bytedance.com", "douyin.com", "tiktok.com", "capcut.com",
    # Baidu / Huawei / Xiaomi / JD / Meituan / PDD / NetEase / Sina / Sohu
    "baidu.com", "huawei.com", "hicloud.com", "xiaomi.com", "mi.com",
    "jd.com", "meituan.com", "pinduoduo.com", "temu.com",
    "163.com", "126.com", "netease.com", "sina.com", "weibo.com",
    "sohu.com", "ifeng.com",
    # Media / community / commerce
    "bilibili.com", "zhihu.com", "douban.com", "xiaohongshu.com",
    "kuaishou.com", "iqiyi.com", "youku.com", "ctrip.com", "trip.com",
    "shein.com", "lenovo.com", "zte.com.cn", "dji.com",
    # Infrastructure / dev
    "gitee.com", "csdn.net", "cnblogs.com", "oschina.net", "aliyuncs.com",
)

_ALLOW_ENV_VAR = "HERMES_ALLOW_PRC_ENDPOINTS"
_ALLOW_WEB_ENV_VAR = "HERMES_ALLOW_PRC_WEB"


class BlockedEndpointError(ValueError):
    """Raised when a URL points at a blocked PRC-operated service."""


def enforcement_disabled() -> bool:
    """Return True when the operator has opted out via env var.

    This is the master switch: it disables BOTH tiers.
    """
    return is_truthy_value(os.environ.get(_ALLOW_ENV_VAR), default=False)


def web_enforcement_disabled() -> bool:
    """Return True when general PRC web browsing is re-enabled.

    Separate from :func:`enforcement_disabled` because the two policies are
    different in kind: an operator may reasonably want the agent barred from
    PRC *inference providers* (where prompts and credentials go) while still
    letting it read a PRC news site for research. Setting the master switch
    also disables this tier.
    """
    if enforcement_disabled():
        return True
    return is_truthy_value(os.environ.get(_ALLOW_WEB_ENV_VAR), default=False)


def blocked_domain_for(url: str) -> str | None:
    """Return the blocked parent domain *url* resolves to, or ``None``.

    Covers both tiers: the PRC-operated service endpoints and, unless
    ``HERMES_ALLOW_PRC_WEB`` is set, the general PRC web.

    Returns ``None`` for empty URLs and for every host not on the list, so
    callers can use it as a plain predicate. Enforcement opt-out is honored
    here so a single check covers every call site.
    """
    if not url or enforcement_disabled():
        return None
    for domain in BLOCKED_ENDPOINT_DOMAINS:
        if base_url_host_matches(url, domain):
            return domain
    if not web_enforcement_disabled():
        for domain in BLOCKED_WEB_DOMAINS:
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
