# Removed PRC-operated integrations

Hermes no longer ships any first-party integration with a service operated from
the People's Republic of China. This document records **what was removed, why,
what was deliberately kept, and how the policy is enforced** so the decision is
auditable and reversible by a future maintainer.

## Why

The harness previously bundled model providers, messaging platforms, a memory
backend, a TTS backend, and document tools that terminate at PRC-operated API
endpoints. Enabling any of them sends user prompts, conversation history,
attached files, and API credentials to those endpoints. The operator of this
harness does not want users able to establish those connections, so the
integrations were removed rather than merely defaulted off.

The dividing line throughout is the **service operator**, not the model weights
or the language. An open-weight model of Chinese origin served by a non-PRC
provider is not affected — that connection terminates at the non-PRC provider.
See [Deliberately kept](#deliberately-kept).

## What was removed

### Model providers (`plugins/model-providers/`)

| Plugin | Service | Operator | Endpoint |
|---|---|---|---|
| `alibaba` | Qwen / DashScope (Model Studio) | Alibaba Cloud | `dashscope*.aliyuncs.com` |
| `alibaba-coding-plan` | Alibaba Cloud Coding Plan | Alibaba Cloud | `coding*.dashscope.aliyuncs.com` |
| `qwen-oauth` | Qwen Portal (OAuth, via Qwen CLI) | Alibaba Cloud | `portal.qwen.ai` |
| `deepseek` | DeepSeek V3/V4 | DeepSeek (Hangzhou) | `api.deepseek.com` |
| `kimi-coding` | Kimi / Moonshot (global + China) | Moonshot AI (Beijing) | `api.moonshot.ai`, `api.moonshot.cn`, `api.kimi.com` |
| `minimax` | MiniMax M-series (global + China + OAuth) | MiniMax (Shanghai) | `api.minimax.io`, `api.minimaxi.com` |
| `zai` | Z.AI / GLM | Zhipu AI (Beijing) | `api.z.ai`, `open.bigmodel.cn` |
| `stepfun` | StepFun Step Plan | StepFun (Shanghai) | `api.stepfun.ai`, `api.stepfun.com` |
| `xiaomi` | Xiaomi MiMo | Xiaomi (Beijing) | `api.xiaomimimo.com` |

Two further providers existed only in the auth registry and were removed with
them: **Tencent TokenHub** (`tokenhub.tencentmaas.com`) and **Tencent
TokenPlan** (`api.lkeap.cloud.tencent.com`).

Removing the plugin directory is sufficient to unregister a provider — the
registry in `providers/__init__.py` discovers profiles by directory scan. The
accompanying entries in `hermes_cli/auth.py` (`PROVIDER_REGISTRY`), the overlays
and aliases in `hermes_cli/providers.py`, the auxiliary/vision model tables in
`agent/auxiliary_client.py`, and the OAuth machinery for Qwen and MiniMax were
removed alongside them.

### Messaging platforms

| Integration | Service | Operator | Where it lived |
|---|---|---|---|
| `qqbot` | QQ Bot (Open Platform API v2) | Tencent | `gateway/platforms/qqbot/` |
| `weixin` | Weixin / WeChat personal (iLink Bot) | Tencent | `gateway/platforms/weixin.py` |
| `yuanbao` | Tencent Yuanbao (元宝) | Tencent | `gateway/platforms/yuanbao*.py` |
| `wecom` / `wecom_callback` | WeCom (Enterprise WeChat) | Tencent | `plugins/platforms/wecom/` |
| `feishu` | Feishu / Lark | ByteDance | `plugins/platforms/feishu/` |
| `dingtalk` | DingTalk (钉钉) | Alibaba | `plugins/platforms/dingtalk/` |

Their `Platform` enum members, env-var loaders, allowlist/pairing maps, display
tiers, setup wizards, dashboard cards, toolsets, and `send_message` routing were
removed from `gateway/`, `hermes_cli/`, `toolsets.py`, and
`tools/send_message_tool.py`.

### Tools

- `tools/feishu_doc_tool.py` — read Feishu/Lark document content.
- `tools/feishu_drive_tool.py` — Feishu/Lark document comment operations.
- `tools/yuanbao_tools.py` — Yuanbao group info, member queries, DM, stickers.
- `hermes_cli/dingtalk_auth.py` — DingTalk QR device-flow registration.

### Memory provider

- `plugins/memory/openviking` — **OpenViking**, backed by ByteDance VikingDB on
  Volcano Engine (`api.vikingdb.cn-beijing.volces.com`). This one is worth
  calling out: a memory provider receives the *most* durable copy of user
  content of anything in the harness.

### Text-to-speech

- **MiniMax TTS** (`api.minimax.io/v1/t2a_v2`, `api.minimaxi.com/v1/t2a_v2`),
  removed from `tools/tts_tool.py` and the provider lists in
  `agent/tts_registry.py` / `agent/tts_provider.py`. It was easy to miss because
  it lived in the TTS surface rather than among the model providers.

### Other wiring removed

- `api.deepseek.com` from the Iron Proxy upstream allowlist and bearer-swap map
  (`agent/proxy_sources/iron_proxy.py`).
- DeepSeek and Moonshot AI top-up links (`agent/billing_links.py`).
- Qwen CLI (`~/.qwen/oauth_creds.json`) and MiniMax OAuth as borrowed credential
  sources (`agent/credential_sources.py`, `agent/credential_pool.py`,
  `agent/credential_persistence.py`).
- All corresponding env vars and commented examples in `.env.example` and
  `cli-config.yaml.example`.

## Enforcement: the endpoint deny-list

Deleting integrations is necessary but not sufficient. Several paths accept a
**user-supplied endpoint** and would happily reach a removed service if pointed
at it: `model.base_url`, the `custom` provider, `providers:` and
`custom_providers:` config entries, `*_BASE_URL` env overrides, and the URL
fetching tools.

`agent/blocked_endpoints.py` is the single place that refuses those hosts. It is
enforced at three boundaries:

| Boundary | Behavior |
|---|---|
| `tools/url_safety.py::is_safe_url` | Fetches to blocked hosts are refused, alongside the existing SSRF checks. |
| `hermes_cli/auth.py::resolve_api_key_provider_credentials` | A `*_BASE_URL` override aimed at a blocked host raises `AuthError`. |
| `hermes_cli/providers.py` | `providers:` / `custom_providers:` entries naming a blocked host are ignored with a warning. |

Matching is on the **hostname**, exact or as a parent domain, via
`utils.base_url_host_matches`. Substring matching on the raw URL is never used:
it would both miss `https://API.Z.AI/v1` and false-positive on
`https://example.test/notes/about-z.ai`. `tests/agent/test_blocked_endpoints.py`
pins both directions, including lookalike hosts
(`api.deepseek.com.attacker.test`) and path spoofs (`proxy.test/api.z.ai/v1`).

**Escape hatch.** Setting `HERMES_ALLOW_PRC_ENDPOINTS=1` disables enforcement.
It exists so an operator in a different jurisdiction can re-enable these
services deliberately. It is off by default and never set by Hermes itself.

## Deliberately kept

These were reviewed and **not** removed. The reasoning is recorded so the line
isn't redrawn by accident:

- **Chinese-origin open-weight models served by non-PRC providers** — Qwen, GLM,
  Kimi, DeepSeek and MiniMax weights remain reachable through OpenRouter,
  DeepInfra, Fireworks, Novita, Hugging Face, AWS Bedrock, and OpenCode. Those
  connections terminate at a non-PRC operator, which is the boundary this change
  is drawn on. Model-metadata, pricing, and wire-format compatibility tables for
  those model families were kept for the same reason — removing them would break
  the legitimate non-PRC routes. `agent/moonshot_schema.py` is the clearest
  example: it fixes up tool schemas for Kimi models served via aggregators.
- **GMI Cloud** (`gmi`) — headquartered in Taiwan / Mountain View, not the PRC.
- **Novita AI** (`novita`) — Singapore-headquartered. Flagging it here because
  it is the closest call on the list; remove it if your policy is based on
  founder nationality rather than operator jurisdiction.
- **Upstage** (`upstage`) — South Korean.
- **LINE** (`plugins/platforms/line`) — operated by LY Corporation (Japan).
- **`README.zh-CN.md`** — a Chinese-language translation of the README. A
  translation is not a service connection.

## Known residue

Some internal helpers still carry host-specific wire-format branches for the
removed endpoints (for example `api.minimax.*` / `open.bigmodel.cn` handling in
`agent/auxiliary_client.py`). These are now unreachable: no bundled provider
resolves to those hosts, and the deny-list refuses them if supplied manually.
They were left rather than surgically excised because the surrounding code is
shared with live providers and the edit carried more regression risk than value.
They are dead branches, not connection paths.

## Verifying

```bash
# The deny-list and its boundaries
python -m pytest tests/agent/test_blocked_endpoints.py

# No removed provider is registered
python -c "import providers; print(sorted(p.name for p in providers.list_providers()))"

# No removed platform is in the gateway enum
python -c "from gateway.config import Platform; print(sorted(p.value for p in Platform))"
```
