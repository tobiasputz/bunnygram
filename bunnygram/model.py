"""Pure-Python, hardware-independent model for an ambient floating companion.
There are deliberately NO hunger, death, mood, or care meters.
"""
from __future__ import annotations
import copy
import json
import random
import threading
import time
from pathlib import Path

PETS = {
    "bunny": {"name": "Mochi", "personality": "Gentle & dreamy", "accent": "#f6a6c6"},
    "cat": {"name": "Miso", "personality": "Curious & cuddly", "accent": "#e5b58b"},
    "fox": {"name": "Pip", "personality": "Playful & adventurous", "accent": "#ffae76"},
    "frog": {"name": "Puddle", "personality": "Sleepy & thoughtful", "accent": "#9edc9a"},
    "cookie": {"name": "Chip", "personality": "Sweet, crumbly & mischievous", "accent": "#dcaa77"},
    "bee": {"name": "Bumble", "personality": "Buzzy, cheerful & curious", "accent": "#f2cc65"},
}
GIFTS = ("heart", "flower", "star", "present")
AMBIENT = ("idle", "blink", "curious", "sit", "hop", "wave", "dance", "sleep")
DURATIONS = {"heart":4.0, "flower":4.0, "star":4.0, "present":5.0,
             "wave":3.6, "hop":3.0, "dance":5.0, "happy":3.5,
             "curious":5.0, "sleep":9.0, "sit":7.0, "blink":0.4, "idle":5.0}
MAX_MAIL = 200


def default_state():
    return {
        "version": 3,
        "pet": "bunny",
        "names": {pet: info["name"] for pet, info in PETS.items()},
        "settings": {
            "brightness": 100,
            "mirror_horizontal": False,
            "rotate_180": False,
            "quiet_hours": False,
            "display_on": True,
            "fullscreen": False,
            "show_preview_border": False,
        },
        "mail": [],
        "total_interactions": 0,
        "created_at": time.time(),
    }


