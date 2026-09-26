---
title: Hermes coordinator with Copilot CLI workers
description: Delegate local jobs directly to Copilot CLI without a Copilot SDK layer.
---

# Hermes coordinator with Copilot CLI workers

The current architecture makes **Hermes the coordinator** and **Copilot CLI the
local worker**. It replaces the experimental SDK text-provider bridge, which
deliberately disabled native tools and started every completion in a temporary
directory.

```text
User -> Hermes gateway and conversation
        -> native copilot provider -> GPT-6 Astra / Responses API
        -> copilot_cli tool -> separate local Copilot CLI process
                            <- result or clarification question
        <- Hermes background ledger / completion queue
User <- Hermes reply

Answer -> Hermes -> resume the worker's CLI session in a new process
Schedule -> Hermes cron -> Hermes -> foreground CLI job -> cron delivery
```

Hermes retains conversation history, plans, approvals, skills, scheduling and
channel delivery. Copilot handles the details of each bounded job. There is no SDK
coordinator, SDK provider or SDK runtime in this request path.

## Install and configure

Install [hermes-copilot-cli](https://github.com/Chibaheit/hermes-copilot-cli) in
Hermes' Python environment, plus the standalone Copilot CLI. The initial supported
deployment is Linux/POSIX with CLI 1.0.88's JSONL protocol.

```sh
git clone --depth 1 https://github.com/Chibaheit/hermes-copilot-cli.git ~/Repos/hermes-copilot-cli
uv pip install --python ~/Repos/hermes-agent/venv/bin/python -e ~/Repos/hermes-copilot-cli
```

Merge these settings into the active profile, preserving unrelated entries:

```yaml
model:
  provider: copilot
  default: gpt-6-astra
  base_url: https://api.githubcopilot.com
  api_mode: codex_responses
plugins:
  enabled:
    - copilot-cli
  entries:
    copilot-cli:
      settings:
        executable: /home/YOUR_USER/.local/bin/copilot
        workspace: /home/YOUR_USER/Repos
        model: gpt-6-astra
        permissions: read-only
        timeout_seconds: 900
        max_workers: 3
platform_toolsets:
  cli: [hermes-cli, copilot-cli]
  telegram: [hermes-telegram, copilot-cli]
```

Append `copilot-cli` to each enabled channel's existing toolsets, preserving
other tools. Explicit `--toolsets` selections must include it too. The tool
can be deferred behind Hermes' normal tool-search mechanism.

Use `COPILOT_GITHUB_TOKEN` in the profile's `.env`; never put credentials in YAML
or Git. Workers receive only the owning profile's explicit token and private CLI
configuration. GPT-6 Astra does **not** support `/chat/completions`; the
`codex_responses` mode is required.

Add the standing coordinator instructions from the plugin README to the profile's
`SOUL.md`, preserving its persona. Restart Hermes after changing discovery,
provider or system-prompt settings.

## Migrating the old SDK deployment

Replace `copilot-sdk` with `copilot-cli` in `plugins.enabled`, delete the
`copilot_sdk` section, and replace the model fields above. Then remove the obsolete
Python packages from the Hermes environment:

```sh
uv pip uninstall --python ~/Repos/hermes-agent/venv/bin/python \
  hermes-copilot-sdk github-copilot-sdk
hermes gateway restart
```

Do not delete other applications' SDK environments, old source checkouts,
credentials, Telegram pairing or Google Workspace state. The
[Linux deployment guide](./copilot-sdk-telegram-gog.md) retains its historical URL
but now describes direct CLI workers.

## Results, questions and scheduled jobs

The `copilot_cli` tool offers `run`, `status`, `reply` and `cancel`.
Async-capable channels get an immediate job ID, followed by a fresh Hermes turn
containing the result. `needs_input` is relayed as a user question; `reply`
continues the same CLI session. Duplicate replies are rejected.

Hermes cron remains the scheduler. Scheduled prompts invoke the worker with
`background=false`, so the existing cron runner waits for the actual result and
delivers it to the configured channel. One-shot/non-async surfaces also run
inline rather than promising an undeliverable notification.

Worker state and logs are private under `$HERMES_HOME/copilot-cli/<job-id>/`.
Errors, deadlines, cancellation and unknown outcomes after crashes are explicit.
Logs are retained locally and may contain sensitive task content.

## Permission boundary

The default is **read-only investigation** with native CLI `view`, `rg` and `glob`.
Shell, writes, web tools, nested delegation and MCP tools are not exposed.
Working directories must resolve inside the configured workspace.

Only an operator should enable `permissions: workspace`. It allows local file
editing and unattended shell execution, without granting all paths/URLs. This is
**not an OS sandbox**: shell commands still have the service account's privileges.
Worker restrictions must not be bypassed using a different Hermes tool.

## Verification scope

On Sat, 2026-09-26, native GPT-6 Astra Responses API inference, direct CLI file
reading, and a real clarification/resume round trip succeeded without using the
SDK. The plugin suite also exercises actual subprocesses, real Hermes discovery,
background persistence/delivery routing, cancellation, timeouts and profile
boundaries. Live messaging delivery requires a separately observed channel round
trip; process startup alone does not establish it.
