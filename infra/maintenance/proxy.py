#!/usr/bin/env python3
"""Maintenance edge proxy: gate on deploy flag / site-status, else reverse-proxy."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from http.client import HTTPConnection, HTTPSConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from gate import (
    LOCAL_ALIVE_PATH,
    decide_gate,
    deploy_flag_active,
    render_maintenance_html,
    should_always_pass,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [maintenance] %(message)s",
)
logger = logging.getLogger("maintenance")

LISTEN_HOST = os.environ.get("LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "8080"))
FLAGS_DIR = os.environ.get("FLAGS_DIR", "/var/maintenance/flags")
STATUS_URL = os.environ.get(
    "STATUS_URL", "http://api:8000/api/v1/site-status"
)
API_UPSTREAM = os.environ.get("API_UPSTREAM", "http://api:8000").rstrip("/")
WEB_UPSTREAM = os.environ.get("WEB_UPSTREAM", "http://web:80").rstrip("/")
POLL_INTERVAL_SEC = float(os.environ.get("POLL_INTERVAL_SEC", "15"))
TEMPLATE_PATH = Path(
    os.environ.get("TEMPLATE_PATH", "/app/index.html")
)

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


def _pick_upstream(path: str) -> str:
    if (
        path.startswith("/api/")
        or path.startswith("/docs")
        or path.startswith("/redoc")
        or path == "/openapi.json"
        or path.startswith("/openapi.json?")
        or path == "/health"
        or path.startswith("/health?")
    ):
        return API_UPSTREAM
    return WEB_UPSTREAM


_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "proxy-connection",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def _proxy(handler: BaseHTTPRequestHandler) -> None:
    parsed_req = urlsplit(handler.path)
    path = parsed_req.path or "/"
    upstream_base = _pick_upstream(path)
    upstream = urlsplit(upstream_base)
    target_path = handler.path
    headers = {
        k: v
        for k, v in handler.headers.items()
        if k.lower() not in _HOP_BY_HOP and k.lower() != "host"
    }
    # Prefer hostname without default port — some upstreams reject Host: web:80.
    if upstream.hostname:
        default_port = 443 if upstream.scheme == "https" else 80
        port = upstream.port or default_port
        headers["Host"] = (
            upstream.hostname
            if port == default_port
            else f"{upstream.hostname}:{port}"
        )
    body = b""
    length = int(handler.headers.get("Content-Length") or 0)
    if length > 0:
        body = handler.rfile.read(length)
    if body:
        headers["Content-Length"] = str(len(body))
    else:
        headers.pop("Content-Length", None)

    conn: HTTPConnection | HTTPSConnection
    if upstream.scheme == "https":
        conn = HTTPSConnection(upstream.hostname, upstream.port or 443, timeout=120)
    else:
        conn = HTTPConnection(upstream.hostname, upstream.port or 80, timeout=120)
    try:
        conn.request(handler.command, target_path, body=body or None, headers=headers)
        resp = conn.getresponse()
        resp_body = resp.read()
        handler.send_response(resp.status)
        for key, value in resp.getheaders():
            if key.lower() in _HOP_BY_HOP or key.lower() == "content-length":
                continue
            handler.send_header(key, value)
        # Always set Content-Length after buffering. Upstream may have used
        # Transfer-Encoding: chunked; without a length, HTTP/1.1 keep-alive
        # responses confuse Caddy into returning 502.
        handler.send_header("Content-Length", str(len(resp_body)))
        handler.send_header("Connection", "close")
        handler.end_headers()
        if handler.command != "HEAD":
            handler.wfile.write(resp_body)
    except Exception as exc:
        logger.warning("upstream proxy error: %s", exc)
        try:
            decision = decide_gate(
                flag_active=True,
                status=None,
                status_fetch_ok=False,
            )
            _serve_maintenance(handler, decision)
        except Exception as inner:
            logger.exception("failed to serve maintenance fallback: %s", inner)
    finally:
        conn.close()


def _serve_maintenance(handler: BaseHTTPRequestHandler, decision) -> None:
    html = render_maintenance_html(TEMPLATE, decision).encode("utf-8")
    handler.send_response(503)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(html)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Retry-After", "30")
    handler.send_header("Connection", "close")
    handler.end_headers()
    if handler.command != "HEAD":
        handler.wfile.write(html)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.info("%s - " + fmt, self.address_string(), *args)

    def _handle(self) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path or "/"
        if path == LOCAL_ALIVE_PATH:
            body = b'{"status":"ok"}\n'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
            return
        if should_always_pass(path, self.command):
            _proxy(self)
            return
        decision = _current_gate()
        if decision.gated:
            _serve_maintenance(self, decision)
            return
        _proxy(self)

    def do_GET(self) -> None:
        self._handle()

    def do_HEAD(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def do_PUT(self) -> None:
        self._handle()

    def do_PATCH(self) -> None:
        self._handle()

    def do_DELETE(self) -> None:
        self._handle()

    def do_OPTIONS(self) -> None:
        self._handle()


def main() -> None:
    Path(FLAGS_DIR).mkdir(parents=True, exist_ok=True)
    poller = threading.Thread(target=_poll_loop, name="status-poller", daemon=True)
    poller.start()
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    logger.info(
        "listening on %s:%s api=%s web=%s status=%s flags=%s",
        LISTEN_HOST,
        LISTEN_PORT,
        API_UPSTREAM,
        WEB_UPSTREAM,
        STATUS_URL,
        FLAGS_DIR,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
