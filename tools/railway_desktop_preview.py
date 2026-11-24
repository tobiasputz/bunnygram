"""Live desktop test of the SAME device model and RGB565 assets, with Railway commands.

Use while the physical board is OFF; both would otherwise consume one queue.
"""
import argparse
import json
import ssl
import sys
import threading
import time
import urllib.request
from pathlib import Path

from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'device'))
from companion import Companion, FRAMES


def cloud_request(url,token,method,path,body=None):
    data=json.dumps(body).encode() if body is not None else None
    req=urllib.request.Request(url+path,data=data,method=method,
                               headers={'Authorization':'Bearer '+token,'Accept':'application/json',
                                        'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=12,context=ssl.create_default_context()) as response:
        return json.load(response)


def worker(stop,pet,lock,url,token):
    while not stop.is_set():
        try:
            with lock: after=pet.state['last_remote_id']
            cmds=cloud_request(url,token,'GET','/api/device/commands?after='+str(after))['commands']
            for cmd in cmds:
                with lock:
                    if cmd['id']>pet.state['last_remote_id']:
                        pet.command(cmd['payload']['action'],cmd['payload'],remote_id=cmd['id'])
            with lock: state=pet.status()
            cloud_request(url,token,'POST','/api/device/state',
                          {'state':state,'last_remote_id':state['last_remote_id']})
        except Exception as exc:
            print('Cloud preview sync error:',exc)
        stop.wait(10)


def load_frame(pet,frame):
    with open(ROOT/'device'/'assets'/(pet+'.bin'),'rb') as f:
        f.seek(FRAMES.index(frame)*2048)
        data=f.read(2048)
    rgb=bytearray(32*32*3)
    for i in range(1024):
        v=(data[2*i]<<8)|data[2*i+1]
        rgb[i*3]=(v>>11)*255//31
        rgb[i*3+1]=((v>>5)&63)*255//63
        rgb[i*3+2]=(v&31)*255//31
    return Image.frombytes('RGB',(32,32),bytes(rgb))


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--offline',action='store_true',help='Preview locally without Railway')
    args=ap.parse_args()
    import pygame
    pygame.init()
    pet=Companion(str(ROOT/'local_settings'/'desktop_preview_state.json'))
    lock=threading.RLock()
    stop=threading.Event()
    worker_thread=None
    if not args.offline:
        conf=json.loads((ROOT/'local_settings'/'config.json').read_text())
        if not conf['railway_url'].startswith('https://'):
            raise SystemExit('Railway URL must be HTTPS')
        worker_thread=threading.Thread(target=worker,args=(stop,pet,lock,conf['railway_url'],conf['device_token']),daemon=True)
        worker_thread.start()
    display=pygame.display.set_mode((640,480))
    pygame.display.set_caption('Bunnygram — Railway landscape preview (stop physical ESP32 first)')
    clock=pygame.time.Clock()
    last_key=None
    cached_surface=None
    running=True
    while running:
        for evt in pygame.event.get():
            if evt.type==pygame.QUIT or evt.type==pygame.KEYDOWN and evt.key==pygame.K_ESCAPE:running=False
        with lock:
            frame,xoff,yoff=pet.tick()
            s=dict(pet.state)
        display.fill((0,0,0))
        if s['display_on']:
            scale=min(s['scale'],7)
            cache_key=(s['pet'],frame,s['mirror_x'],s['mirror_y'],scale)
            if cache_key!=last_key:
                im=load_frame(s['pet'],frame)
                if s['mirror_x']:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                if s['mirror_y']:im=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                im=im.resize((32*scale,32*scale),Image.Resampling.NEAREST)
                cached_surface=pygame.image.fromstring(im.tobytes(),im.size,'RGB')
                last_key=cache_key
            # Device uses 320x240; twice-sized preview window.
            size=32*scale
            xpos=(320-size)//2+xoff
            ypos=(240-size)//2+yoff
            display.blit(pygame.transform.scale(cached_surface,(size*2,size*2)),(xpos*2,ypos*2))
            # brightness is controlled by board hardware PWM; approximate it here
            if s['brightness']<100:
                shade=pygame.Surface((640,480));shade.fill((0,0,0));shade.set_alpha(int(255*(1-s['brightness']/100)))
                display.blit(shade,(0,0))
        pygame.display.flip()
        clock.tick(10)
    stop.set()
    if worker_thread:worker_thread.join(timeout=1)
    pet.save()
    pygame.quit()

if __name__=='__main__':main()
