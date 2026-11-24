"""Generate editable 32x32 placeholder sprites using Pillow.
Existing files are never overwritten unless --force is supplied.
"""
import os
import sys
from PIL import Image, ImageDraw

ROOT = os.path.dirname(__file__)
ASSETS = os.path.join(ROOT, 'assets')
S = 32
C = {'outline': '#60485e', 'body':'#f9d8e8', 'light':'#fff0f6', 'pink':'#ee95b5',
     'shadow':'#deafc5', 'eyes':'#493b58', 'blush':'#f3a5b5', 'green':'#7ccd87',
     'darkgreen':'#438d61','yellow':'#ffca65','red':'#f27b94','white':'#fdf4ee'}

def rect(s, color, x,y,w,h):
    ImageDraw.Draw(s).rectangle((x,y,x+w-1,y+h-1), fill=color)

def bunny(mode='idle', variant=0):
    s=Image.new('RGBA',(S,S),(0,0,0,0))
    oy = 1 if variant else 0
    # ears
    rect(s,C['outline'],7,2+oy,7,16);rect(s,C['outline'],19,2+oy,7,16)
    rect(s,C['body'],8,3+oy,5,14);rect(s,C['body'],20,3+oy,5,14)
    rect(s,C['pink'],10,5+oy,2,10);rect(s,C['pink'],22,5+oy,2,10)
    # body + head
    rect(s,C['outline'],7,19+oy,19,11);rect(s,C['body'],8,20+oy,17,9)
    rect(s,C['light'],12,23+oy,9,5)
    rect(s,C['outline'],4,12+oy,25,15);rect(s,C['body'],5,13+oy,23,13)
    rect(s,C['light'],8,14+oy,17,8)
    if mode in ('sleep','blink','happy'):
        rect(s,C['eyes'],10,19+oy,5,1);rect(s,C['eyes'],20,19+oy,5,1)
        if mode=='happy':rect(s,C['pink'],16,23+oy,2,2)
    elif mode=='sad':
        rect(s,C['eyes'],11,17+oy,3,3);rect(s,C['eyes'],21,17+oy,3,3)
        rect(s,C['eyes'],16,23+oy,3,1)
    else:
        rect(s,C['eyes'],11,17+oy,3,4);rect(s,C['eyes'],21,17+oy,3,4)
        rect(s,C['pink'],16,22+oy,3,2)
    rect(s,C['blush'],6,22+oy,4,2);rect(s,C['blush'],25,22+oy,3,2)
    if mode == 'eat':
        rect(s,C['green'],16,24+oy,5,5)
        if variant: rect(s,C['darkgreen'],17,24+oy,3,2)
    if mode == 'sleep':
        rect(s,'#b2d8fa',25,5,2,2);rect(s,'#b2d8fa',28,2,3,1)
    if mode == 'excited':
        rect(s,C['pink'],2,5,3,2);rect(s,C['pink'],29,8,2,3)
    return s

def icon(name):
    s=Image.new('RGBA',(S,S),(0,0,0,0))
    if name=='heart':
        for x,y,w,h in [(8,8,6,5),(18,8,6,5),(6,12,20,7),(9,19,14,4),(13,23,6,4)]:rect(s,C['red'],x,y,w,h)
    elif name=='letter':
        rect(s,C['outline'],5,9,23,16);rect(s,C['white'],6,10,21,14)
        ImageDraw.Draw(s).line([(7,11),(16,19)],fill=C['pink'],width=2);ImageDraw.Draw(s).line([(26,11),(16,19)],fill=C['pink'],width=2)
    elif name=='flower':
        rect(s,C['darkgreen'],15,17,3,12)
        for x,y in [(11,7),(19,7),(7,14),(23,14),(11,19),(19,19)]:rect(s,C['pink'],x,y,6,6)
        rect(s,C['yellow'],14,12,6,6)
    elif name=='cake':
        rect(s,C['outline'],7,15,19,14);rect(s,C['pink'],8,16,17,11)
        rect(s,C['white'],8,16,17,5);rect(s,C['yellow'],16,5,2,10);rect(s,C['red'],16,2,2,4)
    elif name=='gift':
        rect(s,C['outline'],6,11,21,18);rect(s,C['pink'],7,12,19,15)
        rect(s,C['yellow'],15,11,4,17);rect(s,C['yellow'],7,17,19,3)
        rect(s,C['red'],11,7,5,5);rect(s,C['red'],18,7,5,5)
    return s

SPRITES = {
 'bunny_idle_0': lambda:bunny('idle',0),
 'bunny_idle_1': lambda:bunny('idle',1),
 'bunny_blink': lambda:bunny('blink'),
 'bunny_happy': lambda:bunny('happy'),
 'bunny_eat_0': lambda:bunny('eat',0),
 'bunny_eat_1': lambda:bunny('eat',1),
 'bunny_sleep': lambda:bunny('sleep'),
 'bunny_sad': lambda:bunny('sad'),
 'bunny_excited': lambda:bunny('excited'),
 **{f'icon_{n}': (lambda k=n:icon(k)) for n in ['heart','letter','flower','cake','gift']}
}

def generate(force=False):
    os.makedirs(ASSETS,exist_ok=True)
    for name, make in SPRITES.items():
        path=os.path.join(ASSETS,name+'.png')
        if force or not os.path.isfile(path):make().save(path)
    print(f'Generated / verified {len(SPRITES)} sprites in {ASSETS}')

if __name__=='__main__':generate('--force' in sys.argv)
