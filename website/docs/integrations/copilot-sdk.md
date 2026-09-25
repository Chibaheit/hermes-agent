---
title: Copilot SDK (experimental plugin)
description: Use the official GitHub Copilot SDK through an opt-in external model-provider plugin.
---

# Copilot SDK

This fork can use the official GitHub Copilot SDK through the standalone
[`Chibaheit/hermes-copilot-sdk`](https://github.com/Chibaheit/hermes-copilot-sdk)
plugin. It uses Hermes' existing pip model-provider extension point; **no vendor
code, dependencies, or changed safety defaults are added to Hermes core**.

This is separate from `copilot` (direct API) and `copilot-acp` (ACP subprocess).
Those providers continue to behave as before.

## Setup

Install the plugin in the same Python 3.11-3.13 environment as Hermes, following its
[installation instructions](https://github.com/Chibaheit/hermes-copilot-sdk#install-and-enable).
The plugin pins `github-copilot-sdk==1.0.14`; provision the matching runtime with
`python -m copilot download-runtime`.

The verified plugin revision is
[`ed22b3c`](https://github.com/Chibaheit/hermes-copilot-sdk/commit/ed22b3c9822236fb3109ccc3c5d321342c62d44a).
For a reproducible installation:

```sh
python -m pip install "git+https://github.com/Chibaheit/hermes-copilot-sdk.git@ed22b3c9822236fb3109ccc3c5d321342c62d44a"
python -m copilot download-runtime
```

Merge the following into the current profile's `config.yaml`:

```yaml
plugins:
  enabled:
    - copilot-sdk
model:
  provider: copilot-sdk
  default: YOUR_COPILOT_MODEL_ID
  base_url: copilot-sdk://runtime
  api_mode: chat_completions
copilot_sdk:
  timeout_seconds: 120
```

Preserve any already-enabled plugins. Put `COPILOT_GITHUB_TOKEN` in that profile's
`.env`, with Copilot entitlement/permissions, and restart Hermes. The plugin
intentionally does not reuse the interactive Copilot login or another profile's
credentials. Discover available model IDs using the plugin's `list_models()`;
then run `hermes --provider copilot-sdk --model YOUR_COPILOT_MODEL_ID`.

This baseline's interactive model picker excludes external-process plugins;
explicit configuration or CLI flags are required. Installing the plugin alone
does not activate it.

## Execution and limitations

Hermes owns history, tool execution, and approvals. Each completion starts a fresh,
tool-disabled SDK session with private profile-scoped storage. Hermes messages and
tool schemas are sent as text; strictly validated textual tool requests return to
Hermes' normal loop. Native Copilot tools, skills and configuration discovery are
disabled. Timeout/cancellation trigger bounded session and runtime cleanup.

The adapter is **experimental and text-only**, not a native OpenAI endpoint.
Streaming is buffered; structured response formats and usage accounting are not
available. A stable serialized prefix does not guarantee remote prompt-cache
reuse. Runtime I/O still occurs: empty mode is not an OS sandbox.

The initial compatibility baseline is this fork's official-upstream commit
`03fee43ca344ead7245a3b0ae20d38de0ae75642`. The fork was **not synchronized to newer
upstream** during this integration because the current GitHub grant cannot update
workflow files. No workflows were removed or rewritten to bypass that restriction.

## 中文摘要

通过独立插件接入官方 Copilot SDK，不修改 Hermes 核心依赖或原有安全默认值。
在当前配置档启用插件、设置模型并提供具备 Copilot 权限的令牌后使用；
已有 `copilot` 与 `copilot-acp` 不受影响。

SDK 不直接执行工具，工具请求仍由 Hermes 校验、执行和审批。当前为实验性
纯文本兼容层，暂不支持图片、原生结构化输出、实时 token 流或用量统计。
独立存储及空模式不是操作系统沙箱；详细安装、隔离边界和测试见插件仓库。
