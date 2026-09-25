---
title: Linux setup with Copilot SDK, Telegram, and gog
description: Reproduce a headless Hermes deployment with a paired Telegram bot and Google Workspace access.
---

# Linux setup with Copilot SDK, Telegram, and gog

This is the setup validated on Fri, 2026-09-25. It uses the fork's existing
plugin, platform, and skill extension points; no Hermes core changes are needed.
The primary user interface is Telegram, not an interactive Hermes terminal.

## Data flow and local state

```text
Approved Telegram user
  -> Telegram bot -> Hermes gateway -> Copilot SDK plugin -> GPT-6 Astra
  <- Telegram reply <- Hermes tool loop <- model response
                            |
                            +-> gog skill -> terminal -> gog -> Google APIs
```

Hermes owns tool execution and approvals. The SDK's native tools are disabled.
See [Copilot SDK](./copilot-sdk.md) for the text-only adapter's limitations.
Google OAuth consent is separate from Copilot authentication and Telegram pairing.
Only authorize the Google services you intend the agent to use. Retrieved Google
content can enter the Hermes/model conversation; authorization is not a promise
that content stays local.

| Location | Purpose | Commit to Git? |
| --- | --- | --- |
| `~/Repos/hermes-agent` | Fork source and isolated `venv` | Source/docs only |
| `~/Repos/hermes-copilot-sdk` | External provider plugin source | Source only |
| `~/.local/bin/hermes` | Launcher pointing at the fork's venv | No |
| `~/.hermes/config.yaml` | Provider and behavior settings | Sanitized examples only |
| `~/.hermes/.env` | Copilot/Telegram tokens and gog keyring password | Never |
| `~/.hermes/skills/productivity/gog` | Installed, scanned upstream skill | Restore from source |
| `~/.config/gogcli`, `~/.local/share/gogcli` | gog config, OAuth client metadata, encrypted token storage | Never |
| `~/.config/systemd/user/hermes-gateway.service` | Persistent user gateway | Regenerate on the host |

The commands below target the **default Linux profile**. Run them as the same
non-root user who owns the gateway. Named profiles need their own Hermes home,
secrets, skills, service, and explicitly isolated gog storage. Do not reuse this
default-profile recipe unchanged for a multiplexed deployment.

## 1. Install the fork and external dependencies

Prerequisites: Git, curl, tar, GitHub CLI (`gh`) authenticated for the repositories,
and `uv` on `PATH`. Install uv from https://docs.astral.sh/uv/getting-started/installation/
if missing. Keep `~/.local/bin` on `PATH`.

For fresh checkouts:

```bash
mkdir -p ~/Repos ~/.local/bin
git clone --depth 1 https://github.com/Chibaheit/hermes-agent.git ~/Repos/hermes-agent
git clone --depth 1 https://github.com/Chibaheit/hermes-copilot-sdk.git ~/Repos/hermes-copilot-sdk
cd ~/Repos/hermes-agent
UV_PROJECT_ENVIRONMENT=venv uv sync --locked --extra all --python 3.11
uv pip install --python venv/bin/python \
  "git+https://github.com/Chibaheit/hermes-copilot-sdk.git@ed22b3c9822236fb3109ccc3c5d321342c62d44a" \
  "python-telegram-bot[webhooks]==22.8"
venv/bin/python -m copilot download-runtime
```

The verified baseline was Hermes `82bcaa40de4e6bf99b8d148e23cedc5ce4155dae`
(0.21.3), Python 3.11.16, plugin 0.1.0, SDK 1.0.14, and SDK runtime 1.0.85.
The initial setup installed the plugin editable from the checkout at the pinned
commit; the command above pins the same source without relying on a moving branch.
Do not substitute the interactive Copilot CLI for the SDK's matching runtime.

Before replacing an existing `hermes` launcher, preserve it under an unused backup
name (the validated host used `hermes-pre-fork`). Then:

```bash
ln -sfn "$HOME/Repos/hermes-agent/venv/bin/hermes" "$HOME/.local/bin/hermes"
hermes --version
uv pip check --python ~/Repos/hermes-agent/venv/bin/python
```

