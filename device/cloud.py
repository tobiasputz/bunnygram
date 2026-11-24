"""Minimal fail-closed HTTPS relay client for MicroPython ESP32-S3.

Requires CA bundle in /trust_roots.pem. Deliberately DOES NOT fall back to
unverified TLS. Do not expose the local ESP32 HTTP listener to the internet.
"""
try:
    import ujson as json
except ImportError:
    import json
import socket
import ssl
import gc


class CloudClient:
    def __init__(self, base_url, device_token, ca_path='trust_roots.pem'):
        if not base_url.startswith('https://'):
            raise ValueError('Railway cloud URL must start with https://')
        rest = base_url[8:].strip('/')
        if not rest or '/' in rest or ':' in rest or len(rest) > 255:
            raise ValueError('Expected https://your-service.up.railway.app with no path')
        if len(device_token) < 32:
            raise ValueError('Device credential is too short')
        self.host = rest
        self.device_token = device_token
        with open(ca_path, 'rb') as f:
            self.ca = f.read()
        if b'BEGIN CERTIFICATE' not in self.ca:
            raise ValueError('Missing trustworthy CA certificates')

    @staticmethod
    def decode_http(raw):
        pos = raw.find(b'\r\n\r\n')
        if pos < 0:
            raise OSError('Invalid HTTP response')
        head, body = raw[:pos].decode('latin-1'), raw[pos+4:]
        first = head.split('\r\n', 1)[0].split(' ')
        if len(first) < 2:
            raise OSError('Malformed HTTP status')
        code = int(first[1])
        if code != 200:
            raise OSError('Railway HTTP status: ' + str(code))
        headers = {}
        for row in head.split('\r\n')[1:]:
            if ':' in row:
                k, v = row.split(':', 1)
                headers[k.lower().strip()] = v.strip().lower()
        if headers.get('transfer-encoding') == 'chunked':
            out = bytearray()
            while True:
                idx = body.find(b'\r\n')
                if idx < 0:
                    raise OSError('Incomplete chunk header')
                size = int(body[:idx].split(b';')[0], 16)
                body = body[idx+2:]
                if size == 0:
                    return bytes(out)
                if len(body) < size + 2 or body[size:size+2] != b'\r\n':
                    raise OSError('Incomplete HTTP chunk')
                out.extend(body[:size])
                body = body[size+2:]
        elif 'content-length' in headers and len(body) < int(headers['content-length']):
            raise OSError('Incomplete HTTP response')
        return body

    def request(self, method, path, payload=None):
        gc.collect()
        if not path.startswith('/') or ' ' in path:
            raise ValueError('Invalid path')
        body = json.dumps(payload).encode('utf-8') if payload is not None else b''
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.verify_mode = ssl.CERT_REQUIRED
        # MicroPython needs a CA chain explicitly; it has no universal system CA store.
        context.load_verify_locations(cadata=self.ca)
        info = socket.getaddrinfo(self.host, 443, 0, socket.SOCK_STREAM)[0]
        conn = socket.socket(info[0], info[1], info[2])
        tls = None
        try:
            conn.settimeout(10)
            conn.connect(info[-1])
            tls = context.wrap_socket(conn, server_hostname=self.host)
            conn = None
            lines = [method + ' ' + path + ' HTTP/1.1', 'Host: ' + self.host,
                     'User-Agent: Bunnygram-ESP32/5', 'Accept: application/json',
                     'Accept-Encoding: identity', 'Authorization: Bearer ' + self.device_token,
                     'Connection: close']
            if payload is not None:
                lines.extend(['Content-Type: application/json', 'Content-Length: ' + str(len(body))])
            data = ('\r\n'.join(lines) + '\r\n\r\n').encode('ascii') + body
            # SSL sockets on MicroPython support write(), not always sendall().
            while data:
                count = tls.write(data[:1024])
                if not count:
                    raise OSError('TLS write failed')
                data = data[count:]
            parts = bytearray()
            while True:
                block = tls.read(1024)
                if not block:
                    break
                parts.extend(block)
                if len(parts) > 24576:
                    raise OSError('Cloud response too large')
            raw = self.decode_http(parts)
            return json.loads(raw.decode('utf-8'))
        finally:
            try:
                if tls: tls.close()
                elif conn: conn.close()
            except Exception:
                pass
            gc.collect()

    def poll_and_report(self, companion):
        after = companion.state['last_remote_id']
        fetched = self.request('GET', '/api/device/commands?after=' + str(after))
        for message in fetched.get('commands', []):
            mid = message['id']
            if mid <= companion.state['last_remote_id']:
                continue
            cmd = message['payload']
            # Persist command AND cursor together, so replays after a reboot
            # cannot deliver a letter or other action twice.
            companion.command(cmd['action'], cmd, remote_id=mid)
        state = companion.status()
        return self.request('POST', '/api/device/state',
                            {'state': state, 'last_remote_id': companion.state['last_remote_id']})
