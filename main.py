"""Bunnygram: runnable Python/pygame prototype of an always-plugged-in pet.
Run: pip install -r requirements.txt && python main.py
"""
import json
import os
import random
import textwrap
import threading
import time
import urllib.request
from pathlib import Path
import pygame
from game_rules import new_state, tick, feed, pet, toggle_sleep, mood, add_message, open_next
from generate_sprites import generate, SPRITES

HERE=Path(__file__).resolve().parent
CONFIG=HERE/'config.json'
STATEFILE=HERE/'data'/'pet_state.json'
W,H=240,240
WHITE=(253,235,243)
PINK=(255,154,192)
PALE=(173,146,167)
BLACK=(0,0,0)

def read_config():
    if not CONFIG.exists():CONFIG.write_text((HERE/'config.example.json').read_text(encoding='utf8'),encoding='utf8')
    return json.loads(CONFIG.read_text(encoding='utf8'))

def load_state():
    try:
        state=json.loads(STATEFILE.read_text(encoding='utf8'))
        defaults=new_state()
        for k,v in defaults.items():state.setdefault(k,v)
        return tick(state)
    except (OSError,ValueError,TypeError):return new_state()

def save_state(state):
    STATEFILE.parent.mkdir(parents=True,exist_ok=True)
    temp=STATEFILE.with_suffix('.tmp')
    temp.write_text(json.dumps(state,indent=2,ensure_ascii=False),encoding='utf8')
    temp.replace(STATEFILE)

def fetch_messages(url, bearer):
    if not url:return []
    req=urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'Bunnygram/1.0'})
    if bearer:req.add_header('Authorization','Bearer '+bearer)
    with urllib.request.urlopen(req,timeout=5) as response:
        if response.status!=200:raise ValueError('Inbox HTTP '+str(response.status))
        raw=response.read(128*1024)
    data=json.loads(raw)
    return data.get('messages',[]) if isinstance(data,dict) else []

class Poller:
    """Network thread writes to its own queue; only main thread updates game state."""
    def __init__(self, url, token, period):
        self.url=url;self.token=token;self.period=max(5.,float(period))
        self.items=[];self.lock=threading.Lock()
        self.stop=threading.Event()
        self.status='Offline mode' if not url else 'Connecting...'
        self.thread=None
        if url:
            self.thread=threading.Thread(target=self.run,daemon=True)
            self.thread.start()
    def run(self):
        while not self.stop.is_set():
            try:
                items=fetch_messages(self.url,self.token)
                with self.lock:
                    self.items.extend(items)
                    self.items=self.items[-300:]
                    self.status='Inbox online'
            except Exception as e:
                with self.lock:self.status='Inbox error: '+str(e)[:60]
            self.stop.wait(self.period)
    def pop(self):
        with self.lock:
            items,self.items=self.items,[]
            return items
    def shutdown(self):
        self.stop.set()
        if self.thread:self.thread.join(timeout=0.3)

def load_sprites():
    result={}
    for name in SPRITES:
        path=HERE/'assets'/f'{name}.png'
        try:
            im=pygame.image.load(str(path)).convert_alpha()
            if im.get_size()!=(32,32):im=pygame.transform.scale(im,(32,32))
            result[name]=im
        except Exception as e:print('Unable to load',path,e)
    return result

