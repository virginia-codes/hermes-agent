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
- `README.zh-CN.md`, the Chinese-language README translation, along with the
  language badge linking to it from `README.md`, `README.es.md` and
  `README.ur-pk.md`, and its entry in the `nix/lib.nix` wheel-source exclusion
  list. This one is a judgment call rather than a service connection: the
  translation reached no PRC endpoint, so it was initially kept and is now
  removed on the narrower ground that the project no longer maintains a
  zh-CN surface. Reinstating it would not reopen any of the network paths this
  document is about.

## Enforcement: the endpoint deny-list

Deleting integrations is necessary but not sufficient. Several paths accept a
**user-supplied endpoint** and would happily reach a removed service if pointed
at it: `model.base_url`, the `custom` provider, `providers:` and
`custom_providers:` config entries, `*_BASE_URL` env overrides, and the URL
fetching tools.

`agent/blocked_endpoints.py` is the single place that refuses those hosts. It is
enforced at these boundaries:

| Boundary | Behavior |
|---|---|
| `tools/url_safety.py::is_safe_url` | Fetches to blocked hosts are refused, alongside the existing SSRF checks. |
| `hermes_cli/auth.py::resolve_api_key_provider_credentials` | A `*_BASE_URL` override aimed at a blocked host raises `AuthError`. |
| `hermes_cli/providers.py` | `providers:` / `custom_providers:` entries naming a blocked host are ignored with a warning. |
| `hermes_cli/web_server.py::_reject_blocked_base_url` | The dashboard/desktop "custom endpoint" form returns HTTP 400 instead of saving. |
| `hermes_cli/web_server.py` probe routes | `/api/providers/validate` and `/api/providers/custom-endpoints/validate` refuse **before** the probe — those routes send the user's API key to the URL, so probing a blocked host would leak the credential to it. |

Matching is on the **hostname**, exact or as a parent domain, via
`utils.base_url_host_matches`. Substring matching on the raw URL is never used:
it would both miss `https://API.Z.AI/v1` and false-positive on
`https://example.test/notes/about-z.ai`. `tests/agent/test_blocked_endpoints.py`
pins both directions, including lookalike hosts
(`api.deepseek.com.attacker.test`) and path spoofs (`proxy.test/api.z.ai/v1`).

**Escape hatch.** Setting `HERMES_ALLOW_PRC_ENDPOINTS=1` disables enforcement.
It exists so an operator in a different jurisdiction can re-enable these
services deliberately. It is off by default and never set by Hermes itself.

### The second tier: the general PRC web

Blocking the service endpoints stops Hermes *connecting to* a PRC provider. It
does not stop the agent *browsing to* a PRC site — `web_fetch`, the browser
tools and image/vision fetches would happily load `https://www.people.com.cn`.
`BLOCKED_WEB_DOMAINS` in the same module closes that, with two rules:

- **`cn`** — the ccTLD. `base_url_host_matches` tests `host == rule or
  host.endswith("." + rule)`, so one entry covers every `*.cn`, `*.com.cn`,
  `*.gov.cn`, and does *not* match lookalikes like `notcn.com` or `cnn.com`.
- **Named `.com` operators** — Alibaba, Tencent, ByteDance, Baidu, Huawei,
  Xiaomi, JD, NetEase, Bilibili, Gitee and the rest. A ccTLD rule alone misses
  every one of these, which is the trap this tier exists to avoid.

`HERMES_ALLOW_PRC_WEB=1` re-enables **only** this tier, because the two
policies differ in kind: an operator may reasonably bar the agent from PRC
*inference providers* — where prompts and credentials go — while still letting
it read a PRC news site for research. The master switch above disables both.

**What this is not.** A deny-list cannot enumerate the PRC web, so this raises
the floor rather than guaranteeing jurisdictional isolation. Two specific gaps:

- **The terminal tool bypasses it.** A subprocess running `curl https://x.cn`
  never reaches a Hermes HTTP client. Only a network-level control (egress
  proxy, host firewall) covers that.
