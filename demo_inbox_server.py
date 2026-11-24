"""Local-only demo HTTP inbox; NOT internet-safe, not authenticated."""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

MESSAGES=[]
class Handler(BaseHTTPRequestHandler):
    def reply(self, status, data):
        body=json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers();self.wfile.write(body)
    def do_GET(self):
        if self.path!='/inbox':return self.reply(404,{'error':'not found'})
        self.reply(200,{'messages':MESSAGES})
    def do_POST(self):
        if self.path!='/send':return self.reply(404,{'error':'not found'})
        n=int(self.headers.get('Content-Length','0'))
        if n<1 or n>4096:return self.reply(400,{'error':'invalid payload length'})
        try:item=json.loads(self.rfile.read(n).decode('utf-8'))
        except Exception:return self.reply(400,{'error':'invalid JSON'})
        if not isinstance(item,dict) or not item.get('id') or item.get('type') not in ('letter','gift'):
            return self.reply(400,{'error':'expected id and type letter or gift'})
        MESSAGES.append(item)
        self.reply(201,{'status':'added','count':len(MESSAGES)})

if __name__=='__main__':
    print('LOCAL DEMO SERVER http://127.0.0.1:8765/inbox (Ctrl+C to stop)')
    HTTPServer(('127.0.0.1',8765),Handler).serve_forever()
