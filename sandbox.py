import os
import subprocess
import threading
import http.server
import socketserver
import json
import sys
from urllib.parse import quote

from backend.errors import safe_user_error
from backend.health import check_sandbox_runtime
from backend.logging_config import get_logger, log_event


logger = get_logger(__name__)

PORT = int(os.getenv("DOCKER_PORT", 8080))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SANDBOX_DIR = os.path.join(BASE_DIR, "sandbox_dir")

def init_sandbox_dir():
    if not os.path.exists(SANDBOX_DIR):
        os.makedirs(SANDBOX_DIR)
    
    # Write a default placeholder page
    index_path = os.path.join(SANDBOX_DIR, "index.html")
    if not os.path.exists(index_path):
        with open(index_path, "w", encoding="utf-8") as f:
            f.write("<html><body style='background:#12131a;color:#fff;display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif;'><h2>Sandbox Vazia</h2></body></html>")
    write_sandbox_health_file()


def write_sandbox_health_file():
    health_path = os.path.join(SANDBOX_DIR, "healthz")
    payload = check_sandbox_runtime(SANDBOX_DIR, PORT)
    with open(health_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

def write_project_files(html: str, css: str, js: str):
    init_sandbox_dir()
    
    # Write index.html, styles.css, and app.js into sandbox_dir
    with open(os.path.join(SANDBOX_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
        
    with open(os.path.join(SANDBOX_DIR, "styles.css"), "w", encoding="utf-8") as f:
        f.write(css)
        
    with open(os.path.join(SANDBOX_DIR, "app.js"), "w", encoding="utf-8") as f:
        f.write(js)

def start_local_fallback_server():
    log_event(logger, "sandbox.local_fallback.initializing", port=PORT)
    
    class NoCacheHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            super().end_headers()

        def do_GET(self):
            if self.path in {"/healthz", "/health.json"}:
                payload = check_sandbox_runtime(SANDBOX_DIR, PORT)
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(200 if payload["ok"] else 503)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()
            
    def run_server():
        handler = lambda *args, **kwargs: NoCacheHTTPRequestHandler(*args, directory=SANDBOX_DIR, **kwargs)
        socketserver.TCPServer.allow_reuse_address = True
        try:
            with socketserver.TCPServer(("", PORT), handler) as httpd:
                log_event(logger, "sandbox.local_fallback.started", port=PORT, health_path="/healthz")
                httpd.serve_forever()
        except Exception as server_err:
            log_event(logger, "sandbox.local_fallback.start_error", level="error", port=PORT, error=str(server_err))
            
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

IS_DOCKER_ACTIVE = False

def get_sandbox_status():
    return {
        "mode": "docker" if IS_DOCKER_ACTIVE else "local_fallback",
        "port": PORT,
        "is_docker": IS_DOCKER_ACTIVE,
    }

def start_docker_sandbox():
    global IS_DOCKER_ACTIVE
    init_sandbox_dir()
    
    # Stop existing sandbox first
    stop_docker_sandbox()
    
    try:
        # Convert path to absolute
        abs_sandbox_dir = os.path.abspath(SANDBOX_DIR)
        
        try:
            import docker
            client = docker.from_env()
            log_event(logger, "sandbox.docker.starting", port=PORT)
            
            # Run docker container in background
            client.containers.run(
                "nginx:alpine",
                name="jarvis-sandbox",
                detach=True,
                ports={'80/tcp': PORT},
                volumes={abs_sandbox_dir: {'bind': '/usr/share/nginx/html', 'mode': 'ro'}}
            )
            IS_DOCKER_ACTIVE = True
            log_event(logger, "sandbox.docker.started", port=PORT)
            return True
        except ImportError:
            raise RuntimeError("módulo 'docker' não está instalado no ambiente Python")
    except Exception as e:
        IS_DOCKER_ACTIVE = False
        log_event(logger, "sandbox.docker.start_error", level="warning", port=PORT, error=str(e))
        start_local_fallback_server()
        return True

def stop_docker_sandbox():
    try:
        import docker
        client = docker.from_env()
        container = client.containers.get("jarvis-sandbox")
        container.remove(force=True)
        log_event(logger, "sandbox.docker.stopped")
    except Exception:
        pass

project_process = None
project_http_server = None
last_project_root = None

def _to_preview_url(path: str, root_dir: str = SANDBOX_DIR, port: int = PORT) -> str:
    rel_path = os.path.relpath(path, root_dir).replace(os.sep, "/")
    rel_url = "/".join(quote(part) for part in rel_path.split("/"))
    return f"http://127.0.0.1:{port}/{rel_url}"

def _find_preview_index(root_dir: str = SANDBOX_DIR) -> str | None:
    candidates = []
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", "node_modules", ".git", ".jarvis", "venv", ".venv", "dist"}]
        if "index.html" in files:
            candidates.append(os.path.join(root, "index.html"))

    if not candidates:
        return None

    preferred_segments = (f"{os.sep}client{os.sep}", f"{os.sep}frontend{os.sep}", f"{os.sep}public{os.sep}")
    nested = [path for path in candidates if any(segment in path for segment in preferred_segments)]
    if nested:
        return max(nested, key=lambda path: os.path.getmtime(path))
    return max(candidates, key=lambda path: os.path.getmtime(path))

def _find_python_entry(root_dir: str = SANDBOX_DIR) -> str | None:
    candidates = []
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", "node_modules", ".git", ".jarvis", "venv", ".venv", "dist"}]
        depth = os.path.relpath(root, root_dir).count(os.sep)
        if depth > 2:
            dirs[:] = []
            continue
        for filename in ("app.py", "main.py"):
            if filename in files:
                candidates.append(os.path.join(root, filename))

    if not candidates:
        return None

    preferred_dirs = (f"{os.sep}server{os.sep}", f"{os.sep}backend{os.sep}", f"{os.sep}api{os.sep}")
    preferred = [path for path in candidates if any(segment in path for segment in preferred_dirs)]
    if preferred:
        return max(preferred, key=lambda path: os.path.getmtime(path))
    return max(candidates, key=lambda path: os.path.getmtime(path))

def _find_package_dir(root_dir: str = SANDBOX_DIR) -> str | None:
    candidates = []
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in {"node_modules", ".git", ".jarvis", "__pycache__", "venv", ".venv", "dist"}]
        depth = os.path.relpath(root, root_dir).count(os.sep)
        if depth > 2:
            dirs[:] = []
            continue
        if "package.json" in files:
            candidates.append(root)

    if not candidates:
        return None
    return max(candidates, key=lambda path: os.path.getmtime(os.path.join(path, "package.json")))

def inspect_project_layout(root_dir: str) -> dict:
    root = os.path.realpath(os.path.abspath(root_dir))
    return {
        "root": root,
        "preview_index": _find_preview_index(root),
        "python_entry": _find_python_entry(root),
        "package_dir": _find_package_dir(root),
    }


def _start_project_http_server(root_dir: str) -> tuple[bool, str]:
    global project_http_server

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

    handler = lambda *args, **kwargs: QuietHandler(*args, directory=root_dir, **kwargs)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    project_http_server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    port = project_http_server.server_address[1]
    thread = threading.Thread(target=project_http_server.serve_forever, daemon=True)
    thread.start()
    return True, f"http://127.0.0.1:{port}/"


def _package_script(package_dir: str) -> str | None:
    try:
        with open(os.path.join(package_dir, "package.json"), "r", encoding="utf-8") as handle:
            scripts = json.load(handle).get("scripts", {})
    except (OSError, ValueError, AttributeError):
        return None
    for name in ("dev", "preview", "start"):
        if isinstance(scripts.get(name), str) and scripts[name].strip():
            return name
    return None


def run_custom_project(on_output_callback, root_dir: str | None = None, allow_dependency_install: bool | None = None):
    global project_process, last_project_root
    stop_custom_project()

    selected_root = os.path.realpath(os.path.abspath(root_dir or SANDBOX_DIR))
    last_project_root = selected_root
    legacy_sandbox = selected_root == os.path.realpath(SANDBOX_DIR)
    if allow_dependency_install is None:
        allow_dependency_install = legacy_sandbox
    preview_index = _find_preview_index(selected_root)
    package_dir = _find_package_dir(selected_root)
    python_entry = _find_python_entry(selected_root)

    if package_dir:
        rel_dir = os.path.relpath(package_dir, selected_root)
        location = "." if rel_dir == "." else rel_dir
        script_name = _package_script(package_dir)
        if not script_name and preview_index:
            running, preview_url = _start_project_http_server(selected_root)
            on_output_callback(f"[Project] Preview estatico: {preview_url}\n")
            return {"running": running, "preview_url": preview_url, "root": selected_root}
        if not script_name:
            on_output_callback("[Project] package.json sem script de preview, dev ou start.\n")
            return {"running": False, "preview_url": None, "root": selected_root}
        node_modules_dir = os.path.join(package_dir, "node_modules")
        should_install = allow_dependency_install or not os.path.isdir(node_modules_dir)
        if should_install:
            on_output_callback(f"[Sandbox] Dependencias em falta em {location}. A executar 'npm install'...\n")
        else:
            on_output_callback(f"[Project] package.json detetado em {location}. A usar o script existente '{script_name}'.\n")

        def run_thread():
            global project_process
            try:
                if should_install:
                    install_proc = subprocess.run(
                        "npm install",
                        cwd=package_dir,
                        shell=True,
                        text=True,
                        capture_output=True,
                        timeout=180
                    )
                    if install_proc.returncode != 0:
                        on_output_callback(f"[Sandbox Error] npm install failed:\n{install_proc.stderr}\n")
                        return

                project_process = subprocess.Popen(
                    f"npm run {script_name}",
                    cwd=package_dir,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )

                if project_process.stdout:
                    for line in project_process.stdout:
                        on_output_callback(line)
            except Exception as e:
                on_output_callback(f"[Sandbox Error] {safe_user_error('Erro ao iniciar projeto node', e)}\n")

        t = threading.Thread(target=run_thread, daemon=True)
        t.start()
        preview_url = "http://127.0.0.1:5173/" if script_name in {"dev", "preview"} else "http://127.0.0.1:3000/"
        return {"running": True, "preview_url": preview_url, "root": selected_root}

    if python_entry:
        script_dir = os.path.dirname(python_entry)
        script_name = os.path.basename(python_entry)
        rel_script = os.path.relpath(python_entry, selected_root)
        on_output_callback(f"[Project] Python detetado: {rel_script}. A iniciar 'python {script_name}'...\n")

        def run_thread():
            global project_process
            try:
                venv_python = os.path.join(BASE_DIR, 'venv', 'Scripts', 'python.exe')
                python_cmd = venv_python if os.path.exists(venv_python) else 'python'
                requirements_path = os.path.join(script_dir, "requirements.txt")

                if allow_dependency_install and os.path.exists(requirements_path):
                    on_output_callback("[Sandbox] requirements.txt detected. Installing backend dependencies...\n")
                    install_proc = subprocess.run(
                        [python_cmd, "-m", "pip", "install", "-r", requirements_path],
                        cwd=script_dir,
                        text=True,
                        capture_output=True,
                        timeout=180,
                    )
                    if install_proc.returncode != 0:
                        on_output_callback(f"[Sandbox Error] pip install failed:\n{install_proc.stderr}\n")
                        return

                project_process = subprocess.Popen(
                    [python_cmd, "-u", script_name],
                    cwd=script_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                if project_process.stdout:
                    for line in project_process.stdout:
                        on_output_callback(line)
            except Exception as e:
                on_output_callback(f"[Sandbox Error] {safe_user_error('Erro ao iniciar projeto python', e)}\n")

        t = threading.Thread(target=run_thread, daemon=True)
        t.start()
        return {"running": True, "preview_url": None, "root": selected_root}

    if preview_index:
        if legacy_sandbox:
            preview_url = _to_preview_url(preview_index, selected_root, PORT)
            on_output_callback(f"[Sandbox] Static HTML/CSS/JS project detected. Available at {preview_url}\n")
            return {"running": False, "preview_url": preview_url, "root": selected_root}
        running, base_url = _start_project_http_server(selected_root)
        relative_index = os.path.relpath(preview_index, selected_root).replace(os.sep, "/")
        preview_url = base_url if relative_index == "index.html" else f"{base_url}{relative_index}"
        on_output_callback(f"[Project] Preview estatico: {preview_url}\n")
        return {"running": running, "preview_url": preview_url, "root": selected_root}

    on_output_callback("[Project] Nao foi encontrado um entrypoint de preview.\n")
    return {"running": False, "preview_url": None, "root": selected_root}
def stop_custom_project():
    global project_process, project_http_server
    if project_http_server:
        server = project_http_server
        project_http_server = None
        try:
            server.shutdown()
            server.server_close()
        except Exception as e:
            log_event(logger, "sandbox.project_http.stop_error", level="error", error=str(e))
    if project_process:
        process = project_process
        project_process = None
        log_event(logger, "sandbox.project_process.stopping", pid=process.pid)
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    shell=False,
                    capture_output=True,
                )
            else:
                process.terminate()
                process.wait(timeout=3)
            log_event(logger, "sandbox.project_process.stopped", pid=process.pid)
            return
        except Exception as e:
            log_event(logger, "sandbox.project_process.stop_error", level="error", pid=process.pid, error=str(e))

