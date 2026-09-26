---
title: Copilot SDK (experimental plugin)
description: Use the official GitHub Copilot SDK through an opt-in external model-provider plugin.
---

# Copilot SDK

> **Superseded for the current deployment:** use
> [Hermes coordinator with Copilot CLI workers](./copilot-cli.md).
> The SDK bridge below is retained as historical documentation, not the
> recommended architecture. Hermes now coordinates direct CLI workers.

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
  default: gpt-6-astra
  base_url: copilot-sdk://runtime
  api_mode: chat_completions
copilot_sdk:
  timeout_seconds: 120
```

Preserve any already-enabled plugins. Put `COPILOT_GITHUB_TOKEN` in that profile's
`.env`, with Copilot entitlement/permissions, and restart Hermes. The plugin
intentionally does not reuse the interactive Copilot login or another profile's
credentials. Discover available model IDs using the plugin's `list_models()`;
then run `hermes --provider copilot-sdk --model gpt-6-astra`.
This fork's recommended configuration uses the GPT-6 family. If that model is
unavailable to your account, select another authorized GPT-6-family model
explicitly rather than silently falling back to an older family.

This baseline's interactive model picker excludes external-process plugins;
explicit configuration or CLI flags are required. Installing the plugin alone
does not activate it.

## Headless Linux and Telegram

See [Linux setup with Copilot SDK, Telegram, and gog](./copilot-sdk-telegram-gog.md)
for the reproducible fork installation, persistent Telegram gateway, restricted
pairing, Google Workspace skill, encrypted OAuth storage, and verification steps.
The gateway uses the same configured provider; direct terminal chat is only a
setup probe, not required for normal use.

## Access locally on Windows

The local setup uses a separate profile at
`$HOME\.hermes\profiles\copilot-sdk`, leaving the default profile unchanged.
Save the configuration above as that profile's `config.yaml`; its `.env` stays
local and must never be copied into this repository.

With Hermes and the pinned plugin installed in
`$HOME\Repos\.venvs\hermes-copilot-sdk`, start an interactive terminal chat:

```powershell
$previousHome = $env:HERMES_HOME
$env:HERMES_HOME = "$HOME\.hermes\profiles\copilot-sdk"
try {
    & "$HOME\Repos\.venvs\hermes-copilot-sdk\Scripts\hermes.exe" --cli
} finally {
    $env:HERMES_HOME = $previousHome
}
```

Adjust the executable path if your Hermes environment is elsewhere. On the
already-configured local machine, the same profile can be opened with its launcher:

```powershell
& "$HOME\.hermes\profiles\copilot-sdk\start.ps1"
```

The launcher is a local convenience, not a file installed by the plugin. This is
a terminal application; no web server or public endpoint is started.

## Local execution evidence

Authenticated Hermes inference and a real `read_file` round trip succeeded on
Windows with Python 3.12. Hermes emitted a tool request, executed the file read,
and returned the synthetic file's contents after a second SDK completion.
That initial live run used `gpt-5.4-mini` before the model preference changed;
the local profile now selects `gpt-6-astra`. That Windows result is not
model-specific GPT-6 validation.

On Fri, 2026-09-25, the Linux installation with Python 3.11.16 successfully
listed account-authorized GPT-6 models and completed authenticated inference
with `gpt-6-astra`, both directly through the SDK plugin and through Hermes'
one-shot chat. The Telegram gateway connected, pairing was approved, and the user
service was enabled. The installed gog skill loaded, Google token refresh passed,
and read-only Gmail, Calendar, and Drive probes succeeded. This does not claim a
Telegram-triggered Google tool round trip or GPT-6 Windows validation.

Credentials were saved through Hermes' credential helper in the isolated profile,
with file access restricted to the local user and SYSTEM. No token or personal
repository content is included in this fork.

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
Hermes' CLI may display zero token counts when usage is unavailable; these are
not evidence that inference was free or consumed no tokens.

The initial compatibility baseline is this fork's official-upstream commit
`03fee43ca344ead7245a3b0ae20d38de0ae75642`. The fork was **not synchronized to newer
upstream** during this integration because the current GitHub grant cannot update
workflow files. No workflows were removed or rewritten to bypass that restriction.

## 中文摘要

通过独立插件接入官方 Copilot SDK，不修改 Hermes 核心依赖或原有安全默认值。
在当前配置档启用插件、设置模型并提供具备 Copilot 权限的令牌后使用；
已有 `copilot` 与 `copilot-acp` 不受影响。

推荐模型为 `gpt-6-astra`，需要换模型时仍选择账号可用的 GPT-6 系列。
Windows 本机可运行 `& "$HOME\.hermes\profiles\copilot-sdk\start.ps1"`
打开已配置的终端聊天；这不是网页服务。独立配置档和凭据保留在本机，
不会上传到仓库。此前真实推理与文件工具调用已成功，但发生在切换 GPT-6
之前，不能据此宣称 Windows 上的 GPT-6 模型已完成真实运行验证。Linux 上现已
完成 GPT-6 Astra 的 SDK 与 Hermes 单次对话验证，以及 Telegram 连接和 Google
只读访问验证；完整操作步骤见上方 Linux 指南。

SDK 不直接执行工具，工具请求仍由 Hermes 校验、执行和审批。当前为实验性
纯文本兼容层，暂不支持图片、原生结构化输出、实时 token 流或用量统计。
独立存储及空模式不是操作系统沙箱；详细安装、隔离边界和测试见插件仓库。
