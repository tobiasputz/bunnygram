"""Small no-cloud phone controller. Bind on local LAN only; do not port-forward.
Phone must pair using the 6-digit code printed on host computer.
"""
from __future__ import annotations
import json
import queue
import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'web'
ASSETS = ROOT / 'assets'


def local_ip():
    """Get an approximate LAN IP without transmitting data externally."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(('192.0.2.1', 80))
        return sock.getsockname()[0]
    except OSError:
        return '127.0.0.1'
    finally:
        sock.close()


class Pairing:
    def __init__(self, path):
        self.path = Path(path)
        self.code = f'{secrets.randbelow(1000000):06d}'
        self.token = secrets.token_urlsafe(32)
        self.failed = {}
        self.lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Reusing a controller after an app restart is convenient; the pairing
        # code changes each session, but saved paired devices stay authorized.
        try:
            prior = json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(prior.get('token'), str) and len(prior['token']) >= 30:
                self.token = prior['token']
        except (OSError, ValueError, TypeError):
            pass
        self.path.write_text(json.dumps({'token': self.token}), encoding='utf-8')
        try:self.path.chmod(0o600)
        except OSError:pass

    def allowed(self, supplied):
        return isinstance(supplied, str) and secrets.compare_digest(self.token, supplied)

    def pair(self, ip, code):
        now = time.monotonic()
        with self.lock:
            attempts, since = self.failed.get(ip, (0, now))
            if now - since > 180:
                attempts, since = 0, now
            if attempts >= 8:
                return False, 'Too many attempts. Retry in a few minutes.'
            if not isinstance(code, str) or not secrets.compare_digest(self.code, code):
                self.failed[ip] = (attempts + 1, since)
                return False, 'Incorrect pairing code'
            self.failed.pop(ip, None)
            return True, self.token


class PhoneServer:
    def __init__(self, companion, command_queue, preview, port=8765, bind='0.0.0.0', security_file=None):
        self.companion=companion
        self.commands=command_queue
        self.preview=preview
        self.pairing=Pairing(security_file or ROOT/'data'/'controller_secrets.json')
        outer=self

        class Handler(BaseHTTPRequestHandler):
            server_version='BunnygramPhone/3.0'
            def log_message(self, format, *args):
                if self.path.startswith('/api/health'):return
                if self.path.startswith('/api/status'):return
                if self.path.startswith('/api/preview'):return
                return super().log_message(format,*args)

            def response(self, code, payload):
                raw=json.dumps(payload,ensure_ascii=False).encode('utf-8')
                self.send_response(code)
                self.send_header('Content-Type','application/json; charset=utf-8')
                self.send_header('Content-Length',str(len(raw)))
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.end_headers()
                try:self.wfile.write(raw)
                except (BrokenPipeError,ConnectionResetError):pass

            def file_response(self, path, mime):
                try:raw=path.read_bytes()
                except OSError:return self.response(404,{'error':'Not found'})
                self.send_response(200)
                self.send_header('Content-Type',mime)
                self.send_header('Content-Length',str(len(raw)))
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.end_headers()
                try:self.wfile.write(raw)
                except (BrokenPipeError,ConnectionResetError):pass

            def authorized(self):
                token=self.headers.get('X-Bunnygram-Token','')
                if not outer.pairing.allowed(token):
                    self.response(401,{'error':'Pair your phone to connect'})
                    return False
                return True

            def json_body(self):
                try:n=int(self.headers.get('Content-Length','0'))
                except ValueError:raise ValueError('Invalid Content-Length') from None
                if n < 1 or n > 8192:raise ValueError('Invalid request size')
                try:payload=json.loads(self.rfile.read(n).decode('utf-8'))
                except (ValueError,UnicodeDecodeError):raise ValueError('Invalid JSON') from None
                if not isinstance(payload,dict):raise ValueError('Expected JSON object')
                return payload

            def do_GET(self):
                path=unquote(urlsplit(self.path).path)
                if path == '/':return self.file_response(WEB/'index.html','text/html; charset=utf-8')
                if path == '/app.css':return self.file_response(WEB/'app.css','text/css; charset=utf-8')
                if path == '/app.js':return self.file_response(WEB/'app.js','application/javascript; charset=utf-8')
                if path == '/favicon.png':return self.file_response(ASSETS/'icons'/'heart.png','image/png')
                if path == '/api/health':return self.response(200,{'ok':True,'app':'Bunnygram Floating Companion'})
                if path == '/api/status':
                    if not self.authorized():return
                    return self.response(200,outer.companion.snapshot())
                if path == '/api/preview':
                    if not self.authorized():return
                    with outer.preview['lock']:
                        raw=outer.preview['png']
                    if not raw:return self.response(503,{'error':'Preview not ready'})
                    self.send_response(200)
                    self.send_header('Content-Type','image/png')
                    self.send_header('Cache-Control','no-store')
                    self.send_header('Content-Length',str(len(raw)))
                    self.end_headers()
                    try:self.wfile.write(raw)
                    except (BrokenPipeError,ConnectionResetError):pass
                    return
                if path.startswith('/assets/'):
                    relative=Path(path[len('/assets/'):])
                    if not path.lower().endswith('.png') or relative.is_absolute():
                        return self.response(404,{'error':'Not found'})
                    target=(ASSETS/relative).resolve()
                    if not target.is_relative_to(ASSETS.resolve()):
                        return self.response(403,{'error':'Forbidden'})
                    return self.file_response(target,'image/png')
                return self.response(404,{'error':'Not found'})

            def do_POST(self):
                path=unquote(urlsplit(self.path).path)
                try:data=self.json_body()
                except ValueError as e:return self.response(400,{'error':str(e)})
                if path == '/api/pair':
                    ok,result=outer.pairing.pair(self.client_address[0],data.get('code'))
                    return self.response(200 if ok else 403,
                                         {'token':result} if ok else {'error':result})
                if path != '/api/action':return self.response(404,{'error':'Not found'})
                if not self.authorized():return
                action=data.get('action')
                if not isinstance(action,str):return self.response(400,{'error':'Missing action'})
                # Validate most errors synchronously; display thread is the
                # only writer to the game state, including triggered reactions.
                reply=queue.Queue(maxsize=1)
                try:outer.commands.put_nowait((action,data,reply))
                except queue.Full:return self.response(503,{'error':'Command queue full'})
                try:result=reply.get(timeout=3)
                except queue.Empty:return self.response(503,{'error':'Display not responding'})
                self.response(200 if result.get('ok') else 400,result)

        class Server(ThreadingHTTPServer):
            daemon_threads=True
            allow_reuse_address=True
        self.httpd=Server((bind,port), Handler)
        self.port=self.httpd.server_address[1]
        self.thread=None

    def start(self):
        self.thread=threading.Thread(target=self.httpd.serve_forever,daemon=True,name='BunnygramPhone')
        self.thread.start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        if self.thread:self.thread.join(timeout=2)