- **TLD is a weak proxy for operator nationality**, in both directions — some
  `.cn` domains are not PRC-operated, and PRC companies register `.com` freely.
  The named-operator list mitigates the second direction, not the first.

`tiktok.com` is included as ByteDance-operated. If you treat TikTok as a
US/Singapore entity, delete that one entry — nothing else depends on it.

One knock-on: `tools/url_safety.py` kept a single-entry SSRF exception,
`_TRUSTED_PRIVATE_IP_HOSTS = {"multimedia.nt.qq.com.cn"}`, letting QQ media
downloads resolve into benchmark space (`198.18.0.0/15`). The QQ integration is
gone and `*.cn` is now denied earlier than that check runs, so the exception was
dead code. The set is empty; the hook remains so a future host can be
allowlisted without re-deriving the two call sites.

### The operator's own blocklist

`security.website_blocklist` in `~/.hermes/config.yaml` is a separate,
user-managed list (`tools/website_policy.py`) that predates this work. It is
now consulted by `is_safe_url` as well, so one entry covers every path the
guard protects — previously it was honored only by `web_tools`, `browser_tool`,
`vision_tools`, `image_source`, `skills_hub` and the Firecrawl provider.

```yaml
security:
  website_blocklist:
    enabled: true
    domains: ["cn", "example.com"]
    shared_files: ["/etc/hermes/blocklist.txt"]
```

It fails **open** on a malformed config — a broken YAML file must not take out
all URL fetching — while the built-in deny-list above is unaffected by user
config and keeps enforcing.

## The picker list is a separate surface

Worth knowing if you ever remove another provider: unregistering it is **not**
enough to stop it being offered.

`hermes_cli/models.py::CANONICAL_PROVIDERS` is a hand-maintained list, not
derived from the plugin registry or `PROVIDER_REGISTRY`. It is what
`hermes_cli/inventory.py::build_models_payload` renders, and the CLI picker,
the web dashboard and the desktop app all read that payload. A provider deleted
everywhere else still appeared on a blank-slate setup until it was removed from
this list too — along with `PROVIDER_GROUPS`, `_PROVIDER_MODELS`,
`_PROVIDER_ALIASES` (a stale alias would resolve `--provider glm` to a dead
slug), `_MODELS_DEV_PREFERRED` and `_PROVIDER_RETIRED_ALIASES`.

`tests/agent/test_blocked_endpoints.py` pins all of these.

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

## Known residue

Some internal helpers still carry host-specific wire-format branches for the
removed endpoints (for example `api.minimax.*` / `open.bigmodel.cn` handling in
`agent/auxiliary_client.py`). These are now unreachable: no bundled provider
resolves to those hosts, and the deny-list refuses them if supplied manually.
They were left rather than surgically excised because the surrounding code is
shared with live providers and the edit carried more regression risk than value.
They are dead branches, not connection paths.

## Verifying

Use `scripts/run_tests.sh`, not `pytest` directly — see `AGENTS.md`. It runs
one subprocess per test file with bounded parallelism, which is both far faster
and CI-equivalent.

```bash
# The deny-list, every provider-list surface, and the dashboard API guard (~5s)
scripts/run_tests.sh tests/agent/test_blocked_endpoints.py tests/providers -q

# No removed provider is registered
python -c "import providers; print(sorted(p.name for p in providers.list_providers()))"

# No removed provider is OFFERED — this is the list the CLI picker, web
# dashboard and desktop app all render, and it is NOT derived from the
# registry above, so it has to be checked separately.
python -c "from hermes_cli.models import CANONICAL_PROVIDERS as C; print([p.slug for p in C])"

# The blank-slate payload the dashboard and desktop actually consume
python -c "from hermes_cli.inventory import build_models_payload, load_picker_context; \
print([r.get('provider') for r in build_models_payload(load_picker_context(), \
include_unconfigured=True).get('providers', [])])"

# No removed platform is in the gateway enum
python -c "from gateway.config import Platform; print(sorted(p.value for p in Platform))"
```
