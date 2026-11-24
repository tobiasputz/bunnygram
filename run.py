"""Run desktop companion + LAN phone app. python run.py --port 8765"""
from __future__ import annotations
import argparse
import json
import os
import queue
import threading
import time
from pathlib import Path
from bunnygram.assets import generate
from bunnygram.display import Renderer
from bunnygram.model import Companion
from bunnygram.server import PhoneServer,local_ip

ROOT=Path(__file__).resolve().parent


def main(argv=None):
    ap=argparse.ArgumentParser(description='Bunnygram: floating pet + phone controller')
    ap.add_argument('--port',type=int,default=8765,help='Phone web app port, default 8765')
    ap.add_argument('--host',default='0.0.0.0',help='LAN interface; 127.0.0.1 = only this computer')
    ap.add_argument('--scale',type=int,default=3,help='Desktop window scale')
    args=ap.parse_args(argv)
    generate(force=False)
    import pygame
    pygame.init()
    renderer=Renderer(pygame,scale=max(1,min(5,args.scale)))
    model=Companion(ROOT/'data'/'companion_save.json')
    commands=queue.Queue(maxsize=100)
    preview={'lock':threading.Lock(),'png':None}
    try:
        srv=PhoneServer(model,commands,preview,port=args.port,bind=args.host)
    except OSError as e:
        pygame.quit()
        raise SystemExit(f'Could not start phone app on port {args.port}: {e}') from e
    srv.start()
    ip=local_ip()
    print('\n'+'='*63)
    print(' Bunnygram Floating Companion — phone controls are ON')
    print(f' On this computer:  http://127.0.0.1:{srv.port}')
    if args.host != '127.0.0.1':print(f' On your phone (same Wi-Fi): http://{ip}:{srv.port}')
    print(f' PAIRING CODE: {srv.pairing.code}')
    print(' Keep this code private. No buttons are required on the display.')
    print(' F1 = developer details; F11 = fullscreen; R = reload sprites')
    print('='*63+'\n')
    debug=False
    clock=pygame.time.Clock()
    next_save=time.monotonic()+10
    next_capture=0
    alive=True
    try:
        while alive:
            for event in pygame.event.get():
                if event.type==pygame.QUIT:alive=False
                elif event.type==pygame.KEYDOWN:
                    if event.key==pygame.K_ESCAPE:alive=False
                    elif event.key==pygame.K_F1:debug=not debug
                    elif event.key==pygame.K_F11:
                        model.apply('setting',{'setting':'fullscreen','value':not model.snapshot()['settings']['fullscreen']})
                    elif event.key==pygame.K_r:renderer.reload()
            for _ in range(50):
                try:action,data,reply=commands.get_nowait()
                except queue.Empty:break
                try:
                    if action=='reload_sprites':renderer.reload()
                    elif action=='save_screenshot':
                        path=ROOT/'screenshots'
                        path.mkdir(exist_ok=True)
                        target=path/('bunnygram_'+time.strftime('%Y%m%d_%H%M%S')+'.png')
                        pygame.image.save(renderer.canvas,str(target))
                    else:model.apply(action,data)
                    model.save()
                    reply.put_nowait({'ok':True})
                except Exception as e:
                    reply.put_nowait({'ok':False,'error':str(e)})
            model.tick()
            status=model.snapshot()
            renderer.fullscreen_set(status['settings']['fullscreen'])
            surface=renderer.render(status,time.monotonic(),debug=debug)
            renderer.present(surface)
            now=time.monotonic()
            if now>next_capture:
                raw=renderer.png(surface)
                with preview['lock']:preview['png']=raw
                next_capture=now+1.0
            if now>next_save:
                model.save();next_save=now+10
            clock.tick(30)
    finally:
        srv.stop()
        model.save()
        pygame.quit()
    return 0

if __name__=='__main__':raise SystemExit(main())
