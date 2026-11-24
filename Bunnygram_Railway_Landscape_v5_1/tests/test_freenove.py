import tempfile, unittest, sys, json, types, importlib.util
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'device'))
from companion import PETS,FRAMES,Companion

class SourceTests(unittest.TestCase):
    def test_six_pets_fourteen_frames(self):
        self.assertEqual(len(PETS),6)
        self.assertEqual(len(FRAMES),14)
        for pet in PETS:
            raw=(ROOT/'device'/'assets'/(pet+'.bin')).read_bytes()
            self.assertEqual(len(raw),14*32*32*2)
            for f in FRAMES:
                with Image.open(ROOT/'desktop'/'assets'/pet/(f+'.png')) as im:
                    self.assertEqual(im.size,(32,32))

    def test_switch_and_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            loc=str(Path(tmp)/'state.json')
            pet=Companion(loc)
            pet.command('switch_pet',{'pet':'cookie'})
            pet.command('rename',{'name':'Choco'})
            pet.command('send_mail',{'text':'Hello from me!','from':'Yours'})
            pet.command('open_mail',{'id':pet.state['mail'][0]['id']})
            loaded=Companion(loc)
            self.assertEqual(loaded.state['pet'],'cookie')
            self.assertEqual(loaded.state['names']['cookie'],'Choco')
            self.assertEqual(loaded.status()['unread'],0)
            self.assertEqual(loaded.state['mail'][0]['text'],'Hello from me!')

    def test_all_reactions_and_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            pet=Companion(str(Path(tmp)/'st.json'))
            for p in PETS:pet.command('switch_pet',{'pet':p})
            for r in ('wave','hop','dance','happy','sleep','curious','heart','flower','star','present'):
                pet.command('react',{'reaction':r})
                name,_,_=pet.tick()
                self.assertIn(name,FRAMES)
            for key,v in (('mirror_x',True),('mirror_y',True),('brightness',65),('rotation',2),('scale',5),('display_on',False)):
                pet.command('setting',{'setting':key,'value':v})
                self.assertEqual(pet.state[key],v)
            for key,v in (('brightness',0),('scale',9),('rotation',4),('mirror_x','true')):
                with self.assertRaises(ValueError):pet.command('setting',{'setting':key,'value':v})

    def test_phone_api_pair_switch_and_mail(self):
        import socket, threading, time
        from webserver import Controller
        with tempfile.TemporaryDirectory() as tmp:
            model=Companion(str(Path(tmp)/'state.json'))
            web=Controller(model, {'pairing_code':'12345678','auth_token':'abcdefghijklmnopqrstuvwxyz0123456789'},'127.0.0.1',port=0)
            port=web.sock.getsockname()[1]
            stop=threading.Event()
            def pump():
                while not stop.is_set():web.poll()
            thread=threading.Thread(target=pump, daemon=True);thread.start()
            def request(method,path,body=None,token=None):
                data=b'' if body is None else json.dumps(body).encode('utf-8')
                headers='Host: localhost\r\nConnection: close\r\n'
                if token:headers+='X-Bunnygram-Token: '+token+'\r\n'
                if method=='POST':headers+='Content-Type: application/json\r\nContent-Length: '+str(len(data))+'\r\n'
                raw=(method+' '+path+' HTTP/1.1\r\n'+headers+'\r\n').encode()+data
                with socket.create_connection(('127.0.0.1',port),timeout=2) as sock:
                    sock.sendall(raw)
                    out=bytearray()
                    while True:
                        part=sock.recv(8192)
                        if not part:break
                        out.extend(part)
                status=int(out.split(b' ',2)[1])
                content=bytes(out).split(b'\r\n\r\n',1)[1]
                return status,json.loads(content)
            try:
                self.assertEqual(request('GET','/api/state')[0],401)
                self.assertEqual(request('POST','/api/pair',{'code':'bad'})[0],403)
                status,answer=request('POST','/api/pair',{'code':'12345678'})
                self.assertEqual(status,200)
                token=answer['token']
                code,answer=request('POST','/api/action',{'action':'switch_pet','pet':'bee'},token)
                self.assertEqual((code,answer['state']['pet']),(200,'bee'))
                code,answer=request('GET','/api/state',token=token)
                self.assertEqual((code,answer['pet']),(200,'bee'))
            finally:
                stop.set();web.sock.close();thread.join(timeout=1)

    def test_driver_mock_spi(self):
        import time
        if not hasattr(time,'sleep_ms'):time.sleep_ms=lambda ms:None
        old=sys.modules.get('machine')
        class Pin:
            OUT=1
            def __init__(self,*args,**kwargs):pass
            def value(self,*args):return 1
        class PWM:
            def __init__(self,*args,**kwargs):pass
            def duty_u16(self,*args):pass
        class SPI:
            total=0
            writes=[]
            def __init__(self,*args,**kwargs):pass
            def write(self,buf):
                SPI.total+=len(buf)
                SPI.writes.append(bytes(buf))
        sys.modules['machine']=types.SimpleNamespace(Pin=Pin,PWM=PWM,SPI=SPI)
        try:
            from ili9341 import Display
            d=Display(rotation=0,brightness=85)
            # Confirm the hardware-verified ILI9341 inversion command
            # is applied by every new Display instance.
            self.assertIn(b'\x21', SPI.writes)
            self.assertEqual((d.width,d.height),(240,320))
            d.set_rotation(2)
            self.assertEqual((d.width,d.height),(240,320))
            d.set_rotation(1)
            self.assertEqual((d.width,d.height),(320,240))
            d.sprite((ROOT/'device/assets/bee.bin').read_bytes()[:2048],10,20,4,True,True)
            self.assertGreater(SPI.total,128*128*2)
            d.draw_ip('192.168.1.22')
        finally:
            if old is None:del sys.modules['machine']
            else:sys.modules['machine']=old

if __name__=='__main__':unittest.main()
