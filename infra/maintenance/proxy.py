#!/usr/bin/env python3
"""Maintenance gate for Caddy forward_auth (no reverse-proxy of app traffic).

Caddy asks GET /_maintenance/auth before proxying to api/web. When gated we
return 503 + HTML; when open we return 200. That keeps reverse_proxy in Caddy
and avoids the HTTP/1.1 buffering 502s from the previous Python middlebox.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from gate import (
    LOCAL_ALIVE_PATH,
    LOCAL_AUTH_PATH,
    decide_gate,
    deploy_flag_active,
    render_maintenance_html,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [maintenance] %(message)s",
)
logger = logging.getLogger("maintenance")

LISTEN_HOST = os.environ.get("LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "8080"))
FLAGS_DIR = os.environ.get("FLAGS_DIR", "/var/maintenance/flags")
STATUS_URL = os.environ.get("STATUS_URL", "http://api:8000/api/v1/site-status")
POLL_INTERVAL_SEC = float(os.environ.get("POLL_INTERVAL_SEC", "15"))
TEMPLATE_PATH = Path(os.environ.get("TEMPLATE_PATH", "/app/index.html"))

_state_lock = threading.Lock()
_cached_status: dict[str, Any] | None = None
_status_fetch_ok = False
_last_decision_reason: str | None = None


def _load_template() -> str:
    try:
        return TEMPLATE_PATH.read_text(encoding="utf-8")
    except OSError:
        return (
            "<!DOCTYPE html><html><head><title>Maintenance</title></head>"
            "<body><h1><!--TITLE-->Maintenance<!--/TITLE--></h1>"
            "<p><!--MESSAGE-->Please come back later.<!--/MESSAGE--></p>"
            "<!--DETAIL--></body></html>"
        )


TEMPLATE = _load_template()


def _fetch_status() -> tuple[dict[str, Any] | None, bool]:
    try:
        req = urllib.request.Request(STATUS_URL, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body)
            if isinstance(data, dict):
                return data, True
            return None, False
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        logger.warning("site-status poll failed: %s", exc)
        return None, False


def _poll_loop() -> None:
    global _cached_status, _status_fetch_ok, _last_decision_reason
    while True:
        status, ok = _fetch_status()
        flag = deploy_flag_active(FLAGS_DIR)
        decision = decide_gate(
            flag_active=flag,
            status=status,
            status_fetch_ok=ok,
            upstream_reachable=True if ok else None,
        )
        with _state_lock:
            if ok:
                _cached_status = status
            _status_fetch_ok = ok
            if decision.reason != _last_decision_reason:
                logger.info(
                    "gate=%s reason=%s",
                    decision.gated,
                    decision.reason,
                )
                _last_decision_reason = decision.reason
        time.sleep(POLL_INTERVAL_SEC)


def _current_gate(*, force_refresh: bool = False):
    flag = deploy_flag_active(FLAGS_DIR)
    with _state_lock:
        status = _cached_status
        ok = _status_fetch_ok
    if force_refresh or (not ok and not flag):
        status, ok = _fetch_status()
        with _state_lock:
            if ok:
                _cached_status = status
            _status_fetch_ok = ok
    return decide_gate(
        flag_active=flag,
        status=status,
        status_fetch_ok=ok,
        upstream_reachable=True if ok else None,
    )


def _send(
    handler: BaseHTTPRequestHandler,
    *,
    status: int,
    body: bytes,
    content_type: str,
    extra_headers: dict[str, str] | None = None,
) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Connection", "close")
    if extra_headers:
        for key, value in extra_headers.items():
            handler.send_header(key, value)
    handler.end_headers()
    if handler.command != "HEAD":
        handler.wfile.write(body)


def _serve_auth(handler: BaseHTTPRequestHandler) -> None:
    """Caddy forward_auth: 2xx = allow; otherwise Caddy returns this response."""
    decision = _current_gate()
    if not decision.gated:
        _send(
            handler,
            status=200,
            body=b'{"gated":false}\n',
            content_type="application/json",
            extra_headers={"X-Maintenance-Gate": "open"},
        )
        return
    html = render_maintenance_html(TEMPLATE, decision).encode("utf-8")
    _send(
        handler,
        status=503,
        body=html,
        content_type="text/html; charset=utf-8",
        extra_headers={
            "Retry-After": "30",
            "X-Maintenance-Gate": decision.reason or "gated",
        },
    )


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.info("%s - " + fmt, self.address_string(), *args)

    def _handle(self) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path or "/"
        if path == LOCAL_ALIVE_PATH:
            _send(
                self,
                status=200,
                body=b'{"status":"ok"}\n',
                content_type="application/json",
            )
            return
        if path == LOCAL_AUTH_PATH:
            _serve_auth(self)
            return
        # Direct hits (debugging): same as auth.
        if path in {"/", "/index.html"}:
            _serve_auth(self)
            return
        _send(
            self,
            status=404,
            body=b'{"error":"not_found"}\n',
            content_type="application/json",
        )

    def do_GET(self) -> None:
        self._handle()

    def do_HEAD(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        # forward_auth uses GET by default; accept POST for probes.
        self._handle()


def main() -> None:
    Path(FLAGS_DIR).mkdir(parents=True, exist_ok=True)
    poller = threading.Thread(target=_poll_loop, name="status-poller", daemon=True)
    poller.start()
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    logger.info(
        "listening on %s:%s (forward_auth gate) status=%s flags=%s",
        LISTEN_HOST,
        LISTEN_PORT,
        STATUS_URL,
        FLAGS_DIR,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
