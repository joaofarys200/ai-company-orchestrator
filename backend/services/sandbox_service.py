import http.server
import json
import os
import socketserver
import threading

from backend.health import check_frontend_static
from backend.logging_config import get_logger, log_event


logger = get_logger(__name__)


class NoCacheHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


def start_frontend_http_server(project_root: str, port: int = 8000) -> None:
    dist_dir = os.path.join(project_root, "frontend", "dist")

    class FrontendHTTPRequestHandler(NoCacheHTTPRequestHandler):
        def do_GET(self):
            if self.path in {"/healthz", "/health.json"}:
                payload = check_frontend_static(project_root, port)
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(200 if payload["ok"] else 503)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()

    def run_server():
        handler = lambda *args, **kwargs: FrontendHTTPRequestHandler(*args, directory=dist_dir, **kwargs)
        socketserver.TCPServer.allow_reuse_address = True
        try:
            with socketserver.TCPServer(("", port), handler) as httpd:
                log_event(
                    logger,
                    "frontend_static.started",
                    message=f"Frontend HTTP server running on http://localhost:{port}",
                    port=port,
                    health_path="/healthz",
                )
                httpd.serve_forever()
        except Exception as e:
            log_event(logger, "frontend_static.start_error", level="error", port=port, error=str(e))

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
