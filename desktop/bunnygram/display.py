"""Pygame renderer. Pixel art on absolute black for Pepper's Ghost optics."""
from __future__ import annotations
import io
import math
from pathlib import Path
from PIL import Image
from .assets import ASSETS, STATES, ICONS, PETS

SIZE=240
BLACK=(0,0,0)


class Renderer:
    def __init__(self, pygame, scale=3):
        self.pg=pygame
        self.scale=scale
        self.sprites={}
        self.icons={}
        self.fullscreen=False
        self.canvas=pygame.Surface((SIZE,SIZE))
        self.screen=pygame.display.set_mode((SIZE*scale,SIZE*scale), pygame.RESIZABLE)
        pygame.display.set_caption('Bunnygram · Floating Companion · Phone-controlled')
        self.font=pygame.font.Font(None,15)
        self.small=pygame.font.Font(None,13)
        self.reload()

    def reload(self):
        self.sprites={}
        for pet in PETS:
            for name in STATES:
                try:
                    self.sprites[(pet,name)]=self.pg.image.load(str(ASSETS/pet/(name+'.png'))).convert_alpha()
                except Exception as e:
                    print('Missing sprite',pet,name,e)
        self.icons={}
        for icon in ICONS:
            try:self.icons[icon]=self.pg.image.load(str(ASSETS/'icons'/(icon+'.png'))).convert_alpha()
            except Exception as e:print('Missing icon',icon,e)

    def fullscreen_set(self, enabled):
        if enabled == self.fullscreen:return
        self.fullscreen=enabled
        flags=self.pg.FULLSCREEN if enabled else self.pg.RESIZABLE
        self.screen=self.pg.display.set_mode((0,0) if enabled else (SIZE*self.scale,SIZE*self.scale),flags)

    def _frame(self, behavior, secs):
        period=int(secs*3.5)%2
        if behavior in ('wave','hop','dance'):
            return behavior+'_'+str(period)
        if behavior in ('heart','flower','star','present','happy'):
            return 'happy'
        if behavior in ('sleep','curious','sit','blink'):
            return behavior
        return 'idle_'+str(period)

    def render(self, status, t, debug=False):
        pg=self.pg
        bg=self.canvas
        bg.fill(BLACK)
        settings=status['settings']
        if settings['display_on']:
            beh=status['activity']
            pet=status['pet']
            frame=self._frame(beh,t)
            sprite=self.sprites.get((pet,frame)) or self.sprites.get((pet,'idle_0'))
            if sprite is not None:
                # 32 pixel sprite -> 144px is deliberately nearest-neighbor.
                sprite=pg.transform.scale(sprite,(144,144))
                # Each character drifts gently on the otherwise pure-black stage.
                # A bee actually hovers, while the cookie rocks in place.
                resting = beh in ('sleep', 'sit')
                if pet == 'bee':
                    x = 48 + round(math.sin(t * 0.9) * (4 if resting else 17))
                    y = 45 + (0 if resting else round(math.sin(t * 2.8) * 7))
                elif pet == 'cookie':
                    x = 48 + round(math.sin(t * 0.55) * (2 if resting else 6))
                    y = 48 + (0 if resting else round(math.sin(t * 2.0) * 2))
                else:
                    x = 48 + round(math.sin(t * 0.33) * (3 if resting else 10))
                    y = 48 + (0 if resting else round(math.sin(t * 2.5) * 2))
                if beh == 'hop':
                    y -= round(abs(math.sin(t*8)) * 22)
                bg.blit(sprite, (x, y))
            eff={"heart":"heart","flower":"flower","star":"star","present":"present"}.get(beh)
            if eff and eff in self.icons:
                icon=pg.transform.scale(self.icons[eff],(40,40))
                dx=round(math.sin(t*2.8)*5)
                dy=round(math.sin(t*3.1)*8)
                bg.blit(icon,(159+dx,33+dy))
            elif beh in ('wave','happy','dance') and 'heart' in self.icons:
                icon=pg.transform.scale(self.icons['heart'],(22,22))
                bg.blit(icon,(178,60+round(math.sin(t*2)*3)))
            if status['unread'] and 'letter' in self.icons:
                # Tiny free-floating letter; no room or interface in glass.
                icon=pg.transform.scale(self.icons['letter'],(28,28))
                bg.blit(icon,(185,18+round(math.sin(t*3)*4)))
            if settings['show_preview_border']:
                pg.draw.rect(bg,(58,45,71),(1,1,238,238),1)
            brightness=settings['brightness']
            if brightness<100:
                dark=pg.Surface((SIZE,SIZE),pg.SRCALPHA)
                dark.fill((0,0,0,int(255*(1-brightness/100))))
                bg.blit(dark,(0,0))
        # Optional horizontal flip and 180° rotation accommodate real optics.
        output=bg
        if settings['mirror_horizontal']:
            output=pg.transform.flip(output,True,False)
        if settings['rotate_180']:
            output=pg.transform.rotate(output,180)
        if debug:
            output=output.copy()
            txt=f"{status['pet_name']}  [{status['activity']}]  unread:{status['unread']}"
            output.blit(self.font.render(txt,False,(230,180,214)),(5,5))
            output.blit(self.small.render('F1: debug · F11: fullscreen · R: reload',False,(150,132,155)),(5,227))
        return output

    def present(self, output):
        # pygame's default transform.scale preserves the hard pixel art edges.
        w,h=self.screen.get_size()
        side=min(w,h)
        img=self.pg.transform.scale(output,(side,side))
        self.screen.fill(BLACK)
        self.screen.blit(img,((w-side)//2,(h-side)//2))
        self.pg.display.flip()

    def png(self, surface):
        # Phone preview mirrors exactly what's shown in the display window.
        rgb=self.pg.image.tostring(surface,'RGB')
        im=Image.frombytes('RGB',surface.get_size(),rgb)
        data=io.BytesIO()
        im.save(data,'PNG',optimize=True)
        return data.getvalue()
