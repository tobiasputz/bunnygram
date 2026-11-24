"""Tiny same-LAN-only HTTP phone controller. Do NOT expose to the Internet."""
try:import ujson as json
except ImportError:import json
import socket
import time

class Controller:
    def __init__(self, pet, conf, ip, port=80):
        self.pet=pet
        self.pin=conf['pairing_code']
        self.token=conf['auth_token']
        self.ip=ip
        self.failed=0
        self.last_failed=0
        self.sock=socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        self.sock.bind(('0.0.0.0',port))
        self.sock.listen(2)
        self.sock.settimeout(0.008)

    def _answer(self, client, status, payload, mime='application/json; charset=utf-8'):
        if not isinstance(payload,bytes):
            payload=json.dumps(payload).encode('utf-8')
        codes={200:'OK',400:'Bad Request',401:'Unauthorized',403:'Forbidden',404:'Not Found',413:'Payload Too Large',429:'Too Many Requests'}
        header=('HTTP/1.1 %d %s\r\nContent-Type: %s\r\nContent-Length: %d\r\n'
                'Cache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n')%(status,codes.get(status,'Error'),mime,len(payload))
        client.sendall(header.encode('ascii'))
        client.sendall(payload)

    def poll(self):
        try:conn,_=self.sock.accept()
        except OSError:return
        try:
            conn.settimeout(0.6)
            self._handle(conn)
        except Exception as exc:
            print('Web request error:',exc)
        finally:
            try:conn.close()
            except Exception:pass

    def _handle(self,c):
        data=bytearray()
        while b'\r\n\r\n' not in data and len(data)<4096:
            part=c.recv(1024)
            if not part:return
            data.extend(part)
        if b'\r\n\r\n' not in data:
            return self._answer(c,413,{'error':'Headers too large'})
        head,tail=bytes(data).split(b'\r\n\r\n',1)
        lines=head.decode('utf-8').split('\r\n')
        first=lines[0].split(' ')
        if len(first)<2:return self._answer(c,400,{'error':'Bad request'})
        method,path=first[:2]
        headers={}
        for line in lines[1:]:
            if ':' in line:
                k,v=line.split(':',1);headers[k.lower().strip()]=v.strip()
        if method=='GET' and path=='/':
            # Streaming from flash avoids holding the full HTML in the heap.
            with open('phone.html','rb') as f:page=f.read()
            return self._answer(c,200,page,'text/html; charset=utf-8')
        if method=='GET' and path=='/api/health':
            return self._answer(c,200,{'ok':True,'board':'Freenove FNK0104B','ip':self.ip})
        if method=='GET' and path=='/api/state':
            if headers.get('x-bunnygram-token')!=self.token:
                return self._answer(c,401,{'error':'Pair first'})
            return self._answer(c,200,self.pet.status())
        if method!='POST' or path not in ('/api/pair','/api/action'):
            return self._answer(c,404,{'error':'Not found'})
        if headers.get('content-type','').split(';')[0].strip()!='application/json':
            return self._answer(c,400,{'error':'JSON expected'})
        try:content_length=int(headers.get('content-length','0'))
        except ValueError:content_length=-1
        if content_length<1 or content_length>2048:
            return self._answer(c,413,{'error':'Request too large'})
        body=bytearray(tail)
        while len(body)<content_length:
            part=c.recv(min(1024,content_length-len(body)))
            if not part:break
            body.extend(part)
        if len(body)!=content_length:return self._answer(c,400,{'error':'Incomplete request'})
        try:payload=json.loads(body.decode('utf-8'))
        except (ValueError,UnicodeError):return self._answer(c,400,{'error':'Invalid JSON'})
        if not isinstance(payload,dict):return self._answer(c,400,{'error':'Invalid payload'})
        if path=='/api/pair':
            now=time.time()
            if now-self.last_failed>180:self.failed=0
            if self.failed>=8:return self._answer(c,429,{'error':'Too many attempts; restart or retry later'})
            if payload.get('code')!=self.pin:
                self.failed+=1;self.last_failed=now
                return self._answer(c,403,{'error':'Wrong pairing code'})
            self.failed=0
            return self._answer(c,200,{'token':self.token})
        if headers.get('x-bunnygram-token')!=self.token:
            return self._answer(c,401,{'error':'Pair first'})
        try:self.pet.command(payload.get('action'),payload)
        except (ValueError,TypeError) as exc:return self._answer(c,400,{'error':str(exc)})
        return self._answer(c,200,{'ok':True,'state':self.pet.status()})
