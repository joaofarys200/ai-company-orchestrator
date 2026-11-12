import http.server
import json
import os
import shutil
import socket
import socketserver
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

from backend.health import check_frontend_static
from backend.logging_config import get_logger, log_event
from services.study_fs import (
    is_path_within_roots,
    resolve_confined_path,
    resolve_confined_subpath,
    safe_document_id,
    validate_safe_identifier,
)
from services.video_intelligence_service import ensure_browser_playable_video


logger = get_logger(__name__)

_SAFE_DATA_STUDY_EXTENSIONS = {
    ".pdf", ".mp4", ".webm", ".mkv", ".mov", ".avi", ".wmv", ".m4v",
    ".wav", ".mp3", ".m4a", ".ogg", ".flac",
    ".jpg", ".jpeg", ".png", ".webp",
    ".docx", ".pptx",
}


@dataclass(slots=True)
class FrontendServerHandle:
    server: Any
    thread: threading.Thread
    extra_servers: List[tuple[Any, threading.Thread]] = field(default_factory=list)

    def stop(self) -> None:
        all_pairs = [(self.server, self.thread), *self.extra_servers]
        for srv, th in all_pairs:
            try:
                srv.shutdown()
                srv.server_close()
            except Exception:
                pass
            if th and th.is_alive():
                th.join(timeout=2)