class Companion:
    """Write operations run in display thread; HTTP readers use snapshot()."""
    def __init__(self, filename, rng=None, monotonic=None, wall_clock=None):
        self.filename = Path(filename)
        self.rng = rng or random.Random()
        self.mono = monotonic or time.monotonic
        self.wall = wall_clock or time.time
        self.lock = threading.RLock()
        self.state = default_state()
        self.load()
        self.activity = "idle"
        self.activity_until = self.mono() + 4
        self.reaction = None
        self.reaction_until = 0.0
        self.notice = ""
        self.notice_until = 0.0
        self.revision = 0

    def load(self):
        try:
            raw = json.loads(self.filename.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return
            with self.lock:
                if raw.get("pet") in PETS:
                    self.state["pet"] = raw["pet"]
                if isinstance(raw.get("names"), dict):
                    for key, value in raw["names"].items():
                        if key in PETS and isinstance(value, str) and value.strip():
                            self.state["names"][key] = value.strip()[:24]
                if isinstance(raw.get("settings"), dict):
                    for key, default in self.state["settings"].items():
                        value = raw["settings"].get(key)
                        if isinstance(default, bool) and isinstance(value, bool):
                            self.state["settings"][key] = value
                        elif key == "brightness" and type(value) in (int, float):
                            self.state["settings"][key] = int(max(10, min(100, value)))
                if isinstance(raw.get("mail"), list):
                    self.state["mail"] = [x for x in raw["mail"][-MAX_MAIL:]
                                           if isinstance(x, dict) and isinstance(x.get("id"), str)]
                if isinstance(raw.get("total_interactions"), int):
                    self.state["total_interactions"] = max(0, raw["total_interactions"])
                if type(raw.get("created_at")) in (float, int):
                    self.state["created_at"] = raw["created_at"]
        except (OSError, ValueError, TypeError):
            pass

    def save(self):
        with self.lock:
            snapshot = copy.deepcopy(self.state)
        self.filename.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.filename.with_suffix(".tmp")
        tmp.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.filename)

    def _notice(self, label):
        self.notice = label
        self.notice_until = self.mono() + 3.5

    def _react(self, key):
        self.reaction = key
        self.reaction_until = self.mono() + DURATIONS.get(key, 3)
        self._notice({"heart":"A little love!", "flower":"A flower for you!",
                      "star":"A tiny wish!", "present":"Surprise!", "wave":"Hello!",
                      "happy":"Yay!", "dance":"Dance time!", "hop":"Boing!"}.get(key, ""))

    def tick(self, hour=None):
        now = self.mono()
        with self.lock:
            if self.reaction and now >= self.reaction_until:
                self.reaction = None
            if now >= self.activity_until:
                quiet = self.state["settings"]["quiet_hours"]
                night = (hour if hour is not None else time.localtime(self.wall()).tm_hour)
                if quiet and (night >= 23 or night < 7):
                    self.activity = "sleep"
                    seconds = self.rng.uniform(25, 55)
                else:
                    choices = ("idle", "idle", "idle", "curious", "sit", "sit", "hop", "wave", "dance", "sleep", "blink")
                    # Different companions have slightly different tendencies.
                    extra = {"bunny":("sit", "hop"), "cat":("sleep", "curious"),
                             "fox":("hop", "dance"), "frog":("sit", "sleep"),
                             "cookie":("sit", "dance"), "bee":("hop", "wave")}
                    self.activity = self.rng.choice(choices + extra[self.state["pet"]])
                    seconds = (self.rng.uniform(12, 25) if self.activity == "sleep"
                               else self.rng.uniform(5, 13))
                    if self.activity == "blink":
                        seconds = 0.25
                self.activity_until = now + seconds

    def apply(self, action, args=None):
        args = args or {}
        with self.lock:
            if action == "switch_pet":
                pet = args.get("pet")
                if pet not in PETS:
                    raise ValueError("Unknown pet")
                self.state["pet"] = pet
                self.activity = "idle"
                self.activity_until = self.mono() + 5
                self._react("wave")
            elif action == "rename":
                name = str(args.get("name", "")).strip()
                if not 1 <= len(name) <= 24:
                    raise ValueError("Name must contain 1–24 characters")
                self.state["names"][self.state["pet"]] = name
            elif action == "react":
                reaction = args.get("reaction")
                if reaction not in ("heart", "flower", "star", "present", "wave", "hop", "dance", "happy", "sleep", "curious"):
                    raise ValueError("Unknown reaction")
                self._react(reaction)
            elif action == "setting":
                setting = args.get("setting")
                if setting not in self.state["settings"]:
                    raise ValueError("Unknown setting")
                old = self.state["settings"][setting]
                if setting == "brightness":
                    try:
                        amount = int(args["value"])
                    except (ValueError, TypeError, KeyError):
                        raise ValueError("Brightness must be between 10 and 100") from None
                    if not 10 <= amount <= 100:
                        raise ValueError("Brightness must be between 10 and 100")
                    self.state["settings"][setting] = amount
                else:
                    if not isinstance(args.get("value"), bool):
                        raise ValueError("Toggle setting must be true or false")
                    self.state["settings"][setting] = args["value"]
            elif action == "send_mail":
                text = str(args.get("text", "")).strip()
                sender = str(args.get("from", "You")).strip() or "You"
                kind = args.get("kind", "letter")
                gift = args.get("gift", "heart")
                if not text or len(text) > 600:
                    raise ValueError("Letter text must contain 1–600 characters")
                if len(sender) > 40:
                    raise ValueError("Sender must contain at most 40 characters")
                if kind not in ("letter", "gift") or gift not in GIFTS:
                    raise ValueError("Invalid letter or gift")
                import uuid
                entry = {"id": uuid.uuid4().hex, "from": sender, "text": text,
                         "kind": kind, "gift": gift, "received_at": self.wall(), "opened": False}
                self.state["mail"].append(entry)
                self.state["mail"] = self.state["mail"][-MAX_MAIL:]
                self._react("present" if kind == "gift" else "happy")
                self._notice("New letter!" if kind == "letter" else "A present arrived!")
            elif action == "open_mail":
                mid = args.get("id")
                item = next((x for x in self.state["mail"] if x["id"] == mid), None)
                if item is None:
                    raise ValueError("Letter not found")
                item["opened"] = True
                self._react("heart" if item["kind"] == "letter" else item["gift"])
            elif action == "clear_mail":
                raise ValueError("Removing letters is intentionally disabled")
            else:
                raise ValueError("Unknown action")
            self.state["total_interactions"] += 1
            self.revision += 1

    def snapshot(self):
        with self.lock:
            pet = self.state["pet"]
            mail = copy.deepcopy(self.state["mail"])
            return {
                "pet": pet, "pet_name": self.state["names"][pet],
                "pets": {k: {**v, "name": self.state["names"][k]} for k, v in PETS.items()},
                "settings": copy.deepcopy(self.state["settings"]),
                "activity": self.reaction if self.reaction is not None else self.activity,
                "mail": list(reversed(mail)),
                "unread": sum(not x.get("opened", False) for x in mail),
                "notice": self.notice if self.mono() < self.notice_until else "",
                "total_interactions": self.state["total_interactions"],
                "revision": self.revision,
            }
