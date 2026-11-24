"""Convert all original transparent RGBA PNGs into 32x32 RGB565 frames.
The ILI9341 draws black for transparent pixels; binary layout matches companion.FRAMES.
"""
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
PETS=('bunny','cat','fox','frog','cookie','bee')
FRAMES=('idle_0','idle_1','blink','sit','wave_0','wave_1','hop_0','hop_1','sleep','happy','curious','dance_0','dance_1','gift')

def convert():
    source=ROOT/'desktop'/'assets'
    target=ROOT/'device'/'assets'
    target.mkdir(parents=True, exist_ok=True)
    for pet in PETS:
        out=bytearray()
        for frame in FRAMES:
            name=source/pet/(frame+'.png')
            im=Image.open(name).convert('RGBA')
            if im.size!=(32,32):raise ValueError(f'{name}: must be 32x32')
            for r,g,b,a in (im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata()):
                # composited on black, preserving anti-aliased edge colors
                r=(r*a+127)//255;g=(g*a+127)//255;b=(b*a+127)//255
                color=((r>>3)<<11)|((g>>2)<<5)|(b>>3)
                out.extend((color>>8,color&255))
        destination=target/(pet+'.bin')
        destination.write_bytes(out)
        print(pet, len(out), 'bytes')

if __name__=='__main__':convert()