Confirm the install directory points to `~/Repos/hermes-agent`. Keep an existing
`~/.hermes` intact; do not overwrite it with templates. A later exact `uv sync`
can remove externally installed packages, so reinstall the pinned plugin and
Telegram dependency afterward and recheck imports before restarting the gateway.

## 2. Configure Copilot SDK and verify inference

Merge the config from [Copilot SDK setup](./copilot-sdk.md#setup), retaining all
existing enabled plugins. The required values are:

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

Use the following in a **trusted local terminal** to enter the Copilot credential
without placing it in shell history or command arguments:

```bash
~/Repos/hermes-agent/venv/bin/python - <<'PY'
from getpass import getpass
from hermes_cli.config import save_env_value_secure
token = getpass("GitHub credential with Copilot access: ")
if not token.strip():
    raise SystemExit("No credential supplied")
save_env_value_secure("COPILOT_GITHUB_TOKEN", token)
PY
```

An existing authenticated GitHub CLI credential worked on the validated host,
but not every GitHub token has Copilot access. The plugin does not automatically
reuse `gh` or interactive Copilot login. Verify authorized model discovery and
actual inference; executable availability alone does not establish authentication.
Do not silently fall back from GPT-6 to another model family.

```bash
hermes chat --cli --oneshot --ignore-rules -Q --max-turns 2 \
  --run-budget 90 -q 'Reply with exactly HERMES_READY. Do not use tools.'
```

Expected response: `HERMES_READY`. This is a setup probe, not the normal UI.

## 3. Connect Telegram and restrict access

Reuse an existing bot or create one through https://t.me/BotFather. Enter its
token locally through `hermes gateway setup`; never put it in repository files,
chat, shell arguments, or screenshots. Stop another deployment polling the same
bot before starting this one. An existing webhook also needs an intentional
migration; do not silently remove it.

Keep unrestricted access disabled. Either configure an explicit allowed-user
list or use DM pairing. With no allowlist, unknown DM senders can receive a code,
but cannot use the agent until the operator approves it.

On a host with a working systemd user manager:

```bash
hermes gateway install --force --start-now --start-on-login
systemctl --user enable hermes-gateway.service
hermes gateway status
systemctl --user is-enabled hermes-gateway.service
```

The explicit enable is intentional: an already-installed unit was left disabled
by an install invocation without `--force` during setup. Check actual state, not
just the install command's success. Enable user lingering, if needed and permitted,
with `loginctl enable-linger "$USER"` so the service survives logout.

DM the bot, then approve only the code supplied by the intended user:

```bash
hermes pairing approve telegram PAIRING_CODE
hermes pairing list
```

Send another message after approval. Verify Telegram reports `connected` in the
local gateway state, not merely that systemd has spawned a Python process.

## 4. Install gog and its Hermes skill

The validated binary is `gog` v0.41.0 for Linux x86-64. Use a fresh temporary
directory, verify the release checksum, then install only the binary:

```bash
download_dir="$(mktemp -d)"
gh release download v0.41.0 --repo openclaw/gogcli \
  --pattern gogcli_0.41.0_linux_amd64.tar.gz --pattern checksums.txt \
  --dir "$download_dir"
(
  cd "$download_dir" &&
  grep 'gogcli_0.41.0_linux_amd64.tar.gz' checksums.txt | sha256sum -c - &&
  tar -xzf gogcli_0.41.0_linux_amd64.tar.gz ./gog &&
  install -m 755 gog "$HOME/.local/bin/gog"
)
gog --version
hermes skills install openclaw/openclaw/skills/gog --category productivity --yes
hermes skills list --source hub --enabled-only
```

Use the matching release asset on other architectures. Remove the named download
files and empty temporary directory after success. Do not bypass a blocked skill
scan with `--force`. The installed skill was scanned SAFE from upstream commit
`9fdb24bbccc7c7aae063edc6b2851736d6726db2`; future upstream versions must be rescanned.
No vendor skill copy is added to Hermes core.

Ensure `gog` is on the gateway's `PATH`, not just an interactive shell's path.
Load the skill through Hermes' `skill_view` for Google Workspace scenarios and use
`terminal` to execute it. Prefer `--json --no-input --readonly` for read requests.
Sending mail, modifying events, sharing files, or deleting data requires user
authorization; OAuth scopes alone are not permission to perform those actions.

## 5. Configure headless Google OAuth

```bash
gog auth keyring file
~/Repos/hermes-agent/venv/bin/python - <<'PY'
import os
import secrets
from hermes_cli.env_loader import load_hermes_dotenv
from hermes_cli.config import save_env_value_secure
load_hermes_dotenv()
if not os.environ.get("GOG_KEYRING_PASSWORD"):
    save_env_value_secure("GOG_KEYRING_PASSWORD", secrets.token_urlsafe(48))
PY
```

Do not replace an existing keyring password: it is needed to decrypt stored
credentials. Back it up with local secrets, separately from Git. The gateway
loads it through Hermes' `.env`; standalone commands need the same environment.

Create or reuse a **Desktop app** OAuth client:
https://console.cloud.google.com/apis/credentials

Download its JSON to a private local location. Enable the APIs for the requested
services in that same Google Cloud project. OAuth consent does **not** enable
APIs. If the consent app is in testing, add the intended account as a test user;
check Google's testing-mode refresh-token expiry rules for unattended operation.

In a trusted local shell (replace the path and example account):

```bash
uv run --no-project --env-file ~/.hermes/.env -- \
  gog auth credentials set /path/to/client_secret.json
uv run --no-project --env-file ~/.hermes/.env -- \
  gog auth add you@example.com \
  --services gmail,calendar,drive,contacts,docs,sheets,tasks \
  --remote --step 1 --json --no-input
```

Open the printed `auth_url` and approve the intended account/scopes. A localhost
connection error after consent is expected with this two-step remote flow. Paste
the full resulting callback URL **only into a trusted terminal**, not Telegram or
an agent conversation:

```bash
uv run --no-project --env-file ~/.hermes/.env -- \
  gog auth add you@example.com \
  --services gmail,calendar,drive,contacts,docs,sheets,tasks \
  --remote --step 2 --auth-url 'CALLBACK_URL'
```

Keep the account, services, client, storage context, and redirect options identical
between steps. Restart from step 1 if state or code expires. Never commit an
authorization URL containing live state, callback code, client secret, or token.
Rotate any secret exposed during interactive setup.

## 6. Verify and hand off

```bash
uv run --no-project --env-file ~/.hermes/.env -- gog auth list --check --json --no-input
uv run --no-project --env-file ~/.hermes/.env -- gog auth doctor --check --json --no-input
hermes gateway restart
hermes gateway status
```

Read each account's `valid` field and doctor's individual checks; an exit code
alone can conceal warnings. Restart gracefully when no turn is in flight. Begin
a new Telegram conversation with `/new` to load the new skill instructions without
changing an existing conversation's cached prompt.

| Probe | Expected result | Setup evidence |
| --- | --- | --- |
| Hermes version and `uv pip check` | Fork path; compatible environment | Passed |
| SDK model discovery and one-shot chat | GPT-6 Astra available; `HERMES_READY` | Passed |
| Telegram state, pairing, systemd enablement | Connected; intended user approved; enabled | Passed |
| Hermes skill listing and `skill_view(name="gog")` | Enabled skill loads | Passed |
| gog auth list and doctor | Valid token; encrypted keyring readable; refresh succeeds | Passed |
| `gog --readonly --json --no-input --account you@example.com gmail search 'newer_than:1d' --max 1` | Read succeeds | Passed after Gmail API enablement |
| `gog --readonly --json --no-input --account you@example.com calendar events --today --max 1` | Read succeeds | Passed |
| `gog --readonly --json --no-input --account you@example.com drive ls --max 1` | Read succeeds | Passed after Drive API enablement |
| Contacts, Docs, Sheets, Tasks | Corresponding APIs work when enabled | OAuth scopes granted; API calls not tested |
| Telegram-triggered Google tool round trip | Bot reads requested data and replies | Not recorded during setup |

Run gog probes through the same `uv run --no-project --env-file ~/.hermes/.env --`
prefix. Do not publish returned mail, events, file names, or logs containing them.
For API-disabled errors, enable the named API in the OAuth client's project and
retry; do not repeatedly reauthorize a valid account.
