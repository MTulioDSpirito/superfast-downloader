#!/usr/bin/env python3
"""server.py — SuperFast DM: servidor local (UI web + API) em stdlib.

Sobe em http://127.0.0.1:7860
  UI   : http://127.0.0.1:7860/
  API  : /api/add, /api/tasks, /api/task/<id>/{pause,resume,cancel,remove},
         /api/config, /health
Dependências: nenhuma (Python 3 stdlib).
"""
import json
import mimetypes
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import DB
from engine import Downloader

ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(ROOT, "static")
PORT = int(os.environ.get("SFD_PORT", "7860"))
HOST = os.environ.get("SFD_HOST", "127.0.0.1")
DEST_DIR = os.path.expanduser(os.environ.get(
    "SFD_DEST", os.path.join("~/Downloads", "superfast-dm")))
# dados (banco de histórico/config) em um diretório próprio, fácil de limpar ao desinstalar
DATA_DIR = os.path.expanduser(os.environ.get(
    "SFD_DATA", os.path.join("~", ".superfast-dm")))
DB_PATH = os.path.join(DATA_DIR, "sfd.db")
MAX_PARALLEL = int(os.environ.get("SFD_MAX_PARALLEL", "3"))
OPEN_BROWSER = os.environ.get("SFD_OPEN", "0") == "1"


def build():
    db = DB(DB_PATH)
    dl = Downloader(db, DEST_DIR, max_parallel=MAX_PARALLEL)
    return db, dl


SFD_DB, DL = build()


class Handler(BaseHTTPRequestHandler):
    server_version = "SuperFastDM/1.0"

    # ---------- helpers ----------
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _static(self, path):
        fp = os.path.join(STATIC, path)
        if not os.path.isfile(fp):
            self._json({"error": "not found"}, 404)
            return
        ctype = mimetypes.guess_type(fp)[0] or "application/octet-stream"
        with open(fp, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(n) if n else b""
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            return {}

    def log_message(self, format, *args):  # silencia logs por request
        pass

    # ---------- GET ----------
    def do_GET(self):
        u = urlparse(self.path)
        p = u.path
        if p == "/" or p == "/index.html":
            self._static("index.html")
        elif p.startswith("/static/"):
            self._static(p[len("/static/"):])
        elif p == "/api/tasks":
            self._json({"tasks": DL.snapshot()})
        elif p == "/api/config":
            self._json({
                "dest_dir": DEST_DIR, "max_parallel": MAX_PARALLEL,
                "port": PORT,
            })
        elif p == "/health":
            self._json({"ok": True, "active": DL._active})
        else:
            self._json({"error": "not found"}, 404)

    # ---------- OPTIONS (preflight p/ extensão) ----------
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    # ---------- POST ----------
    def do_POST(self):
        u = urlparse(self.path)
        p = u.path
        data = self._body()
        if p == "/api/add":
            url = (data.get("url") or "").strip()
            if not url.startswith(("http://", "https://")):
                self._json({"error": "url inválida (use http/https)"}, 400)
                return
            try:
                conns = int(data.get("connections", 8))
            except Exception:
                conns = 8
            tid = DL.add(url, data.get("filename"), max(1, min(conns, 32)))
            self._json({"id": tid}, 201)
        elif p == "/api/config":
            if "max_parallel" in data:
                DL.max_parallel = max(1, int(data["max_parallel"]))
            self._json({"ok": True})
        elif "/api/task/" in p:
            parts = [x for x in p.split("/") if x]
            # ['api','task','<id>','<action>']
            try:
                tid = int(parts[2])
            except Exception:
                self._json({"error": "id inválido"}, 400)
                return
            action = parts[3] if len(parts) > 3 else ""
            if action == "pause":
                DL.pause(tid); self._json({"ok": True})
            elif action == "resume":
                DL.resume(tid); self._json({"ok": True})
            elif action == "cancel":
                DL.cancel(tid); self._json({"ok": True})
            elif action == "remove":
                DL.remove(tid); self._json({"ok": True})
            else:
                self._json({"error": "ação inválida"}, 400)
        else:
            self._json({"error": "not found"}, 404)


def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print("SuperFast DM  (stdlib, sem dependências)")
    print("  UI   : http://%s:%d/" % (HOST, PORT))
    print("  dest : %s" % DEST_DIR)
    print("  db   : %s" % DB_PATH)
    print("  ctrl : Ctrl+C para sair")

    def _open_when_ready():
        import time
        import webbrowser
        time.sleep(0.6)
        for _ in range(20):
            try:
                from urllib.request import urlopen
                urlopen("http://%s:%d/health" % (HOST, PORT), timeout=3).read()
                webbrowser.open("http://%s:%d/" % (HOST, PORT))
                return
            except Exception:
                time.sleep(0.3)

    if OPEN_BROWSER:
        threading.Thread(target=_open_when_ready, daemon=True).start()

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nencerrando...")
        srv.shutdown()


if __name__ == "__main__":
    main()
