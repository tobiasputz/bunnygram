import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / 'device'
if str(DEV) not in sys.path:sys.path.insert(0,str(DEV))
from companion import Companion
from cloud import CloudClient


class TestRailway(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        os.environ.update({
            'DATABASE_URL':'sqlite:///'+str(Path(self.tmp.name)/'relay.sqlite3'),
            'PUBLIC_ORIGIN':'http://127.0.0.1:8000',
            'OWNER_PASSWORD':'a-correct-long-owner-password',
            'COMPANION_PASSWORD':'another-long-companion-pass',
            'DEVICE_TOKEN':'x'*64,
            'SESSION_SECRET':'y'*64,
            'SECURE_COOKIES':'0',
        })
        name='bunnygram_server_test'
        spec=importlib.util.spec_from_file_location(name,ROOT/'railway'/'app.py')
        module=importlib.util.module_from_spec(spec)
        sys.modules[name]=module
        spec.loader.exec_module(module)
        self.mod=module
        self.c=TestClient(module.app)
        self.c.__enter__()
        self.origin={'Origin':'http://127.0.0.1:8000'}
        self.dev={'Authorization':'Bearer '+'x'*64}

    def tearDown(self):
        self.c.__exit__(None,None,None)
        self.tmp.cleanup()

    def login(self,password):
        return self.c.post('/api/login',json={'password':password},headers=self.origin)

    def test_security_and_permissions(self):
        self.assertEqual(self.c.get('/health').status_code,200)
        self.assertEqual(self.c.get('/api/state').status_code,401)
        self.assertEqual(self.c.get('/api/device/commands').status_code,401)
        self.assertEqual(self.c.post('/api/login',json={'password':'bad'}).status_code,403)
        self.assertEqual(self.login('bad').status_code,401)
        self.assertEqual(self.login('another-long-companion-pass').status_code,200)
        self.assertEqual(self.c.post('/api/action',json={'action':'send_mail','text':'hello'},headers=self.origin).status_code,400)
        self.assertEqual(self.c.post('/api/action',json={'action':'switch_pet','pet':'bee'}).status_code,403)
        self.assertEqual(self.c.post('/api/action',json={'action':'switch_pet','pet':'bee'},headers=self.origin).status_code,200)
        self.assertEqual(self.c.post('/api/action',json={'action':'setting','setting':'rotation','value':1},headers=self.origin).status_code,200)
        self.assertEqual(self.c.post('/api/action',json={'action':'setting','setting':'rotation','value':9},headers=self.origin).status_code,400)
        self.assertEqual(self.c.post('/api/action',json={'action':'send_mail','text':'bad'},headers={'Origin':'https://evil.example'}).status_code,403)

    def test_full_relay_reconnect_and_ack(self):
        self.assertEqual(self.login('a-correct-long-owner-password').status_code,200)
        data=self.c.post('/api/action',json={'action':'switch_pet','pet':'cookie'},headers=self.origin).json()
        self.assertTrue(data['queued'])
        self.c.post('/api/action',json={'action':'send_mail','text':'Hi honey','sender':'Partner'},headers=self.origin)
        self.assertEqual(self.c.get('/api/state').json()['pending'],2)
        got=self.c.get('/api/device/commands?after=0',headers=self.dev)
        self.assertEqual(got.status_code,200)
        queue=got.json()['commands']
        self.assertEqual([x['payload']['action'] for x in queue],['switch_pet','send_mail'])
        model=Companion(path=str(Path(self.tmp.name)/'board_state.json'))
        self.assertEqual(model.state['rotation'],1)
        for cmd in queue:model.command(cmd['payload']['action'],cmd['payload'],remote_id=cmd['id'])
        state=model.status()
        r=self.c.post('/api/device/state',headers=self.dev,json={'state':state,'last_remote_id':state['last_remote_id']})
        self.assertEqual(r.status_code,200,r.text)
        panel=self.c.get('/api/state').json()
        self.assertTrue(panel['online'])
        self.assertEqual(panel['state']['pet'],'cookie')
        self.assertEqual(panel['pending'],0)
        self.assertEqual(len(panel['state']['mail']),1)
        self.assertEqual(self.c.get('/api/device/commands?after=0',headers=self.dev).json()['commands'],[])
        restarted=Companion(path=str(Path(self.tmp.name)/'board_state.json'))
        self.assertEqual(restarted.state['last_remote_id'],queue[-1]['id'])
        self.assertEqual(len(restarted.status()['mail']),1)

    def test_reject_forged_device_state(self):
        a=self.c.post('/api/device/state',headers=self.dev,json={'state':{'pet':'bunny','last_remote_id':1},'last_remote_id':9})
        self.assertEqual(a.status_code,400)
        self.assertEqual(self.c.get('/api/device/commands?after=0',headers={'Authorization':'Bearer invalid'}).status_code,401)

    def test_cloud_http_parser(self):
        raw=b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n4\r\n{"a"\r\n3\r\n:1}\r\n0\r\n\r\n'
        self.assertEqual(CloudClient.decode_http(raw),b'{"a":1}')
        with self.assertRaises(OSError):CloudClient.decode_http(b'HTTP/1.1 302 Found\r\n\r\n')

    def test_landscape_migrates_old_state(self):
        saved=Path(self.tmp.name)/'old.json'
        saved.write_text(json.dumps({'pet':'frog','rotation':0,'mail':[{'id':'test','text':'hi','opened':False}]}))
        model=Companion(path=str(saved))
        self.assertEqual(model.state['rotation'],1)
        self.assertEqual(model.state['pet'],'frog')
        self.assertEqual(len(model.state['mail']),1)
        model.save()
        model2=Companion(path=str(saved))
        self.assertEqual(model2.state['rotation'],1)
        model2.command('setting',{'setting':'rotation','value':3})
        self.assertEqual(Companion(path=str(saved)).state['rotation'],3)


if __name__=='__main__':unittest.main()
