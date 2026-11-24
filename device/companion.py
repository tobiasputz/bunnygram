"""Portable Python companion state/behavior. No care meters or dependencies."""
try:
    import ujson as json
except ImportError:
    import json
import random
import time
import os

PETS = ('bunny', 'cat', 'fox', 'frog', 'cookie', 'bee')
DEFAULT_NAMES = ('Mochi', 'Miso', 'Pip', 'Puddle', 'Chip', 'Bumble')
FRAMES = ('idle_0','idle_1','blink','sit','wave_0','wave_1',
          'hop_0','hop_1','sleep','happy','curious','dance_0','dance_1','gift')
ACTIONS = ('idle','curious','sit','hop','wave','dance','sleep','blink')

def defaults():
    return {'pet':'bunny', 'names': dict(zip(PETS, DEFAULT_NAMES)),
            'brightness':85, 'mirror_x':False,'mirror_y':False,'rotation':1,
            'scale':4, 'display_on':True, 'mail':[], 'rev':0, 'last_remote_id':0, 'layout_version':5}

def ticks():
    return time.ticks_ms() if hasattr(time, 'ticks_ms') else int(time.monotonic()*1000)

def diff(a, b):
    return time.ticks_diff(a, b) if hasattr(time, 'ticks_diff') else a-b

def add(t, ms):
    return time.ticks_add(t, ms) if hasattr(time, 'ticks_add') else t+ms

