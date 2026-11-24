"""Bunnygram Railway relay: HTTPS dashboard + durable Postgres command queue.

Security: separate human sessions and device bearer; HttpOnly/SameSite cookies;
Origin + JSON checks for browser mutations; no direct inbound device connection.
"""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager, asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

HERE = Path(__file__).resolve().parent
DB_URL = os.getenv('DATABASE_URL', '')
PUBLIC_ORIGIN = os.getenv('PUBLIC_ORIGIN', '').rstrip('/')
OWNER_PASSWORD = os.getenv('OWNER_PASSWORD', '')
COMPANION_PASSWORD = os.getenv('COMPANION_PASSWORD', '')
DEVICE_TOKEN = os.getenv('DEVICE_TOKEN', '')
SESSION_SECRET = os.getenv('SESSION_SECRET', '')
SECURE_COOKIES = os.getenv('SECURE_COOKIES', '1') != '0'
SESSION_DURATION = 14 * 86400
LOGIN_FAILURES = {}




def required_config():
    needed = {'DATABASE_URL': DB_URL, 'PUBLIC_ORIGIN': PUBLIC_ORIGIN,
              'OWNER_PASSWORD': OWNER_PASSWORD, 'COMPANION_PASSWORD': COMPANION_PASSWORD,
              'DEVICE_TOKEN': DEVICE_TOKEN, 'SESSION_SECRET': SESSION_SECRET}
    missing = [k for k, value in needed.items() if not value]
    if missing:
        raise RuntimeError('Missing required environment variables: ' + ', '.join(missing))
    if len(DEVICE_TOKEN) < 32 or len(SESSION_SECRET) < 32:
        raise RuntimeError('DEVICE_TOKEN and SESSION_SECRET must each contain at least 32 characters')
    if min(len(OWNER_PASSWORD), len(COMPANION_PASSWORD)) < 12:
        raise RuntimeError('Both phone passwords must be at least 12 characters')
    if OWNER_PASSWORD == COMPANION_PASSWORD:
        raise RuntimeError('Owner and companion passwords must be different')
    if not (PUBLIC_ORIGIN.startswith('https://') or
            (not SECURE_COOKIES and PUBLIC_ORIGIN.startswith('http://127.0.0.1'))):
        raise RuntimeError('PUBLIC_ORIGIN must be HTTPS (except local development)')
    if not (DB_URL.startswith('postgresql://') or DB_URL.startswith('postgres://') or
            DB_URL.startswith('sqlite:///')):
        raise RuntimeError('DATABASE_URL must be PostgreSQL or a local sqlite:/// URL')
    if DB_URL.startswith('sqlite:///') and SECURE_COOKIES:
        raise RuntimeError('SQLite is intended for local testing only (SECURE_COOKIES=0)')


@contextmanager
def db():
    if DB_URL.startswith('sqlite:///'):
        c = sqlite3.connect(DB_URL[10:], timeout=10)
        c.row_factory = sqlite3.Row
    else:
        import psycopg
        from psycopg.rows import dict_row
        c = psycopg.connect(DB_URL, row_factory=dict_row)
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def run(c, query, params=()):
    if not isinstance(c, sqlite3.Connection):
        query = query.replace('?', '%s')
    return c.execute(query, params)


def initialize_db():
    is_sqlite = DB_URL.startswith('sqlite:///')
    with db() as c:
        run(c, """CREATE TABLE IF NOT EXISTS device_status (
            id INTEGER PRIMARY KEY, state_json TEXT NOT NULL,
            last_seen DOUBLE PRECISION NOT NULL DEFAULT 0,
            last_remote_id BIGINT NOT NULL DEFAULT 0)""")
        ident = 'INTEGER PRIMARY KEY AUTOINCREMENT' if is_sqlite else 'BIGSERIAL PRIMARY KEY'
        run(c, 'CREATE TABLE IF NOT EXISTS commands ('
               'id ' + ident + ', payload TEXT NOT NULL, created_at DOUBLE PRECISION NOT NULL, acked INTEGER NOT NULL DEFAULT 0)')
        run(c, 'CREATE INDEX IF NOT EXISTS idx_commands_ack ON commands(acked, id)')
        run(c, "INSERT INTO device_status (id,state_json) VALUES (1,'{}') ON CONFLICT(id) DO NOTHING")


