"""Create transparent, easy-to-replace 32x32 PNG placeholder art.
No images are overwritten unless --force is passed. Open individual images
in Aseprite, LibreSprite, GIMP or any PNG editor.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
PETS = ("bunny", "cat", "fox", "frog", "cookie", "bee")
STATES = ("idle_0", "idle_1", "blink", "wave_0", "wave_1", "hop_0", "hop_1",
          "sleep", "happy", "curious", "dance_0", "dance_1", "gift", "sit")
ICONS = ("heart", "flower", "star", "present", "letter")
P = {
    "bunny": {"line":"#74556c", "body":"#f4d5e9", "light":"#fff0f9", "shade":"#dca8c8", "accent":"#e991b7", "eye":"#493b55"},
    "cat":   {"line":"#65515c", "body":"#f4c89a", "light":"#ffead3", "shade":"#dcaa80", "accent":"#e78e94", "eye":"#423b47"},
    "fox":   {"line":"#704655", "body":"#ef9b6e", "light":"#fff0df", "shade":"#c9775f", "accent":"#ffc57c", "eye":"#433749"},
    "frog":  {"line":"#45695e", "body":"#a7d7a1", "light":"#ddf2c6", "shade":"#80bd91", "accent":"#f6b4a1", "eye":"#314a43"},
    "cookie":{"line":"#76513c", "body":"#d99c65", "light":"#efc58c", "shade":"#bb7e55", "accent":"#f4a6ab", "eye":"#513a43"},
    "bee":   {"line":"#5b4855", "body":"#f7d568", "light":"#fff2aa", "shade":"#eeb05b", "accent":"#f6a9b1", "eye":"#443545"},
}


def box(d, x, y, w, h, color):
    d.rectangle((x, y, x+w-1, y+h-1), fill=color)


def cookie_sprite(mode: str):
    """A round, smiling chocolate-chip cookie; every frame is editable PNG art."""
    c = P["cookie"]
    im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    energetic = mode in ("idle_1", "wave_1", "dance_1", "hop_0", "hop_1")
    jump = 3 if mode.startswith("hop") else 0
    bob = -1 if energetic else 0
    yy = lambda y: y + bob - jump
    # Foot shadows and teeny crumb-coloured arms.
    box(d, 10, yy(27), 5, 3, c["line"])
    box(d, 20, yy(27), 5, 3, c["line"])
    if mode.startswith(("wave", "dance")):
        box(d, 25, yy(10), 5, 4, c["line"])
        box(d, 26, yy(10), 3, 3, c["body"])
        if mode.startswith("dance"):
            box(d, 1, yy(11), 6, 3, c["line"])
    else:
        box(d, 2, yy(18), 7, 4, c["line"])
        box(d, 25, yy(19), 5, 4, c["line"])
    # Asymmetrical round cookie, chips, and a slightly golden rim.
    d.ellipse((4, yy(5), 28, yy(28)), fill=c["line"])
    d.ellipse((5, yy(6), 27, yy(27)), fill=c["body"])
    d.ellipse((7, yy(7), 25, yy(24)), fill=c["light"])
    for x,y,w,h in ((9,10,4,3),(19,9,4,4),(8,20,4,4),(23,20,3,3),(16,24,3,2)):
        box(d,x,yy(y),w,h,c["shade"])
        box(d,x+1,yy(y),max(w-2,1),max(h-1,1),"#79503f")
    # A cookie can still blink, smile, and be surprised.
    if mode in ("blink", "sleep", "sit", "happy"):
        box(d,11,yy(17),4,1,c["eye"])
        box(d,20,yy(17),4,1,c["eye"])
    elif mode=="curious":
        box(d,11,yy(15),3,4,c["eye"])
        box(d,21,yy(14),3,5,c["eye"])
    else:
        box(d,11,yy(15),3,4,c["eye"])
        box(d,21,yy(15),3,4,c["eye"])
        box(d,11,yy(15),1,1,"#ffffff")
        box(d,21,yy(15),1,1,"#ffffff")
    box(d,7,yy(20),3,2,c["accent"])
    box(d,25,yy(20),2,2,c["accent"])
    box(d,16,yy(21),3,1,c["eye"])
    if mode=="happy":
        box(d,16,yy(22),3,2,"#9b5663")
    elif mode=="sleep":
        box(d,26,yy(5),2,2,"#add0f3")
        box(d,29,yy(2),2,2,"#add0f3")
    elif mode=="gift":
        box(d,14,yy(23),10,7,"#ad669b")
        box(d,15,yy(24),8,5,"#efa8cb")
        box(d,18,yy(24),2,5,"#fbe39c")
    elif mode=="dance_1":
        box(d,1,yy(4),2,2,"#ffe1a1")
        box(d,29,yy(6),2,2,"#ffe1a1")
    return im


def bee_sprite(mode: str):
    """A winged, striped bee that flutters, rests, and waves."""
    c = P["bee"]
    im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    flutter = mode in ("idle_1", "wave_1", "hop_1", "dance_1")
    jump = 2 if mode.startswith("hop") else 0
    bob = -1 if flutter else 0
    yy = lambda y: y+bob-jump
    # Antennae and rounded winglets behind the body.
    box(d,12,yy(6),2,6,c["line"])
    box(d,21,yy(6),2,6,c["line"])
    box(d,11,yy(5),4,3,c["line"])
    box(d,20,yy(5),4,3,c["line"])
    wy=8 if flutter else 12
    d.ellipse((1, yy(wy), 12, yy(wy+11)),fill="#8a7894")
    d.ellipse((2, yy(wy+1), 11, yy(wy+10)),fill="#d9f2ff")
    d.ellipse((22, yy(wy), 31, yy(wy+11)),fill="#8a7894")
    d.ellipse((23, yy(wy+1), 30, yy(wy+10)),fill="#d9f2ff")
    # Small black feet, flight-ready.
    box(d,11,yy(27),3,4,c["line"])
    box(d,22,yy(27),3,4,c["line"])
    # Yellow bumblebee with three chocolate-brown stripes.
    d.ellipse((5, yy(11), 29, yy(29)),fill=c["line"])
    d.ellipse((6, yy(12), 28, yy(28)),fill=c["body"])
    box(d,10, yy(23), 17, 2, c["line"])
    box(d,13, yy(27), 12, 2, c["line"])
    box(d,9,yy(13),17,4,c["light"])
    if mode.startswith(("wave", "dance")):
        box(d,26,yy(10),5,3,c["line"])
        box(d,27,yy(11),3,2,c["body"])
    else:
        box(d,3,yy(23),5,3,c["line"])
    # Facial expressions.
    if mode in ("blink","happy","sleep","sit"):
        box(d,11,yy(19),4,1,c["eye"])
        box(d,21,yy(19),4,1,c["eye"])
    elif mode=="curious":
        box(d,11,yy(16),3,5,c["eye"])
        box(d,22,yy(15),3,5,c["eye"])
    else:
        box(d,11,yy(17),3,4,c["eye"])
        box(d,21,yy(17),3,4,c["eye"])
        box(d,11,yy(17),1,1,"#ffffff")
        box(d,21,yy(17),1,1,"#ffffff")
    box(d,7,yy(21),3,2,c["accent"])
    box(d,25,yy(21),3,2,c["accent"])
    box(d,16,yy(22),3,2,c["eye"])
    if mode=="happy":
        box(d,16,yy(23),3,2,"#a95b76")
    elif mode=="sleep":
        box(d,27,yy(6),2,2,"#b7c9f4")
        box(d,29,yy(3),3,1,"#b7c9f4")
    elif mode=="gift":
        box(d,13,yy(24),9,7,"#9068a8")
        box(d,14,yy(25),7,5,"#dfaddc")
        box(d,17,yy(24),2,6,"#ffdda0")
    elif mode=="dance_1":
        box(d,0,yy(5),2,2,"#fff2a0")
        box(d,29,yy(3),2,2,"#fff2a0")
    return im


def pet_sprite(pet: str, mode: str):
    if pet == "cookie":
        return cookie_sprite(mode)
    if pet == "bee":
        return bee_sprite(mode)
    c=P[pet]
    img=Image.new("RGBA", (32,32), (0,0,0,0))
    d=ImageDraw.Draw(img)
    bob=1 if mode in ("idle_1", "wave_1", "hop_1", "dance_1") else 0
    hop=3 if mode.startswith("hop") else 0
    yy=lambda y: y+bob-hop
    # Tail / silhouette behind body.
    if pet == "fox":
        d.polygon([(22,yy(24)),(30,yy(18)),(29,yy(27)),(23,yy(29))],fill=c["line"])
        d.polygon([(24,yy(24)),(29,yy(20)),(28,yy(26))],fill=c["light"])
    elif pet == "cat":
        box(d,25,yy(21),4,7,c["line"]); box(d,27,yy(18),3,5,c["body"])
    elif pet == "bunny":
        box(d,25,yy(25),5,5,c["light"])
    # Ears, behind head.
    if pet == "bunny":
        for x in (7,20):
            box(d,x,yy(1),6,16,c["line"])
            box(d,x+1,yy(2),4,14,c["body"])
            box(d,x+2,yy(4),2,10,c["accent"])
    elif pet in ("cat","fox"):
        ear_top=2 if pet=="fox" else 5
        d.polygon([(5,yy(16)),(7,yy(ear_top)),(15,yy(13))],fill=c["line"])
        d.polygon([(17,yy(13)),(25,yy(ear_top)),(27,yy(16))],fill=c["line"])
        d.polygon([(8,yy(13)),(9,yy(ear_top+5)),(14,yy(15))],fill=c["accent"])
        d.polygon([(19,yy(15)),(23,yy(ear_top+5)),(24,yy(13))],fill=c["accent"])
    else:
        for x in (7,21):
            box(d,x,yy(7),5,6,c["line"])
            box(d,x+1,yy(8),3,4,c["light"])
    # Body and feet.
    box(d,8,yy(20),18,10,c["line"])
    box(d,9,yy(21),16,8,c["body"])
    box(d,12,yy(24),9,4,c["light"])
    box(d,7,yy(28),8,3,c["line"])
    box(d,19,yy(28),8,3,c["line"])
    box(d,8,yy(28),6,2,c["body"])
    box(d,20,yy(28),6,2,c["body"])
    # Head.
    hy=12 if pet == "bunny" else 10 if pet == "frog" else 11
    box(d,4,yy(hy),25,16,c["line"])
    box(d,5,yy(hy+1),23,14,c["body"])
    box(d,8,yy(hy+2),17,6,c["light"])
    if pet == "fox":
        d.polygon([(9,yy(19)),(16,yy(26)),(24,yy(19))],fill=c["light"])
    elif pet == "frog":
        box(d,8,yy(13),17,6,c["body"])
    # Arms / paws.
    if mode.startswith("wave") or mode.startswith("dance"):
        box(d,25,yy(11),5,9,c["line"]);box(d,26,yy(12),3,7,c["body"])
        if mode.startswith("dance"):
            box(d,1,yy(13),6,5,c["line"]);box(d,2,yy(14),4,3,c["body"])
    else:
        box(d,5,yy(23),5,5,c["line"]);box(d,6,yy(24),3,3,c["body"])
        box(d,24,yy(23),5,5,c["line"]);box(d,25,yy(24),3,3,c["body"])
    # Face.
    sleepy=mode in ("sleep","blink","happy","sit")
    if sleepy:
        box(d,10,yy(19),5,1,c["eye"])
        box(d,20,yy(19),5,1,c["eye"])
    elif mode == "curious":
        box(d,11,yy(17),3,5,c["eye"])
        box(d,21,yy(16),3,5,c["eye"])
        box(d,22,yy(16),1,1,"#ffffff")
    else:
        box(d,11,yy(17),3,4,c["eye"])
        box(d,21,yy(17),3,4,c["eye"])
        box(d,11,yy(17),1,1,"#ffffff")
        box(d,21,yy(17),1,1,"#ffffff")
    box(d,6,yy(22),4,2,c["accent"])
    box(d,25,yy(22),3,2,c["accent"])
    if pet == "cat":
        box(d,16,yy(21),3,2,c["accent"])
        for x in (1,25):
            box(d,x,yy(23),5,1,c["line"])
    elif pet == "frog":
        box(d,14,yy(23),7,1,c["eye"])
    else:
        box(d,16,yy(22),3,2,c["accent"] if pet=="bunny" else c["eye"])
    # Small props or facial extras.
    if mode=="sleep":
        box(d,27,yy(4),2,2,"#b6d0fc");box(d,29,yy(1),3,1,"#b6d0fc")
    elif mode=="gift":
        box(d,13,yy(24),9,7,"#a26a9b")
        box(d,14,yy(25),7,5,"#f3a9d4")
        box(d,17,yy(24),2,6,"#fbe2a1")
    elif mode=="happy":
        box(d,16,yy(24),3,2,c["accent"])
    elif mode=="dance_1":
        box(d,0,yy(8),2,2,"#f8e49d")
        box(d,30,yy(7),2,2,"#f8e49d")
    return img


def icon_sprite(kind):
    im=Image.new("RGBA",(32,32),(0,0,0,0)); d=ImageDraw.Draw(im)
    if kind=="heart":
        d.polygon([(16,27),(4,15),(4,10),(8,7),(13,7),(16,11),(19,7),(24,7),(28,11),(28,16)],fill="#f389ac")
        box(d,8,10,4,2,"#ffd5e4")
    elif kind=="flower":
        box(d,15,17,3,13,"#82c89d")
        for x,y in ((12,5),(19,5),(6,12),(24,12),(12,19),(19,19)):
            box(d,x,y,6,6,"#e89fc4")
        box(d,14,12,6,7,"#fbe2a2")
    elif kind=="star":
        d.polygon([(16,3),(20,11),(29,12),(23,19),(25,28),(16,24),(7,28),(9,19),(3,12),(12,11)],fill="#ffe094")
        box(d,13,9,2,4,"#fff2cb")
    elif kind=="present":
        box(d,6,12,21,17,"#6f4c79")
        box(d,7,13,19,15,"#ebb2cf")
        box(d,15,12,4,16,"#ffe49d")
        box(d,7,18,19,3,"#ffe49d")
        box(d,10,7,6,5,"#f18faf")
        box(d,18,7,6,5,"#f18faf")
    else:
        box(d,4,8,24,18,"#86677c")
        box(d,5,9,22,16,"#fff1e7")
        d.line([(6,10),(16,19),(26,10)],fill="#ed9fba",width=2)
    return im


def generate(force=False):
    for pet in PETS:
        target=ASSETS / pet
        target.mkdir(parents=True, exist_ok=True)
        for state in STATES:
            file=target / (state+".png")
            if force or not file.exists():
                pet_sprite(pet,state).save(file)
    (ASSETS/"icons").mkdir(parents=True,exist_ok=True)
    for name in ICONS:
        file=ASSETS/"icons"/(name+".png")
        if force or not file.exists():icon_sprite(name).save(file)


def create_preview(path=None):
    generate()
    cols=("idle_0","blink","wave_0","hop_0","sleep","dance_0","happy","gift")
    w,h=8*118+25,len(PETS)*134+60
    im=Image.new('RGB',(w,h),'#18141f');d=ImageDraw.Draw(im)
    font=ImageFont.load_default()
    for i,pet in enumerate(PETS):
        d.text((10,35+134*i),pet.upper(),fill='#f6d3e9',font=font)
        for j,state in enumerate(cols):
            x,y=68+j*113,25+i*134
            d.rounded_rectangle((x,y,x+99,y+104),radius=12,fill='#292333',outline='#504356')
            spr=Image.open(ASSETS/pet/(state+'.png')).convert('RGBA').resize((80,80),Image.Resampling.NEAREST)
            im.paste(spr,(x+10,y+5),spr)
            d.text((x+8,y+88),state.replace('_0',''),font=font,fill='#d8bacf')
    p=Path(path) if path else ROOT/'sprite_preview.png'
    im.save(p)
    return p


if __name__ == '__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--force',action='store_true',help='Overwrite edited PNGs (usually do NOT use)')
    ns=ap.parse_args()
    generate(force=ns.force)
    print('Generated',len(PETS)*len(STATES)+len(ICONS),'PNG sprites')
    print('Preview:',create_preview())
