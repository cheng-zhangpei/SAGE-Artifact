from __future__ import annotations

import os
import sqlite3
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, List, Optional


class _CaptureHandler(BaseHTTPRequestHandler):
    """记录所有 POST 请求"""
    records: List[dict] = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        _CaptureHandler.records.append({
            "method": "POST", "path": self.path, "body": body,
        })
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass  # 静默


class BackendPool:
    def __init__(self, config: dict):
        self.config = config
        self.sqlite_conn: Optional[sqlite3.Connection] = None
        self.http_server: Optional[HTTPServer] = None
        self.http_thread: Optional[threading.Thread] = None
        self.http_port: int = 0

    def setup(self):
        backends = self.config.get("backends", {})
        if "sqlite" in backends:
            self._setup_sqlite(backends["sqlite"])
        if "http" in backends:
            self._setup_http()
        if "filesystem" in backends:
            self._setup_filesystem(backends["filesystem"])

    def _setup_sqlite(self, cfg: dict):
        self.sqlite_conn = sqlite3.connect(":memory:")
        for table, tcfg in cfg.get("tables", {}).items():
            cols = ", ".join(tcfg["columns"])
            self.sqlite_conn.execute(f"CREATE TABLE {table} ({cols})")
            for row in tcfg.get("rows", []):
                ph = ", ".join(["?"] * len(row))
                self.sqlite_conn.execute(f"INSERT INTO {table} VALUES ({ph})", row)
            self.sqlite_conn.commit()

    def _setup_http(self):
        _CaptureHandler.records = []
        self.http_server = HTTPServer(("127.0.0.1", 0), _CaptureHandler)
        self.http_port = self.http_server.server_address[1]
        self.http_thread = threading.Thread(
            target=self.http_server.serve_forever, daemon=True
        )
        self.http_thread.start()
    def _setup_filesystem(self, cfg: dict):
        """Create files declared in config."""
        import tempfile, os
        self.fs_base = tempfile.mkdtemp(prefix="sage_bench_")
        self.fs_files = {}
        for rel_path, content in cfg.get("files", {}).items():
            full_path = os.path.join(self.fs_base, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.fs_files[rel_path] = full_path

    def _read_file(self, rel_path: str) -> str:
        full_path = os.path.join(self.fs_base, rel_path)
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    def snapshot(self) -> dict:
        snap: Dict[str, Any] = {}
        if self.sqlite_conn:
            tables = {}
            cur = self.sqlite_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            for (name,) in cur.fetchall():
                tables[name] = self.sqlite_conn.execute(
                    f"SELECT * FROM {name}"
                ).fetchall()
            snap["sqlite"] = tables
        if self.http_server:
            snap["http_requests"] = list(_CaptureHandler.records)
        if hasattr(self, 'fs_files') and self.fs_files:
            snap["filesystem"] = {
                p: open(fp).read() for p, fp in self.fs_files.items()
            }
        return snap

    def execute_effect(self, steps: List[dict]) -> List[Any]:
        results: List[Any] = []
        for step in steps:
            backend, op = step["backend"], step["op"]
            if backend == "sqlite" and op == "query":
                cur = self.sqlite_conn.execute(step["sql"])
                results.append(cur.fetchall())
            elif backend == "http" and op == "post":
                body = ""
                if "body_from_step" in step:
                    src = results[step["body_from_step"]]
                    body = str(src) if src else ""
                elif "body" in step:
                    body = step["body"]
                url = f"http://127.0.0.1:{self.http_port}{step['path']}"
                req = urllib.request.Request(
                    url, data=body.encode(), method="POST",
                    headers={"Content-Type": "text/plain"},
                )
                urllib.request.urlopen(req, timeout=5)
                results.append({"url": url, "body": body})
            elif backend == "filesystem" and op == "read":
                content = self._read_file(step["path"])
                results.append(content)
        return results

    def teardown(self):
        if self.sqlite_conn:
            self.sqlite_conn.close()
            self.sqlite_conn = None
        if self.http_server:
            self.http_server.shutdown()
            self.http_server = None
        if hasattr(self, 'fs_base') and self.fs_base:
            import shutil
            shutil.rmtree(self.fs_base, ignore_errors=True)