@asynccontextmanager
async def lifespan(_app):
    required_config()
    initialize_db()
    yield


app = FastAPI(title='Bunnygram Railway', docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


@app.middleware('http')
async def headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    if SECURE_COOKIES:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response


def same_origin(request: Request):
    origin = request.headers.get('origin', '')
    if origin != PUBLIC_ORIGIN:
        raise HTTPException(403, 'Invalid request origin')
    if request.headers.get('content-type', '').split(';')[0] != 'application/json':
        raise HTTPException(415, 'JSON request required')


def make_session(role: str):
    data = f'{role}.{int(time.time()) + SESSION_DURATION}.{secrets.token_hex(16)}'
    mac = hmac.new(SESSION_SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()
    return f'{data}.{mac}'


def current_role(request: Request):
    value = request.cookies.get('bunnygram_session', '')
    bits = value.split('.')
    if len(bits) != 4 or bits[0] not in ('owner', 'companion'):
        raise HTTPException(401, 'Sign in on your phone')
    data = '.'.join(bits[:3])
    correct = hmac.new(SESSION_SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(correct, bits[3]):
        raise HTTPException(401, 'Invalid session')
    try:
        if int(bits[1]) < int(time.time()):
            raise HTTPException(401, 'Session expired')
    except ValueError:
        raise HTTPException(401, 'Invalid session')
    return bits[0]


def device_auth(auth: str):
    if not auth.startswith('Bearer ') or not hmac.compare_digest(auth[7:], DEVICE_TOKEN):
        raise HTTPException(401, 'Invalid device credentials')


class LoginBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    password: str = Field(min_length=1, max_length=256)


class ActionBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: str
    pet: str | None = None
    name: str | None = None
    reaction: str | None = None
    setting: str | None = None
    value: Any = None
    text: str | None = None
    sender: str | None = None
    id: str | None = None


class DeviceBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    state: dict
    last_remote_id: int = Field(ge=0)


def check_action(action: ActionBody, role: str):
    # Never pass arbitrary unvalidated commands to the microcontroller.
    cmd = action.action
    if cmd == 'switch_pet' and action.pet in ('bunny', 'cat', 'fox', 'frog', 'cookie', 'bee'):
        return {'action': cmd, 'pet': action.pet}
    if cmd == 'rename' and isinstance(action.name, str) and 1 <= len(action.name.strip()) <= 24:
        return {'action': cmd, 'name': action.name.strip()}
    if cmd == 'react' and action.reaction in ('wave','hop','dance','happy','sleep','curious','heart','flower','star','present'):
        return {'action': cmd, 'reaction': action.reaction}
    if cmd == 'setting':
        key, value = action.setting, action.value
        if key in ('mirror_x','mirror_y','display_on') and type(value) is bool:
            return {'action': cmd, 'setting': key, 'value': value}
        if key == 'rotation' and type(value) is int and value in (0,1,2,3):
            return {'action': cmd, 'setting': key, 'value': value}
        if key == 'scale' and type(value) is int and 2 <= value <= 6:
            return {'action': cmd, 'setting': key, 'value': value}
        if key == 'brightness' and type(value) is int and 5 <= value <= 100:
            return {'action': cmd, 'setting': key, 'value': value}
    if cmd == 'send_mail' and role == 'owner':
        if isinstance(action.text, str) and 1 <= len(action.text.strip()) <= 500:
            if action.sender is None or isinstance(action.sender, str) and len(action.sender) <= 32:
                return {'action': cmd, 'text': action.text.strip(), 'from': action.sender or 'Your person'}
    if cmd == 'open_mail' and isinstance(action.id, str) and 0 < len(action.id) <= 64:
        return {'action': cmd, 'id': action.id}
    raise HTTPException(400, 'Invalid command or insufficient permission')


@app.get('/')
def index():
    return FileResponse(HERE / 'static' / 'index.html')


@app.get('/app.css')
def css():
    return FileResponse(HERE / 'static' / 'app.css', media_type='text/css')


@app.get('/app.js')
def js():
    return FileResponse(HERE / 'static' / 'app.js', media_type='application/javascript')


@app.get('/health')
def health():
    return {'ok': True, 'service': 'bunnygram-relay'}


@app.post('/api/login')
def login(request: Request, body: LoginBody):
    same_origin(request)
    ip = request.client.host if request.client else 'unknown'
    now = time.monotonic()
    times = [t for t in LOGIN_FAILURES.get(ip, []) if now - t < 300]
    if len(times) >= 8:
        raise HTTPException(429, 'Too many failed attempts, please retry later')
    # Hash fixed-size digests for constant-time comparison even if lengths differ.
    guess = hashlib.sha256(body.password.encode()).digest()
    if hmac.compare_digest(guess, hashlib.sha256(OWNER_PASSWORD.encode()).digest()):
        role = 'owner'
    elif hmac.compare_digest(guess, hashlib.sha256(COMPANION_PASSWORD.encode()).digest()):
        role = 'companion'
    else:
        times.append(now)
        LOGIN_FAILURES[ip] = times
        raise HTTPException(401, 'Incorrect password')
    LOGIN_FAILURES.pop(ip, None)
    response = JSONResponse({'ok': True, 'role': role})
    response.set_cookie('bunnygram_session', make_session(role), max_age=SESSION_DURATION,
                        httponly=True, secure=SECURE_COOKIES, samesite='strict', path='/')
    return response


@app.post('/api/logout')
def logout(request: Request):
    same_origin(request)
    current_role(request)
    response = JSONResponse({'ok': True})
    response.delete_cookie('bunnygram_session', path='/', secure=SECURE_COOKIES, httponly=True, samesite='strict')
    return response


@app.get('/api/state')
def web_state(request: Request):
    role = current_role(request)
    with db() as c:
        row = run(c, 'SELECT state_json,last_seen,last_remote_id FROM device_status WHERE id=1').fetchone()
        queued = run(c, 'SELECT COUNT(*) AS count FROM commands WHERE acked=0').fetchone()['count']
    return {'role': role, 'state': json.loads(row['state_json']),
            'online': (time.time()-row['last_seen']) < 75, 'last_seen': row['last_seen'],
            'pending': queued, 'last_remote_id': row['last_remote_id']}


@app.post('/api/action')
def action(request: Request, body: ActionBody):
    same_origin(request)
    role = current_role(request)
    payload = check_action(body, role)
    with db() as c:
        row = run(c, 'INSERT INTO commands (payload, created_at, acked) VALUES (?,?,0) RETURNING id',
                  (json.dumps(payload, separators=(',', ':')), time.time())).fetchone()
    return {'queued': True, 'command_id': row['id']}


@app.get('/api/device/commands')
def commands(after: int = 0, authorization: str = Header(default='')):
    device_auth(authorization)
    if after < 0:
        raise HTTPException(400, 'Bad cursor')
    with db() as c:
        rows = run(c, 'SELECT id,payload FROM commands WHERE id>? AND acked=0 ORDER BY id LIMIT 12', (after,)).fetchall()
    return {'commands': [{'id': row['id'], 'payload': json.loads(row['payload'])} for row in rows]}


@app.post('/api/device/state')
def report(body: DeviceBody, authorization: str = Header(default='')):
    device_auth(authorization)
    state = body.state
    if len(json.dumps(state)) > 40000 or state.get('pet') not in ('bunny','cat','fox','frog','cookie','bee'):
        raise HTTPException(400, 'Invalid device state')
    if state.get('last_remote_id') != body.last_remote_id:
        raise HTTPException(400, 'State cursor mismatch')
    with db() as c:
        row = run(c, 'SELECT last_remote_id FROM device_status WHERE id=1').fetchone()
        cursor = max(row['last_remote_id'], body.last_remote_id)
        run(c, 'UPDATE device_status SET state_json=?, last_seen=?, last_remote_id=? WHERE id=1',
            (json.dumps(state, separators=(',', ':')), time.time(), cursor))
        run(c, 'UPDATE commands SET acked=1 WHERE id<=?', (cursor,))
    return {'ok': True, 'acknowledged_through': cursor}
