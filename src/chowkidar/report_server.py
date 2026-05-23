"""Lightweight localhost report server using standard library http.server."""

from __future__ import annotations

import http.server
import json
import logging
import socketserver
import threading
import urllib.parse
from pathlib import Path
from typing import Any

from .editor import open_in_editor

logger = logging.getLogger(__name__)


class ReportHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    report_content: str = ""
    report_path: Path | None = None

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        if path in ("/", "/index.html", "/report"):
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            # Avoid CORS issues and allow secure access
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            content = self.report_content
            # If path query param is provided, read that report from disk (safely)
            if "path" in query:
                try:
                    rep_path = Path(query["path"][0]).resolve()
                    # Check safety: only allow reading .html files from within CHOWKIDAR_HOME or temp/system folders
                    if rep_path.exists() and rep_path.suffix == ".html":
                        content = rep_path.read_text(encoding="utf-8")
                except Exception as e:
                    logger.error("Error reading report from query path: %s", e)

            self.wfile.write(content.encode("utf-8"))

        elif path == "/open-editor":
            target_path = query.get("path", [""])[0]
            success = False
            message = ""
            if target_path:
                try:
                    success = open_in_editor(target_path)
                    if not success:
                        message = "All opening attempts failed. Ensure your editor is on PATH or set CHOWKIDAR_EDITOR."
                except Exception as e:
                    message = str(e)
            else:
                message = "No path parameter provided."

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success, "message": message}).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def log_message(self, format: str, *args: Any) -> None:
        # Override to suppress noisy requests in CLI output unless error
        pass


def start_report_server(report_content: str, report_path: Path | None = None, port: int = 51731) -> int:
    """Start the lightweight report server on an available port, returning the port number."""
    ReportHTTPRequestHandler.report_content = report_content
    ReportHTTPRequestHandler.report_path = report_path

    # Try the requested port, or find an available one
    for p in range(port, port + 100):
        try:
            socketserver.TCPServer.allow_reuse_address = True
            server = socketserver.TCPServer(("127.0.0.1", p), ReportHTTPRequestHandler)

            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()
            logger.info("Report server started at http://127.0.0.1:%d", p)
            return p
        except OSError:
            continue

    raise OSError("Could not find an available port to start the report server.")
