"""Pure gate decision logic for the maintenance edge proxy (stdlib-only)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


FLAG_NAME = "UPDATE_IN_PROGRESS"

# Paths that must always reach the API (deploy health + self-poll).
ALWAYS_PASS_PREFIXES = (
    "/health",
    "/api/v1/site-status",
)

# Local liveness for the maintenance container itself (not proxied).
LOCAL_ALIVE_PATH = "/_maintenance/alive"


@dataclass(frozen=True)
class GateDecision:
    gated: bool
    reason: str | None
    message: str | None
    title: str


def flag_path(flags_dir: str | Path) -> Path:
    return Path(flags_dir) / FLAG_NAME


def deploy_flag_active(flags_dir: str | Path) -> bool:
    path = flag_path(flags_dir)
    try:
        return path.is_file()
    except OSError:
        return False


def should_always_pass(path: str, method: str = "GET") -> bool:
    if method.upper() not in {"GET", "HEAD"}:
        return False
    for prefix in ALWAYS_PASS_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return False


def decide_gate(
    *,
    flag_active: bool,
    status: dict[str, Any] | None,
    status_fetch_ok: bool,
    upstream_reachable: bool | None = None,
) -> GateDecision:
    """
    Decide whether to serve the maintenance page.

    Priority: deploy flag → API maintenance.active → unreachable status/upstream.
    """
    if flag_active:
        return GateDecision(
            gated=True,
            reason="deploy",
            message="We're deploying changes right now. Please come back in a few minutes.",
            title="Site update in progress",
        )

    if status_fetch_ok and isinstance(status, dict):
        maintenance = status.get("maintenance") or {}
        if maintenance.get("active"):
            message = (
                maintenance.get("message")
                or "The site is temporarily offline for maintenance. Please come back later."
            )
            reason = maintenance.get("reason") or "scheduled"
            title = (
                "Scheduled maintenance"
                if reason in {"scheduled", "manual"}
                else "Site temporarily unavailable"
            )
            return GateDecision(
                gated=True,
                reason=str(reason),
                message=str(message),
                title=title,
            )
        if upstream_reachable is False:
            return GateDecision(
                gated=True,
                reason="upstream",
                message="The site is temporarily unreachable. Please try again shortly.",
                title="Site temporarily unavailable",
            )
        return GateDecision(gated=False, reason=None, message=None, title="")

    # API status unreachable: fail closed so users don't hit 502 mid-outage.
    return GateDecision(
        gated=True,
        reason="status_unreachable",
        message="The site is temporarily unavailable. Please come back later.",
        title="Site temporarily unavailable",
    )


def render_maintenance_html(template: str, decision: GateDecision) -> str:
    html = template
    title = decision.title or "Site update in progress"
    message = decision.message or "Please come back later."
    html = _replace_marker(html, "TITLE", title)
    html = _replace_marker(html, "MESSAGE", message)
    detail = ""
    if decision.reason and decision.reason not in {"deploy", "status_unreachable"}:
        detail = f'<p class="detail">{_escape(message)}</p>'
    html = html.replace("<!--DETAIL-->", detail)
    return html


def _replace_marker(html: str, name: str, value: str) -> str:
    start = f"<!--{name}-->"
    end = f"<!--/{name}-->"
    i = html.find(start)
    j = html.find(end)
    if i < 0 or j < 0 or j < i:
        return html
    return html[: i + len(start)] + _escape(value) + html[j:]


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
