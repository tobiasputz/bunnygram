"""Bunnygram FNK0104B landscape display + Railway command sync."""
try:import ujson as json
except ImportError:import json
import gc,time
import network
from ili9341 import Display
from companion import Companion,ticks,diff,add,FRAMES,PETS
from cloud import CloudClient

with open('config.json') as f:cfg=json.load(f)
pet=Companion()
# In case the board was just flashed, favor the user's saved display state.
lcd=Display(rotation=pet.state['rotation'],brightness=pet.state['brightness'] if pet.state['display_on'] else 0)

wifi=network.WLAN(network.STA_IF)
wifi.active(True)

def connect_wifi():
    if wifi.isconnected():return wifi.ifconfig()[0]
    print('Connecting to Wi-Fi:',cfg['ssid'])
    try:wifi.connect(cfg['ssid'],cfg['wifi_password'])
    except Exception as exc:print('Wi-Fi start failed',exc);return None
    deadline=add(ticks(),18000)
    while diff(deadline,ticks())>0:
        if wifi.isconnected():
            ip=wifi.ifconfig()[0]
            if not cfg.get('railway_url'):
                print('LOCAL CONTROLLER: http://'+ip+'/')
            else:
                print('Wi-Fi connected; IP',ip)
            return ip
        time.sleep_ms(250)
    print('Wi-Fi unavailable; pet will keep animating offline.')
    return None

ip=connect_wifi()
controller=None
cloud=None
cloud_mode=bool(cfg.get('railway_url'))
if cloud_mode:
    try:
        cloud=CloudClient(cfg['railway_url'],cfg['device_token'])
        print('Railway remote controller:',cfg['railway_url'])
    except Exception as exc:
        print('Railway configuration/TLS trust error:',exc)
elif ip:
    from webserver import Controller
    try:controller=Controller(pet,cfg,ip)
    except Exception as exc:print('Phone controller start failed:',exc)

# TLS certificate verification requires correct system time.
def sync_clock():
    try:
        import ntptime
        ntptime.settime()
        print('Clock synchronized via NTP')
        return True
    except Exception as exc:
        print('Clock synchronization failed, cloud TLS may reject:',exc)
        return False
if ip and cloud_mode:sync_clock()
last_cloud_poll=add(ticks(),-16000)
last_time_sync=ticks()

frame_cache_key=None
frame_cache=None
last_draw=None
last_render=0
last_network_retry=ticks()
need_clear=False


def frame_for(pet_id,frame):
    global frame_cache_key,frame_cache
    key=(pet_id,frame)
    if frame_cache_key==key:return frame_cache
    number=FRAMES.index(frame)
    with open('assets/'+pet_id+'.bin','rb') as f:
        f.seek(number*2048)
        raw=f.read(2048)
    if len(raw)!=2048:raise OSError('Incomplete sprite: '+str(key))
    frame_cache_key=key
    frame_cache=raw
    return raw


def draw(now):
    global last_draw,last_render,need_clear
    st=pet.state
    if st['rotation']!=lcd.rotation:
        lcd.set_rotation(st['rotation'])
        lcd.fill(0)
        last_draw=None
    level=st['brightness'] if st['display_on'] else 0
    lcd.set_brightness(level)
    if not st['display_on']:
        last_draw=None
        need_clear=True
        return
    if need_clear:
        lcd.fill(0)
        need_clear=False
    frame,xoff,yoff=pet.tick()
    scale=min(st['scale'],min(lcd.width,lcd.height)//32)
    size=32*scale
    x=(lcd.width-size)//2+xoff
    y=(lcd.height-size)//2+yoff
    x=max(0,min(lcd.width-size,x))
    y=max(0,min(lcd.height-size,y))
    signature=(st['pet'],frame,x,y,scale,st['mirror_x'],st['mirror_y'])
    if signature==last_draw:return
    if last_draw is not None:
        ox,oy,osize=last_draw[2],last_draw[3],last_draw[4]*32
        lcd.fill_rect(ox,oy,osize,osize,0)
    pix=frame_for(st['pet'],frame)
    lcd.sprite(pix,x,y,scale,st['mirror_x'],st['mirror_y'])
    last_draw=signature
    last_render=now

if ip and not cloud_mode:
    try:
        lcd.fill(0)
        lcd.draw_ip(ip)
        time.sleep(4)
        lcd.fill(0)
    except Exception as exc: print('Startup address splash failed:',exc)
print('Bunnygram ready. 2.8in FNK0104B, landscape default 320x240.')
if not cloud_mode:print('LOCAL PAIRING CODE:',cfg.get('pairing_code','not configured'))
while True:
    now=ticks()
    if controller:
        controller.poll()
    if cloud and wifi.isconnected() and diff(now,last_cloud_poll)>10000:
        last_cloud_poll=now
        try:
            cloud.poll_and_report(pet)
        except Exception as exc:
            print('Railway polling failed (will retry, pet keeps animating):',exc)
    if cloud_mode and wifi.isconnected() and diff(now,last_time_sync)>86400000:
        last_time_sync=now
        sync_clock()
    if diff(now,last_network_retry)>30000:
        last_network_retry=now
        if not wifi.isconnected():
            ip=connect_wifi()
            if ip and cloud_mode:
                sync_clock()
            if ip and controller is None and not cloud_mode:
                from webserver import Controller
                try:controller=Controller(pet,cfg,ip)
                except Exception as exc:print('Controller error',exc)
    if diff(now,last_render)>140:  # ~7 FPS target; skips unchanged sprites
        try:draw(now)
        except Exception as exc:
            print('Display error:',exc)
            time.sleep_ms(500)
        last_render=now
    time.sleep_ms(10)
