import http.server
import json
import os
import socket
import socketserver
import threading
from dataclasses import dataclass
from typing import Any

from backend.health import check_frontend_static
from backend.logging_config import get_logger, log_event


logger = get_logger(__name__)


@dataclass(slots=True)
class FrontendServerHandle:
    server: Any
    thread: threading.Thread

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        if self.thread.is_alive():
            self.thread.join(timeout=2)


class DualStackThreadingServer(socketserver.ThreadingTCPServer):
    address_family = socket.AF_INET6

    def server_bind(self):
        # Enable dual-stack IPv4 and IPv6 so both localhost/127.0.0.1 and [::1] connect with 0ms delay
        try:
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        except (AttributeError, OSError):
            pass
        super().server_bind()


class NoCacheHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def address_string(self):
        # Prevent blocking reverse DNS lookup on Windows (eliminates 2000ms stall)
        return str(self.client_address[0])

    def log_message(self, format, *args):
        # Suppress noisy stdout logs during high-frequency asset/page requests
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


def start_frontend_http_server(
    project_root: str,
    port: int = 8000,
) -> FrontendServerHandle | None:
    dist_dir = os.path.join(project_root, "frontend", "dist")

    class FrontendHTTPRequestHandler(NoCacheHTTPRequestHandler):
        extensions_map = {
            **NoCacheHTTPRequestHandler.extensions_map,
            ".mjs": "application/javascript",
            ".js": "application/javascript",
            ".css": "text/css",
            ".pdf": "application/pdf",
            ".mp4": "video/mp4",
            ".webm": "video/webm",
            ".mkv": "video/x-matroska",
            ".mov": "video/quicktime",
            ".avi": "video/x-msvideo",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }

        def _serve_file_with_range(self, file_path: str, content_type: str):
            """Suporta HTTP 206 Partial Content para seek e streaming de vídeo de alto desempenho."""
            try:
                file_size = os.path.getsize(file_path)
            except OSError:
                self.send_response(404)
                self.end_headers()
                return

            range_header = self.headers.get("Range")
            if range_header and range_header.startswith("bytes="):
                try:
                    ranges = range_header.replace("bytes=", "").split("-")
                    start = int(ranges[0]) if ranges[0] else 0
                    end = int(ranges[1]) if len(ranges) > 1 and ranges[1] else file_size - 1
                    start = max(0, min(start, file_size - 1))
                    end = max(start, min(end, file_size - 1))
                    content_length = end - start + 1

                    self.send_response(206)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                    self.send_header("Content-Length", str(content_length))
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
                    self.send_header("Access-Control-Allow-Headers", "*")
                    self.end_headers()

                    with open(file_path, "rb") as f:
                        f.seek(start)
                        remaining = content_length
                        chunk_size = 64 * 1024
                        while remaining > 0:
                            to_read = min(remaining, chunk_size)
                            chunk = f.read(to_read)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            remaining -= len(chunk)
                    return
                except (ConnectionResetError, BrokenPipeError):
                    return
                except Exception:
                    pass

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.end_headers()
            try:
                with open(file_path, "rb") as f:
                    chunk_size = 64 * 1024
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
            except (ConnectionResetError, BrokenPipeError):
                pass

        def _resolve_pdf_path(self, doc_id: str):
            docs_file = os.path.join(project_root, "data", "study", "documents.json")
            file_path = None
            if os.path.exists(docs_file):
                try:
                    with open(docs_file, "r", encoding="utf-8") as f:
                        docs_data = json.load(f)
                    doc_entry = docs_data.get(doc_id)
                    if doc_entry:
                        fp = doc_entry.get("metadata", {}).get("file_path")
                        if fp:
                            if os.path.isabs(fp) and os.path.exists(fp):
                                file_path = fp
                            elif os.path.exists(os.path.join(project_root, fp)):
                                file_path = os.path.join(project_root, fp)
                except Exception:
                    pass

            if not file_path:
                hash_prefix = doc_id.replace("doc_", "")
                study_dir = os.path.join(project_root, "data", "study")
                if os.path.exists(study_dir):
                    for fname in os.listdir(study_dir):
                        if fname.startswith(hash_prefix) and fname.lower().endswith(".pdf"):
                            candidate = os.path.join(study_dir, fname)
                            if os.path.isfile(candidate):
                                file_path = candidate
                                break
            return file_path

        def do_HEAD(self):
            if self.path.startswith("/api/study/document/") and self.path.endswith("/file"):
                parts = self.path.split("?")[0].strip("/").split("/")
                if len(parts) >= 5:
                    doc_id = parts[3]
                    fp = self._resolve_pdf_path(doc_id)
                    if fp and os.path.exists(fp):
                        size = os.path.getsize(fp)
                        self.send_response(200)
                        self.send_header("Content-Type", "application/pdf")
                        self.send_header("Content-Length", str(size))
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()
                        return
                self.send_response(404)
                self.end_headers()
                return
            return super().do_HEAD()

        def do_GET(self):
            if self.path in {"/favicon.ico", "favicon.ico"}:
                self.send_response(200)
                self.send_header("Content-Type", "image/x-icon")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if self.path in {"/healthz", "/health.json"}:
                payload = check_frontend_static(project_root, port)
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(200 if payload["ok"] else 503)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # Streaming de ficheiro PDF real por document_id
            if self.path.startswith("/api/study/document/") and self.path.endswith("/file"):
                parts = self.path.split("?")[0].strip("/").split("/")
                if len(parts) >= 5:
                    doc_id = parts[3]
                    file_path = self._resolve_pdf_path(doc_id)
                    if file_path and os.path.exists(file_path):
                        try:
                            with open(file_path, "rb") as pf:
                                pdf_bytes = pf.read()
                            self.send_response(200)
                            self.send_header("Content-Type", "application/pdf")
                            self.send_header("Content-Length", str(len(pdf_bytes)))
                            self.send_header("Access-Control-Allow-Origin", "*")
                            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
                            self.send_header("Access-Control-Allow-Headers", "*")
                            self.end_headers()
                            self.wfile.write(pdf_bytes)
                            return
                        except Exception:
                            pass

                self.send_response(404)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b"PDF not found")
                return

            # API de documentos de estudo
            if self.path.startswith("/api/study/documents"):
                docs_file = os.path.join(project_root, "data", "study", "documents.json")
                docs_list = []
                if os.path.exists(docs_file):
                    try:
                        with open(docs_file, "r", encoding="utf-8") as f:
                            docs_dict = json.load(f)
                            docs_list = list(docs_dict.values())
                    except Exception:
                        pass
                body = json.dumps(docs_list, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
                return

            # Streaming de vídeo por document_id
            if self.path.startswith("/api/study/document/") and self.path.endswith("/video"):
                parts = self.path.split("?")[0].strip("/").split("/")
                if len(parts) >= 5:
                    doc_id = parts[3]
                    docs_file = os.path.join(project_root, "data", "study", "documents.json")
                    file_path = None
                    if os.path.exists(docs_file):
                        try:
                            with open(docs_file, "r", encoding="utf-8") as f:
                                docs_data = json.load(f)
                            doc_entry = docs_data.get(doc_id)
                            if doc_entry:
                                fp = doc_entry.get("metadata", {}).get("file_path") or doc_entry.get("metadata", {}).get("video", {}).get("file_path")
                                if fp:
                                    if os.path.isabs(fp) and os.path.exists(fp):
                                        file_path = fp
                                    elif os.path.exists(os.path.join(project_root, fp)):
                                        file_path = os.path.join(project_root, fp)
                        except Exception:
                            pass

                    if not file_path:
                        # Procurar na pasta de vídeos
                        vid_dir = os.path.join(project_root, "data", "study", "videos")
                        if os.path.exists(vid_dir):
                            hash_prefix = doc_id.replace("doc_", "")
                            for fname in os.listdir(vid_dir):
                                if fname.startswith(hash_prefix):
                                    candidate = os.path.join(vid_dir, fname)
                                    if os.path.isfile(candidate):
                                        file_path = candidate
                                        break

                    if file_path and os.path.exists(file_path):
                        ext = os.path.splitext(file_path)[1].lower()
                        mime = self.extensions_map.get(ext, "video/mp4")
                        self._serve_file_with_range(file_path, mime)
                        return

                self.send_response(404)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b"Video not found")
                return

            if self.path.startswith("/data/study/"):
                subpath = self.path.replace("/data/study/", "").split("?")[0]
                target_file = os.path.join(project_root, "data", "study", subpath)
                if os.path.exists(target_file) and os.path.isfile(target_file):
                    ext = os.path.splitext(target_file)[1].lower()
                    content_type = self.extensions_map.get(ext, "application/octet-stream")
                    if content_type.startswith("video/"):
                        self._serve_file_with_range(target_file, content_type)
                        return
                    with open(target_file, "rb") as f:
                        file_bytes = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(file_bytes)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(file_bytes)
                    return

            super().do_GET()

        def end_headers(self):
            # Never cache HTML or SPA entrypoints so changes and builds load immediately
            raw_path = self.path.split("?")[0]
            if raw_path == "/" or raw_path.endswith(".html") or not "." in raw_path.split("/")[-1]:
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
            super().end_headers()

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.end_headers()

    def handler(*args, **kwargs):
        return FrontendHTTPRequestHandler(
            *args,
            directory=dist_dir,
            **kwargs,
        )

    socketserver.TCPServer.allow_reuse_address = True
    server = None
    try:
        # Prefer dual-stack (IPv6 + IPv4) for 0ms localhost latency on Windows
        server = DualStackThreadingServer(("::", port), handler)
    except Exception:
        try:
            # Fallback to standard IPv4 binding if dual-stack is unavailable
            server = socketserver.ThreadingTCPServer(("", port), handler)
        except Exception as start_error:
            log_event(
                logger,
                "frontend_static.start_error",
                level="error",
                port=port,
                error=str(start_error),
            )
            return None

    def run_server() -> None:
        log_event(
            logger,
            "frontend_static.started",
            message=(
                "Frontend HTTP server running on "
                f"http://localhost:{port}"
            ),
            port=port,
            health_path="/healthz",
        )
        server.serve_forever()

    thread = threading.Thread(
        target=run_server,
        daemon=True,
        name="jarvis-frontend-static",
    )
    thread.start()
    return FrontendServerHandle(server=server, thread=thread)