def write_text(surf,font,string,x,y,color=WHITE,center=False):
    rendered=font.render(string,False,color)
    surf.blit(rendered,(x-rendered.get_width()//2 if center else x,y))

def wrap_text(font, string, width):
    result=[]
    for paragraph in str(string).split('\n'):
        words=paragraph.split()
        line=''
        for word in words:
            candidate=(line+' '+word).strip()
            if font.size(candidate)[0]<=width:line=candidate
            else:
                if line:result.append(line)
                line=word
        result.append(line)
    return result

def bar(surf,small,label,value,y):
    write_text(surf,small,label,15,y,PALE)
    pygame.draw.rect(surf,(44,37,53),(67,y+3,137,7),border_radius=2)
    pygame.draw.rect(surf,PINK,(67,y+3,int(137*max(0,min(100,value))/100),7),border_radius=2)

def main():
    cfg=read_config()
    pygame.init()
    generate(force=False)
    scale=max(1,min(5,int(cfg.get('window_scale',3))))
    screen=pygame.display.set_mode((W*scale,H*scale),pygame.RESIZABLE)
    pygame.display.set_caption('Bunnygram - Tamagotchi Prototype | H: hologram mode')
    canvas=pygame.Surface((W,H))
    font=pygame.font.Font(None,20)
    small=pygame.font.Font(None,15)
    tiny=pygame.font.Font(None,13)
    sprite=load_sprites()
    state=load_state()
    poller=Poller(cfg.get('remote_inbox_url',''),cfg.get('remote_bearer_token',''),cfg.get('poll_seconds',30))
    clock=pygame.time.Clock()
    hud=True
    active=None
    action='Welcome home!'
    action_until=time.monotonic()+2.5
    anim=''
    anim_until=0.
    next_save=time.monotonic()+10
    demo_count=0
    blink_at=time.monotonic()+random.uniform(2.,6.)
    running=True
    try:
        while running:
            now=time.monotonic()
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT:running=False
                if ev.type!=pygame.KEYDOWN:continue
                if ev.key==pygame.K_q:running=False
                elif ev.key==pygame.K_h:hud=not hud
                elif ev.key==pygame.K_r:
                    sprite=load_sprites();action='Sprites reloaded';action_until=now+2
                elif ev.key==pygame.K_ESCAPE:active=None
                elif ev.key in (pygame.K_1,pygame.K_f):
                    action=feed(state);action_until=now+2.3
                    anim='eat';anim_until=now+2
                elif ev.key in (pygame.K_2,pygame.K_p):
                    action=pet(state);action_until=now+2.3
                    anim='happy';anim_until=now+2
                elif ev.key in (pygame.K_3,pygame.K_s):
                    action=toggle_sleep(state);action_until=now+2.3;active=None
                elif ev.key in (pygame.K_4,pygame.K_m):
                    active=open_next(state)
                    action='A letter for you!' if active else 'No letters yet!'
                    action_until=now+2.4
                    if active:anim='excited';anim_until=now+2
                elif ev.key in (pygame.K_d,pygame.K_g):
                    demo_count+=1
                    kind='gift' if ev.key==pygame.K_g else 'letter'
                    item={'id':f'demo-{time.time_ns()}-{demo_count}','type':kind,'from':'Your person',
                          'text':'Just a little reminder: you are loved, every single day. <3'}
                    if kind=='gift':item['gift']=random.choice(['flower','heart','cake'])
                    add_message(state,item)
                    action='New '+kind+' arrived!';action_until=now+3
            tick(state)
            for message in poller.pop():
                if add_message(state,message):
                    action='You have new mail!';action_until=now+3
            if now>=next_save:
                save_state(state);next_save=now+10
            canvas.fill(BLACK)
            if active:
                title='A LOVE LETTER' if active['type']=='letter' else 'A LITTLE GIFT'
                write_text(canvas,font,title,W//2,20,PINK,True)
                if active['type']=='gift':
                    symbol='icon_'+active.get('gift','heart')
                    if symbol not in sprite:symbol='icon_gift'
                    canvas.blit(pygame.transform.scale(sprite[symbol],(66,66)),(87,48))
                    top=125
                else:
                    icon=sprite['icon_letter']
                    canvas.blit(pygame.transform.scale(icon,(54,54)),(93,42))
                    top=108
                write_text(canvas,small,'FROM: '+active.get('from','Someone')[:25],W//2,top,PALE,True)
                y=top+21
                for ln in wrap_text(small,active.get('text',''),215)[:7]:
                    write_text(canvas,small,ln,W//2,y,WHITE,True);y+=15
                write_text(canvas,tiny,'ESC = CLOSE',W//2,224,PALE,True)
            else:
                if now<anim_until:mode=anim
                else:mode=mood(state)
                frame=int(now*3)%2
                if mode=='idle' and now>blink_at:
                    key='bunny_blink'
                    if now>blink_at+0.14:blink_at=now+random.uniform(2.0,6.0)
                elif mode=='idle':key='bunny_idle_'+str(frame)
                elif mode=='eat':key='bunny_eat_'+str(frame)
                else:key='bunny_'+mode
                if key not in sprite:key='bunny_idle_0'
                # central graphic on absolutely black background for the mirror
                shift=2 if mode=='happy' and frame else 0
                canvas.blit(pygame.transform.scale(sprite[key],(128,128)),(56,47-shift))
                if state['inbox']:
                    canvas.blit(pygame.transform.scale(sprite['icon_letter'],(36,36)),(181,30))
                    if int(now*2)%2:
                        write_text(canvas,small,'!',221,35,PINK)
                if mode=='happy' and now<anim_until:
                    canvas.blit(pygame.transform.scale(sprite['icon_heart'],(24,24)),(43,54))
                    canvas.blit(pygame.transform.scale(sprite['icon_heart'],(18,18)),(180,56))
                if hud:
                    write_text(canvas,font,state.get('name',cfg.get('pet_name','Mochi'))[:16],W//2,8,WHITE,True)
                    if state.get('sleeping'):
                        write_text(canvas,small,'Z Z Z',W//2,170,PALE,True)
                    elif now<action_until:
                        for i,line in enumerate(wrap_text(small,action,210)[:2]):
                            write_text(canvas,small,line,W//2,174+i*14,WHITE,True)
                    bar(canvas,small,'FOOD',state['hunger'],192)
                    bar(canvas,small,'LOVE',state['happiness'],206)
                    bar(canvas,small,'REST',state['energy'],220)
                    write_text(canvas,tiny,'1 Feed  2 Pet  3 Sleep  4 Mail',W//2,236,PALE,True)
            # Final output can be mirrored if the physical optics require it.
            # Screen rotation is NOT applied here; hardware-specific mounting comes later.
            dest=pygame.transform.scale(canvas,screen.get_size())
            screen.blit(dest,(0,0));pygame.display.flip();clock.tick(30)
    finally:
        poller.shutdown()
        save_state(state)
        pygame.quit()

if __name__=='__main__':main()