class Companion:
    def __init__(self, path='state.json'):
        self.path=path
        self.state=defaults()
        try:
            with open(path) as f: raw=json.load(f)
            if raw.get('pet') in PETS: self.state['pet']=raw['pet']
            for p in PETS:
                if isinstance(raw.get('names',{}).get(p),str):
                    self.state['names'][p]=raw['names'][p][:24]
            for key in ('mirror_x','mirror_y','display_on'):
                if type(raw.get(key)) is bool: self.state[key]=raw[key]
            for key,lo,hi in (('rotation',0,3),('brightness',5,100),('scale',2,6)):
                v=raw.get(key)
                if type(v) is int and lo<=v<=hi:self.state[key]=v
            if raw.get('layout_version',0) < 5:
                self.state['rotation']=1  # one-time migration without wiping pet or mail
            if type(raw.get('last_remote_id')) is int and raw['last_remote_id']>=0:
                self.state['last_remote_id']=raw['last_remote_id']
            if isinstance(raw.get('mail'),list):
                self.state['mail']=[x for x in raw['mail'][-40:] if isinstance(x,dict)]
        except (OSError,ValueError,TypeError,KeyError): pass
        self.pose='idle'
        self.pose_started=ticks()
        self.pose_end=add(self.pose_started,4000)
        self.reaction_end=0
        self.counter=0
        self.last_frame=None

    def save(self):
        tmp=self.path+'.tmp'
        with open(tmp,'w') as f:json.dump(self.state,f)
        try:os.remove(self.path)
        except OSError:pass
        os.rename(tmp,self.path)

    def set_pose(self,pose,seconds=4):
        self.pose=pose
        self.pose_started=ticks()
        self.pose_end=add(self.pose_started,int(seconds*1000))
        self.reaction_end=self.pose_end

    def tick(self):
        now=ticks()
        if diff(now,self.pose_end)>=0:
            # Higher idle weighting; creature animations happen on their own.
            pool=('idle','idle','idle','idle','blink','sit','curious','hop','wave','dance','sleep')
            p=self.state['pet']
            bonus={'bunny':('sit','hop'), 'cat':('sleep','curious'),
                   'fox':('hop','dance'), 'frog':('sit','sleep'),
                   'cookie':('dance','sit'), 'bee':('hop','wave')}[p]
            self.pose=random.choice(pool+bonus)
            self.pose_started=now
            duration={'blink':300,'sleep':11000,'dance':4900,'hop':2700,'wave':3200}.get(self.pose,random.randint(4000,9000))
            self.pose_end=add(now,duration)
        elapsed=diff(now,self.pose_started)
        if self.pose=='idle':frame='idle_'+str((elapsed//680)%2)
        elif self.pose=='wave':frame='wave_'+str((elapsed//300)%2)
        elif self.pose=='hop':frame='hop_'+str((elapsed//240)%2)
        elif self.pose=='dance':frame='dance_'+str((elapsed//340)%2)
        elif self.pose=='blink':frame='blink'
        elif self.pose in FRAMES:frame=self.pose
        elif self.pose in ('heart','flower','star','present'):
            frame='gift'
        else:frame='idle_0'
        # Movement measured in native screen pixels; small and gentle.
        x_offset=0
        y_offset=0
        if self.state['pet']=='bee':
            y_offset=(-4,-2,0,2,4,2,0,-2)[(now//180)%8]
        if self.state['pet']=='cookie':x_offset=(-3,-2,0,2,3,2,0,-2)[(now//250)%8]
        if self.pose=='hop': y_offset-=12 if (elapsed//240)%2 else 0
        if self.pose=='dance': x_offset+=(-7 if (elapsed//340)%2 else 7)
        return frame,x_offset,y_offset

    def command(self,action,args=None,remote_id=None):
        args=args or {}
        s=self.state
        if action=='switch_pet':
            value=args.get('pet')
            if value not in PETS:raise ValueError('Unknown pet')
            s['pet']=value
            self.set_pose('wave',3)
        elif action=='rename':
            value=args.get('name','')
            if not isinstance(value,str) or not 1<=len(value.strip())<=24:raise ValueError('Name must be 1-24 characters')
            s['names'][s['pet']]=value.strip()
        elif action=='react':
            pose=args.get('reaction')
            if pose not in ('wave','hop','dance','happy','sleep','curious','heart','flower','star','present'):
                raise ValueError('Unknown reaction')
            self.set_pose(pose,7 if pose=='sleep' else 4)
        elif action=='setting':
            setting=args.get('setting')
            value=args.get('value')
            if setting in ('mirror_x','mirror_y','display_on') and type(value) is bool:
                s[setting]=value
            elif setting=='rotation' and type(value) is int and value in (0,1,2,3):s[setting]=value
            elif setting=='scale' and type(value) is int and 2<=value<=6:s[setting]=value
            elif setting=='brightness' and type(value) is int and 5<=value<=100:s[setting]=value
            else:raise ValueError('Invalid setting')
        elif action=='send_mail':
            message=args.get('text','')
            if not isinstance(message,str) or not 1<=len(message.strip())<=500:raise ValueError('Message must be 1-500 characters')
            sender=args.get('from','Someone')
            if not isinstance(sender,str) or len(sender)>32:raise ValueError('Invalid sender')
            item={'id':str(ticks())+'-'+str(random.randint(10000,99999)), 'from':sender or 'Someone',
                  'text':message.strip(),'opened':False}
            s['mail'].append(item)
            s['mail']=s['mail'][-40:]
            self.set_pose('gift',5)
        elif action=='open_mail':
            mid=args.get('id')
            matched=False
            for item in s['mail']:
                if item.get('id')==mid:
                    item['opened']=True; matched=True;break
            if not matched:raise ValueError('Message not found')
            self.set_pose('happy',3)
        else:raise ValueError('Unknown action')
        if remote_id is not None:
            if type(remote_id) is not int or remote_id<=s['last_remote_id']:
                raise ValueError('Stale remote command ID')
            s['last_remote_id']=remote_id
        s['rev']=s.get('rev',0)+1
        self.save()

    def status(self):
        s=self.state
        return {'pet':s['pet'], 'names':s['names'], 'pose':self.pose,
                'brightness':s['brightness'], 'mirror_x':s['mirror_x'],
                'mirror_y':s['mirror_y'], 'rotation':s['rotation'],
                'scale':s['scale'],'display_on':s['display_on'],
                'unread':sum(1 for x in s['mail'] if not x.get('opened')),
                'mail':list(reversed(s['mail'])), 'rev':s.get('rev',0),
                'last_remote_id':s['last_remote_id']}
