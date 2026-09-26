"""Creator-bound execution authority, separate from conversation/delivery identity."""

from contextvars import ContextVar
import logging
import re

logger = logging.getLogger(__name__)
_owner: ContextVar[str] = ContextVar("workflow_owner", default="")


def normalize_workflow_owner(value) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"telegram:[1-9][0-9]*", value):
        return ""
    return value


def current_workflow_owner() -> str:
    return _owner.get()


def set_workflow_owner(value) -> None:
    _owner.set(normalize_workflow_owner(value))


def owner_from_event(event) -> str:
    if event.internal:
        return normalize_workflow_owner((event.metadata or {}).get("_workflow_owner"))
    source = event.source
    platform = getattr(source.platform, "value", source.platform)
    return normalize_workflow_owner(f"{platform}:{source.user_id}")


def workflow_auto_approved() -> bool:
    owner = current_workflow_owner()
    if not owner:
        return False
    from tools.approval_context import _get_approval_config

    owners = _get_approval_config().get("auto_approve_owners", [])
    if not isinstance(owners, list) or any(not normalize_workflow_owner(v) for v in owners):
        logger.warning("approvals.auto_approve_owners must be a list of telegram:<numeric-user-id> principals")
        return False
    return owner in owners


def bind_workflow_event(event) -> str:
    set_workflow_owner(owner_from_event(event))
    if not workflow_auto_approved():
        return ""
    return (
        "[Workflow execution policy: the authenticated creator has preauthorized routine "
        "execution and continuation of this requested workflow. Proceed without asking for "
        "the same permission again. Copilot worker permissions are enforced by the tool. "
        "Still stop for missing credentials, OS privileges, genuinely missing information, "
        "or work outside the requested scope.]"
    )


def stamp_cron_owner(job: dict) -> None:
    if owner := current_workflow_owner():
        job["workflow_owner"] = owner


def revoke_changed_cron_owner(job: dict, updated: dict, updates: dict) -> None:
    # A different actor must not turn the creator's preauthorization into arbitrary execution.
    execution_fields = {
        "prompt", "script", "skill", "skills", "no_agent", "monitor_script", "monitor_url",
        "context_from", "workdir", "enabled_toolsets", "model", "provider", "base_url",
        "schedule", "deliver", "failure_deliver", "origin", "reasoning_effort",
    }
    owner = normalize_workflow_owner(job.get("workflow_owner"))
    if owner and owner != current_workflow_owner() and execution_fields.intersection(updates):
        updated.pop("workflow_owner", None)
        logger.warning("Revoked creator approval for cron job %s after an edit by another or unknown actor", job["id"])
