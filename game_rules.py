"""Game rules intentionally kept separate from pygame rendering.
All time is represented in UTC seconds. No network, display or board dependencies.
"""
import time

MAX_STAT=100

def clamp(x, lo=0, hi=MAX_STAT):return max(lo,min(hi,x))

def new_state(now=None):
    now=time.time() if now is None else now
    return {'name':'Mochi','hunger':80.,'happiness':82.,'energy':80.,
            'sleeping':False,'last_tick':now,'hearts':0,'flowers':0,'cakes':0,
            'letters_read':0,'inbox':[],'seen_ids':[]}

def tick(state, now=None):
    now=time.time() if now is None else now
    elapsed=max(0.,min(now-float(state.get('last_tick',now)), 48*3600.))
    state['last_tick']=now
    hours=elapsed/3600.
    state['hunger']=clamp(float(state.get('hunger',80))-hours*2.5)
    state['happiness']=clamp(float(state.get('happiness',80))-hours*(0.8 if state.get('sleeping') else 1.5))
    state['energy']=clamp(float(state.get('energy',80))+(hours*17 if state.get('sleeping') else -hours*3.2))
    return state

def feed(s):
    if s.get('sleeping'):return 'Wake me up first!'
    s['hunger']=clamp(s['hunger']+17); s['happiness']=clamp(s['happiness']+3)
    return 'Nom nom! Thank you!'

def pet(s):
    if s.get('sleeping'):return 'Zzz... (happy snooze)'
    s['happiness']=clamp(s['happiness']+13);s['energy']=clamp(s['energy']-1)
    return 'I love you! <3'

def toggle_sleep(s):
    s['sleeping']=not s.get('sleeping',False)
    return 'Sweet dreams...' if s['sleeping'] else 'Good morning!'

def mood(s):
    if s.get('sleeping'):return 'sleep'
    if s['hunger']<18 or s['happiness']<18:return 'sad'
    return 'idle'

def add_message(s, item):
    if not isinstance(item,dict):return False
    msg_id=str(item.get('id',''))[:120]
    if not msg_id or msg_id in s['seen_ids']:return False
    if item.get('type') not in ('letter','gift'):return False
    clean={'id':msg_id,'type':item['type'],'from':str(item.get('from','Someone special'))[:40],
           'text':str(item.get('text',''))[:600]}
    if clean['type']=='gift':clean['gift']=item.get('gift') if item.get('gift') in ('flower','cake','heart') else 'heart'
    s['seen_ids'].append(msg_id)
    s['seen_ids']=s['seen_ids'][-500:]
    s['inbox'].append(clean)
    s['inbox']=s['inbox'][-100:]
    return True

def open_next(s):
    if not s['inbox']:return None
    item=s['inbox'].pop(0)
    if item['type']=='letter':
        s['letters_read']+=1;s['happiness']=clamp(s['happiness']+10)
    else:
        kind=item['gift']
        s[{'heart':'hearts','flower':'flowers','cake':'cakes'}[kind]]+=1
        s['happiness']=clamp(s['happiness']+12)
        if kind=='cake':s['hunger']=clamp(s['hunger']+8)
    return item
