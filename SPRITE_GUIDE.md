# Sprite art checklist

All sprites are **32 × 32 transparent PNGs**; draw art in a 24–30px region in the center, leaving a margin. Do not use antialiasing or blurry scaling. The pet uses all files below and provides placeholder artwork for every one. Press **R** in the simulator to reload edits.

## Core bunny (required)

| File | Meaning | Animation |
| --- | --- | --- |
| `bunny_idle_0.png` | Sitting / idle, eyes open | Idle alternating every ~0.6 sec |
| `bunny_idle_1.png` | Sitting / idle, slightly moved | Idle alternating |
| `bunny_blink.png` | Closed eyes | Brief random blink |
| `bunny_happy.png` | Happy / being petted | ~1.5 sec after petting |
| `bunny_eat_0.png` | Holding food | Eating alternates frames |
| `bunny_eat_1.png` | Chewing | Eating alternates frames |
| `bunny_sleep.png` | Sleeping | While sleep mode is on |
| `bunny_sad.png` | Hungry or unhappy | Automatic when hunger/happiness is low |
| `bunny_excited.png` | Mail arrived / gift opened | ~2 sec reaction |

## Extra sprites

| File | Used for |
| --- | --- |
| `icon_heart.png` | Floating love-hearts above the pet |
| `icon_letter.png` | New mail indicator |
| `icon_flower.png` | Flower gift |
| `icon_cake.png` | Cake gift |
| `icon_gift.png` | Unknown / generic gift |

A 32×32 bunny drawn in the top left of the sprite sheet does not have to fill the canvas. Use RGBA transparency to layer sprites. For Pepper's Ghost, pure black is the unlit background and transparent sprite pixels are composited onto that black background.

**Orientation note:** A single 45° reflector changes the apparent image orientation. If you mount your screen at a different angle, you may need to horizontally flip the final rendered display. This is configurable when porting to the hardware; test with asymmetric text and a left/right-marked sprite first.
