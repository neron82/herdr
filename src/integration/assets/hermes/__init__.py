"""Hermes plugin installed by Herdr to report resumable session identity."""

# HERDR_INTEGRATION_ID=hermes
# HERDR_INTEGRATION_VERSION=5

from __future__ import annotations

import os
import subprocess
import time

_SOURCE = "herdr:hermes"
_AGENT = "hermes"
# Hermes runs its chat loop as platform "local" (gateway-managed sessions,
# including pane-attached CLI clients), and the plain CLI surface passes an
# empty platform; both are interactive and pane-bound reports must pass.
_INTERACTIVE_PLATFORMS = {"cli", "tui", "desktop", "acp", "local", ""}


def _pane_id() -> str | None:
    if os.environ.get("HERDR_ENV") != "1":
        return None
    return os.environ.get("HERDR_PANE_ID", "").strip() or None


def _send_session(session_id: str, start_source: str) -> None:
    pane_id = _pane_id()
    if pane_id is None:
        return
    command = [
        os.environ.get("HERDR_BIN_PATH") or "herdr",
        "pane",
        "report-agent-session",
        pane_id,
        "--source",
        _SOURCE,
        "--agent",
        _AGENT,
        "--seq",
        str(time.time_ns()),
        "--agent-session-id",
        session_id,
        "--session-start-source",
        start_source,
    ]
    try:
        kwargs = {"timeout": 1, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        subprocess.run(command, check=False, **kwargs)
    except Exception:
        pass


def _platform(kwargs: dict) -> str:
    # Hermes CLI leaves agent.platform unset and its lifecycle hooks pass ""
    # (conversation_loop passes `getattr(agent, "platform", None) or ""`),
    # while the engine-hook path normalizes the same attribute to "cli"
    # (agent_init). Inside a Herdr pane the surface is interactive by
    # definition, so an empty platform must be treated as the CLI surface;
    # truthy non-interactive values (cron, subagent, gateway channels) stay
    # filtered out.
    platform = kwargs.get("platform") or ""
    if not platform and os.environ.get("HERDR_ENV") == "1":
        platform = "cli"
    return platform


def _report_session(start_source: str, **kwargs) -> None:
    if _platform(kwargs) not in _INTERACTIVE_PLATFORMS:
        return
    session_id = kwargs.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return
    _send_session(session_id, start_source)


def _session_started(**kwargs) -> None:
    _report_session("startup", **kwargs)


def _session_reset(**kwargs) -> None:
    _report_session("new", **kwargs)


def _session_observed(**kwargs) -> None:
    if kwargs.get("platform") == "cli":
        _report_session("resume", **kwargs)


def register(ctx):
    ctx.register_hook("on_session_start", _session_started)
    ctx.register_hook("on_session_reset", _session_reset)
    ctx.register_hook("pre_llm_call", _session_observed)
