"""Embedded HTTP listener for OnAir sign pushes (Flask)."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

from flask import Flask, Response, jsonify, request
from werkzeug.serving import make_server

logger = logging.getLogger(__name__)


def create_onair_app(
    get_state: Callable[[], bool],
    apply_state: Callable[[bool], None],
) -> Flask:
    """Build a Flask app implementing the OnAir sign HTTP contract."""

    app = Flask(__name__)

    @app.get("/onair/api/v1/state")
    def get_onair_state() -> Any:
        return jsonify(get_state())

    @app.put("/onair/api/v1/state")
    def put_onair_state() -> Any:
        body = request.get_json(silent=True)
        if not isinstance(body, bool):
            return Response(
                '{"error": "body must be a JSON boolean"}',
                status=400,
                mimetype="application/json",
            )
        apply_state(body)
        return jsonify(get_state())

    return app


def run_flask_in_thread(app: Flask, host: str, port: int) -> tuple[Any, threading.Thread]:
    """Run *app* with Werkzeug in a daemon thread; returns ``(server, thread)``."""
    server = make_server(host, port, app, threaded=True)

    def _run() -> None:
        try:
            server.serve_forever()
        except Exception:
            logger.exception("Flask server failed")
            raise

    thread = threading.Thread(target=_run, name="deckd-flask", daemon=True)
    thread.start()
    return server, thread
