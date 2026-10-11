#!/usr/bin/env python3
"""Token-guarded read-only CSV server for one temporary Graph import.

The token is never logged or committed in plaintext. Only the session holder
can read original Ghidra text; the process exits on request or after TTL.
"""
import argparse, http.server, os, pathlib, threading, time, urllib.parse, json, hashlib

def run(root,token,host,port,ttl):
    base=root.resolve()
    deadline=time.monotonic()+ttl
    stopped=threading.Event()
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self,fmt,*args):
            # Do not log URLs; they contain the bearer capability.
            pass
        def do_GET(self):
            if time.monotonic()>deadline:
                self.send_error(410)
                stopped.set()
                return
            parsed=urllib.parse.urlsplit(self.path)
            prefix="/t6/"+token+"/"
            if not parsed.path.startswith(prefix):
                self.send_error(404)
                return
            key=parsed.path[len(prefix):]
            if key=="stop.csv":
                body=b"done\n1\n"
                self.send_response(200)
                self.send_header("Content-Type","text/csv")
                self.send_header("Cache-Control","no-store")
                self.send_header("Content-Length",str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                self.wfile.flush()
                stopped.set()
                return
            candidate=(base/key).resolve()
            if not candidate.is_relative_to(base) or not candidate.is_file() or candidate.suffix!=".csv":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type","text/csv; charset=utf-8")
            self.send_header("Cache-Control","private, no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Content-Length",str(candidate.stat().st_size))
            self.end_headers()
            try:
                with candidate.open("rb") as f:
                    while chunk:=f.read(1<<16):
                        self.wfile.write(chunk)
            except (BrokenPipeError,ConnectionResetError):
                return

    server=http.server.ThreadingHTTPServer((host,port),Handler)
    server.timeout=0.5
    (root/"server_ready.marker").write_text("ready\n")
    try:
        while not stopped.is_set() and time.monotonic()<deadline:
            server.handle_request()
    finally:
        server.server_close()

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",required=True,type=pathlib.Path)
    ap.add_argument("--token",required=True)
    ap.add_argument("--host",default="127.0.0.1")
    ap.add_argument("--port",type=int,default=8765)
    ap.add_argument("--ttl-seconds",type=int,default=2400)
    a=ap.parse_args()
    if len(a.token)<32 or any(c not in "0123456789abcdef" for c in a.token):
        ap.error("Need a strong random hex token")
    run(a.root,a.token,a.host,a.port,a.ttl_seconds)