class GracefulThreadingTCPServer(socketserver.ThreadingTCPServer):
    def handle_error(self, request, client_address):
        # Ignore client disconnects/aborts that happen normally during fast navigation or reload
        exc_type, _, _ = sys.exc_info()
        if exc_type in (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            return
        super().handle_error(request, client_address)


class DualStackThreadingServer(GracefulThreadingTCPServer):
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

        def _allowed_origin(self) -> Optional[str]:
            origin = (self.headers.get("Origin") or "").strip().rstrip("/")
            if not origin:
                return None
            allowed = {
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://[::1]:5173",
                f"http://localhost:{port}",
                f"http://127.0.0.1:{port}",
                f"http://[::1]:{port}",
                "http://localhost:8000",
                "http://127.0.0.1:8000",
                "http://[::1]:8000",
            }
            if origin in allowed:
                return origin
            return None

        def _send_cors_headers(self) -> None:
            origin = self._allowed_origin()
            if origin:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, Range, X-Jarvis-Token")

        def _is_study_request_authorized(self) -> bool:
            sec_fetch_site = (self.headers.get("Sec-Fetch-Site") or "").strip().lower()
            if sec_fetch_site == "cross-site":
                return False
            origin = (self.headers.get("Origin") or "").strip()
            if origin and not self._allowed_origin():
                return False
            required_token = os.getenv("JARVIS_HTTP_TOKEN", "").strip()
            if required_token:
                supplied = (self.headers.get("X-Jarvis-Token") or "").strip()
                if not supplied and "?" in self.path:
                    from urllib.parse import parse_qs, urlparse
                    qs = parse_qs(urlparse(self.path).query)
                    supplied = (qs.get("token") or [""])[0].strip()
                if supplied != required_token:
                    return False
            return True

        def _send_error_text(self, code: int, msg: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(msg)))
            self._send_cors_headers()
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(msg)

        def _serve_file_with_range(self, file_path: str, content_type: str):
            """Suporta HTTP 206 Partial Content para seek e streaming de ficheiros e vídeo sem bufferizar em RAM."""
            try:
                p = Path(file_path)
                if p.is_symlink() or not p.is_file():
                    self._send_error_text(404, b"Not found")
                    return
                file_size = p.stat().st_size
            except OSError:
                self._send_error_text(404, b"Not found")
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
                    self._send_cors_headers()
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
            self._send_cors_headers()
            self.end_headers()
            if self.command == "HEAD":
                return
            try:
                with open(file_path, "rb") as f:
                    shutil.copyfileobj(f, self.wfile, length=64 * 1024)
            except (ConnectionResetError, BrokenPipeError):
                pass

        def _load_study_catalog_entry(self, doc_id: str) -> Optional[dict]:
            docs_file = Path(project_root) / "data" / "study" / "documents.json"
            if not docs_file.exists():
                return None
            try:
                with open(docs_file, "r", encoding="utf-8") as f:
                    docs_data = json.load(f)
                entry = docs_data.get(doc_id) if isinstance(docs_data, dict) else None
                return entry if isinstance(entry, dict) else None
            except Exception:
                return None

        def _resolve_cataloged_media_path(
            self,
            doc_id: str,
            raw_fp: Optional[str],
            fallback_subdir: Optional[str],
            allowed_exts: tuple[str, ...],
        ) -> Optional[str]:
            study_dir = Path(project_root) / "data" / "study"
            proj_dir = Path(project_root)
            if raw_fp:
                fp_path = Path(raw_fp)
                if not fp_path.is_absolute():
                    fp_path = proj_dir / fp_path
                try:
                    if not fp_path.is_symlink() and fp_path.is_file():
                        return str(fp_path.resolve(strict=False))
                except OSError:
                    pass

            # Fallback por prefixo de hash SOMENTE com identificador suficiente (>= 8 hex/alnum chars)
            if doc_id.startswith("doc_"):
                hash_prefix = doc_id[4:]
                if hash_prefix.startswith("vid_"):
                    hash_prefix = hash_prefix[4:]
                elif hash_prefix.startswith("aud_"):
                    hash_prefix = hash_prefix[4:]
                if len(hash_prefix) >= 8:
                    search_dir = resolve_confined_path(study_dir, fallback_subdir) if fallback_subdir else study_dir.resolve(strict=False)
                    if search_dir.exists():
                        for cand in search_dir.iterdir():
                            if (
                                cand.name.startswith(hash_prefix)
                                and cand.suffix.lower() in allowed_exts
                                and not cand.is_symlink()
                                and cand.is_file()
                            ):
                                return str(cand.resolve(strict=False))
            return None

        def _resolve_pdf_path(self, doc_id: str) -> Optional[str]:
            try:
                clean_id = safe_document_id(doc_id)
            except ValueError:
                return None
            doc_entry = self._load_study_catalog_entry(clean_id)
            raw_fp = doc_entry.get("metadata", {}).get("file_path") if doc_entry else None
            return self._resolve_cataloged_media_path(clean_id, raw_fp, None, (".pdf",))

        def _resolve_video_stream(self, doc_id: str, *, allow_transcode: bool = True) -> Optional[tuple[str, str]]:
            try:
                clean_id = safe_document_id(doc_id)
            except ValueError:
                return None
            doc_entry = self._load_study_catalog_entry(clean_id)
            raw_fp = None
            if doc_entry:
                raw_fp = doc_entry.get("metadata", {}).get("file_path") or doc_entry.get("metadata", {}).get("video", {}).get("file_path")
            file_path = self._resolve_cataloged_media_path(
                clean_id,
                raw_fp,
                "videos",
                (".mp4", ".webm", ".mkv", ".mov", ".avi", ".wmv", ".m4v", ".flv", ".mpg", ".mpeg"),
            )
            if not file_path or not os.path.isfile(file_path):
                return None
            if allow_transcode:
                cache_root = Path(project_root) / "data" / "study" / "videos_cache"
                return ensure_browser_playable_video(file_path, clean_id, cache_dir=cache_root)
            ext = os.path.splitext(file_path)[1].lower()
            mime = self.extensions_map.get(ext, "video/mp4")
            return file_path, mime

        def do_HEAD(self):
            clean_path = self.path.split("?")[0]
            if clean_path.startswith("/api/study/") and not self._is_study_request_authorized():
                self._send_error_text(403, b"Forbidden")
                return
            if clean_path.startswith("/api/study/document/") and clean_path.endswith("/file"):
                parts = clean_path.strip("/").split("/")
                if len(parts) >= 5:
                    doc_id = parts[3]
                    fp = self._resolve_pdf_path(doc_id)
                    if fp and os.path.isfile(fp):
                        size = os.path.getsize(fp)
                        self.send_response(200)
                        self.send_header("Content-Type", "application/pdf")
                        self.send_header("Content-Length", str(size))
                        self.send_header("Accept-Ranges", "bytes")
                        self._send_cors_headers()
                        self.end_headers()
                        return
                self._send_error_text(404, b"PDF not found")
                return
            if clean_path.startswith("/api/study/document/") and clean_path.endswith("/video"):
                parts = clean_path.strip("/").split("/")
                if len(parts) == 5:
                    allow_transcode = "raw=1" not in self.path
                    resolved = self._resolve_video_stream(parts[3], allow_transcode=allow_transcode)
                    if resolved and os.path.isfile(resolved[0]):
                        vpath, vmime = resolved
                        size = os.path.getsize(vpath)
                        self.send_response(200)
                        self.send_header("Content-Type", vmime)
                        self.send_header("Content-Length", str(size))
                        self.send_header("Accept-Ranges", "bytes")
                        self._send_cors_headers()
                        self.end_headers()
                        return
                self._send_error_text(404, b"Video not found")
                return
            return super().do_HEAD()

        def do_GET(self):
            try:
                self._dispatch_GET()
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                pass

        def _dispatch_GET(self):
            clean_path = self.path.split("?")[0]
            if clean_path in {"/favicon.ico", "favicon.ico"}:
                self.send_response(200)
                self.send_header("Content-Type", "image/x-icon")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if clean_path in {"/healthz", "/health.json"}:
                payload = check_frontend_static(project_root, port)
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(200 if payload["ok"] else 503)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if (clean_path.startswith("/api/study/") or clean_path.startswith("/data/study/")) and not self._is_study_request_authorized():
                self._send_error_text(403, b"Forbidden")
                return

            # Streaming de ficheiro PDF real por document_id
            if clean_path.startswith("/api/study/document/") and clean_path.endswith("/file"):
                parts = clean_path.strip("/").split("/")
                if len(parts) == 5:
                    doc_id = parts[3]
                    file_path = self._resolve_pdf_path(doc_id)
                    if file_path and os.path.isfile(file_path):
                        self._serve_file_with_range(file_path, "application/pdf")
                        return
                self._send_error_text(404, b"PDF not found")
                return

            # API de documentos de estudo
            if clean_path == "/api/study/documents":
                docs_file = os.path.join(project_root, "data", "study", "documents.json")
                docs_list = []
                if os.path.exists(docs_file):
                    try:
                        with open(docs_file, "r", encoding="utf-8") as f:
                            docs_dict = json.load(f)
                            if isinstance(docs_dict, dict):
                                docs_list = list(docs_dict.values())
                    except Exception:
                        pass
                body = json.dumps(docs_list, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(body)
                return

            # Streaming de keyframe/media por document_id e frame_id
            if clean_path.startswith("/api/study/document/") and "/media/" in clean_path:
                parts = clean_path.strip("/").split("/")
                if len(parts) == 6 and parts[4] == "media":
                    try:
                        doc_id = safe_document_id(parts[3])
                        frame_id = validate_safe_identifier(parts[5], label="frame_id")
                    except ValueError:
                        self._send_error_text(403, b"Forbidden")
                        return

                    study_dir = Path(project_root) / "data" / "study"
                    keyframes_root = study_dir / "keyframes"
                    doc_kf_dir = resolve_confined_path(keyframes_root, doc_id)
                    doc_entry = self._load_study_catalog_entry(doc_id)
                    target_media: Optional[Path] = None

                    if doc_entry:
                        kfs = doc_entry.get("metadata", {}).get("video", {}).get("keyframes", [])
                        for kf in kfs:
                            if isinstance(kf, dict) and kf.get("frame_id") == frame_id and kf.get("image_path"):
                                cand = Path(kf["image_path"])
                                if not cand.is_absolute():
                                    cand = Path(project_root) / cand
                                if is_path_within_roots(cand, [keyframes_root, study_dir]) and cand.is_file():
                                    target_media = cand.resolve(strict=False)
                                    break

                    if target_media is None and doc_kf_dir.exists():
                        for ext in (".jpg", ".jpeg", ".png", ".webp"):
                            cand = resolve_confined_path(doc_kf_dir, f"{frame_id}{ext}")
                            if cand.is_file():
                                target_media = cand
                                break

                    if target_media is not None:
                        mime = self.extensions_map.get(target_media.suffix.lower(), "image/jpeg")
                        self._serve_file_with_range(str(target_media), mime)
                        return

                self._send_error_text(404, b"Media not found")
                return

            # Streaming de vídeo por document_id (com transcode em cache para MP4 quando .wmv/.avi)
            if clean_path.startswith("/api/study/document/") and clean_path.endswith("/video"):
                parts = clean_path.strip("/").split("/")
                if len(parts) == 5:
                    try:
                        safe_document_id(parts[3])
                    except ValueError:
                        self._send_error_text(403, b"Forbidden")
                        return

                    allow_transcode = "raw=1" not in self.path
                    resolved = self._resolve_video_stream(parts[3], allow_transcode=allow_transcode)
                    if resolved and os.path.isfile(resolved[0]):
                        vpath, vmime = resolved
                        self._serve_file_with_range(vpath, vmime)
                        return

                self._send_error_text(404, b"Video not found")
                return

            if clean_path.startswith("/data/study/"):
                raw_subpath = self.path[len("/data/study/"):].split("?")[0]
                study_root = Path(project_root) / "data" / "study"
                try:
                    target_path = resolve_confined_subpath(study_root, raw_subpath, reject_symlinks=True)
                except ValueError:
                    self._send_error_text(403, b"Forbidden")
                    return

                ext = target_path.suffix.lower()
                if ext not in _SAFE_DATA_STUDY_EXTENSIONS:
                    self._send_error_text(403, b"Forbidden file type")
                    return

                if target_path.exists() and target_path.is_file():
                    content_type = self.extensions_map.get(ext, "application/octet-stream")
                    self._serve_file_with_range(str(target_path), content_type)
                    return

                self._send_error_text(404, b"File not found")
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
            self._send_cors_headers()
            self.end_headers()

    def handler(*args, **kwargs):
        return FrontendHTTPRequestHandler(
            *args,
            directory=dist_dir,
            **kwargs,
        )

    socketserver.TCPServer.allow_reuse_address = True
    server = None
    extra_servers: List[tuple[Any, threading.Thread]] = []
    try:
        # Vincular exclusivamente à interface loopback (IPv4 127.0.0.1 e, se possível, IPv6 ::1 isolado)
        server = GracefulThreadingTCPServer(("127.0.0.1", port), handler)
    except Exception as start_error:
        log_event(
            logger,
            "frontend_static.start_error",
            level="error",
            port=port,
            error=str(start_error),
        )
        return None

    bound_port = server.server_address[1]
    if port > 0:
        try:
            class LoopbackIPv6Server(GracefulThreadingTCPServer):
                address_family = socket.AF_INET6

                def server_bind(self):
                    self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                    super().server_bind()

            srv6 = LoopbackIPv6Server(("::1", bound_port), handler)
            th6 = threading.Thread(
                target=srv6.serve_forever,
                daemon=True,
                name="jarvis-frontend-static-ipv6",
            )
            th6.start()
            extra_servers.append((srv6, th6))
        except Exception:
            pass

    def run_server() -> None:
        log_event(
            logger,
            "frontend_static.started",
            message=(
                "Frontend HTTP server running on "
                f"http://127.0.0.1:{bound_port}"
            ),
            port=bound_port,
            health_path="/healthz",
        )
        server.serve_forever()

    thread = threading.Thread(
        target=run_server,
        daemon=True,
        name="jarvis-frontend-static",
    )
    thread.start()
    return FrontendServerHandle(server=server, thread=thread, extra_servers=extra_servers)
