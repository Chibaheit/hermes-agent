from types import SimpleNamespace

import pytest
import yaml

from gateway.config import Platform
from gateway.run_notifications import GatewayNotificationsMixin
from gateway.session import SessionSource
from gateway.session_context import clear_session_vars, set_session_vars
from tools.workflow_policy import bind_workflow_event, current_workflow_owner, set_workflow_owner


@pytest.mark.asyncio
async def test_completion_identity_not_borrowed_from_cached_conversation(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(yaml.safe_dump({
        "approvals": {"auto_approve_owners": ["telegram:101"]},
    }))
    received = []

    class Adapter:
        supports_async_delivery = True

        async def handle_message(self, event):
            received.append(event)
            event._gateway_accepted = True

    adapter = Adapter()
    # Delivery points at the owner's conversation, even for another creator's completion.
    source = SessionSource(platform=Platform.TELEGRAM, chat_id="shared", user_id="101")

    class Runner(GatewayNotificationsMixin):
        def _build_process_event_source(self, evt):
            return source

        def _resolve_injection_adapter(self, platform_name, source=None):
            return adapter

    runner = Runner()
    for owner, expected in (("telegram:101", True), ("telegram:202", False), ("", False)):
        evt = {"type": "async_delegation", "session_key": "agent:main:telegram:group:shared",
               "workflow_owner": owner}
        assert await runner._inject_watch_notification("result", evt)
        tokens = set_session_vars(platform="telegram", user_id="101")
        try:
            note = bind_workflow_event(received[-1])
            assert bool(note) is expected
            assert current_workflow_owner() == owner
        finally:
            clear_session_vars(tokens)
    owned = {"session_key": "shared", "workflow_owner": "telegram:101"}
    other = {"session_key": "shared", "workflow_owner": "telegram:202"}
    assert runner._event_route_key(owned, runner._COMPLETION_BATCH_KEY_FIELDS) != (
        runner._event_route_key(other, runner._COMPLETION_BATCH_KEY_FIELDS))


def test_terminal_notifications_preserve_captured_owner(tmp_path, monkeypatch):
    from tools.process_registry import ProcessRegistry, ProcessSession
    from tools.terminal_tool_background import _stamp_gateway_routing, _register_completion_watcher
    from gateway.session_context import get_session_env

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    tokens = set_session_vars(platform="telegram", user_id="101", session_key="shared")
    try:
        set_workflow_owner("telegram:101")
        session = ProcessSession(id="proc_test", command="true", task_id="test", session_key="shared")
        _stamp_gateway_routing(session, get_session_env)
        set_workflow_owner("telegram:202")
        event = ProcessRegistry._watch_event_base(session)
        assert event["workflow_owner"] == "telegram:101"
        registry = SimpleNamespace(pending_watchers=[])
        _register_completion_watcher(registry, session, "shared")
        watcher = registry.pending_watchers[0]
        completion = GatewayNotificationsMixin._build_process_completion_event(watcher, session, session.id)
        assert completion["workflow_owner"] == "telegram:101"
    finally:
        clear_session_vars(tokens)
