"""Run with: python -m unittest discover -s tests -v"""
from __future__ import annotations
import json
import queue
import random
import tempfile
import threading
import unittest
from pathlib import Path
from urllib import request, error

from PIL import Image
from bunnygram.assets import ASSETS, ICONS, PETS as ART_PETS, STATES, create_preview, generate
from bunnygram.model import Companion, PETS, default_state
from bunnygram.server import PhoneServer


class FakeTime:
    def __init__(self): self.t = 1000.0
    def mono(self): return self.t
    def wall(self): return self.t + 1000000.0
    def advance(self, seconds): self.t += seconds


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.time = FakeTime()
        self.path = Path(self.temp.name) / "state.json"
        self.pet = Companion(self.path, rng=random.Random(8), monotonic=self.time.mono, wall_clock=self.time.wall)

    def test_all_six_pets_and_no_care_meters(self):
        self.assertEqual(set(PETS), {"bunny", "cat", "fox", "frog", "cookie", "bee"})
        self.assertEqual(set(PETS), set(ART_PETS))
        for item in PETS:
            self.pet.apply("switch_pet", {"pet": item})
            status = self.pet.snapshot()
            self.assertEqual(item, status["pet"])
            self.assertNotIn("hunger", status)
            self.assertNotIn("happiness", status)
            self.assertNotIn("health", status)

    def test_switching_and_naming_survive_reboot(self):
        self.pet.apply("switch_pet", {"pet": "cookie"})
        self.pet.apply("rename", {"name": "Cookie Monster"})
        self.pet.apply("switch_pet", {"pet": "bee"})
        self.pet.apply("rename", {"name": "Buzz"})
        self.pet.apply("setting", {"setting": "mirror_horizontal", "value": True})
        self.pet.save()
        again = Companion(self.path, monotonic=self.time.mono, wall_clock=self.time.wall)
        self.assertEqual(again.snapshot()["pet"], "bee")
        self.assertEqual(again.snapshot()["pets"]["cookie"]["name"], "Cookie Monster")
        self.assertEqual(again.snapshot()["pet_name"], "Buzz")
        self.assertTrue(again.snapshot()["settings"]["mirror_horizontal"])

    def test_old_four_pet_saves_can_load(self):
        before = default_state()
        before["pet"] = "cat"
        before["names"].pop("cookie")
        before["names"].pop("bee")
        self.path.write_text(json.dumps(before), encoding="utf-8")
        new = Companion(self.path, monotonic=self.time.mono, wall_clock=self.time.wall)
        self.assertEqual(new.snapshot()["pet"], "cat")
        self.assertEqual(new.snapshot()["pets"]["bee"]["name"], "Bumble")

    def test_animating_autonomously_and_night_mode(self):
        self.pet.apply("setting", {"setting": "quiet_hours", "value": True})
        self.time.advance(50)
        self.pet.tick(hour=1)
        self.assertEqual(self.pet.snapshot()["activity"], "sleep")
        self.time.advance(70)
        self.pet.tick(hour=12)
        self.assertIn(self.pet.snapshot()["activity"],
                      ("idle", "blink", "curious", "sit", "hop", "wave", "dance", "sleep"))

    def test_phone_actions_and_reactions(self):
        self.pet.apply("switch_pet", {"pet": "bee"})
        self.pet.apply("react", {"reaction": "dance"})
        self.assertEqual(self.pet.snapshot()["activity"], "dance")
        self.time.advance(10)
        self.pet.tick()
        self.assertNotEqual(self.pet.snapshot()["activity"], "dance")
        for bad in ("broken", "elephant", ""):  # No phantom pet types.
            with self.assertRaises(ValueError):
                self.pet.apply("switch_pet", {"pet": bad})

    def test_mail_is_saved_and_opened_by_phone(self):
        self.pet.apply("send_mail", {"kind": "gift", "gift": "flower", "text": "You make me smile", "from": "Me"})
        item = self.pet.snapshot()["mail"][0]
        self.assertEqual(self.pet.snapshot()["unread"], 1)
        self.assertFalse(item["opened"])
        self.pet.apply("open_mail", {"id": item["id"]})
        self.assertEqual(self.pet.snapshot()["unread"], 0)
        self.pet.save()
        self.assertEqual(Companion(self.path).snapshot()["mail"][0]["text"], "You make me smile")
        with self.assertRaises(ValueError):
            self.pet.apply("clear_mail", {})

    def test_input_validation(self):
        invalid = [
            ("rename", {"name": " "}),
            ("rename", {"name": "x"*25}),
            ("react", {"reaction": "fire"}),
            ("send_mail", {"text": " "}),
            ("send_mail", {"text": "x"*601}),
            ("send_mail", {"text": "Hi", "gift": "dynamite"}),
            ("setting", {"setting": "brightness", "value": 101}),
            ("setting", {"setting": "display_on", "value": 1}),
        ]
        for action, values in invalid:
            with self.subTest(action=action, values=values):
                with self.assertRaises(ValueError): self.pet.apply(action, values)


class AssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): generate(force=False)

    def test_all_frames_are_transparent_32x32_pngs(self):
        for pet in ART_PETS:
            for state in STATES:
                p = ASSETS / pet / (state + ".png")
                self.assertTrue(p.is_file(), str(p))
                with Image.open(p) as im:
                    self.assertEqual(im.size, (32, 32))
                    self.assertEqual(im.mode, "RGBA")
                    self.assertEqual(im.getpixel((0, 31))[3], 0)
                    self.assertTrue(im.getbbox())
        for kind in ICONS:
            self.assertTrue((ASSETS / "icons" / (kind + ".png")).is_file())

    def test_cookie_and_bee_are_visually_distinct(self):
        cookie = (ASSETS / "cookie" / "idle_0.png").read_bytes()
        bee = (ASSETS / "bee" / "idle_0.png").read_bytes()
        bunny = (ASSETS / "bunny" / "idle_0.png").read_bytes()
        self.assertNotEqual(cookie, bee)
        self.assertNotEqual(bee, bunny)
        self.assertNotEqual(cookie, bunny)
        self.assertNotEqual((ASSETS / "cookie" / "idle_0.png").read_bytes(),
                            (ASSETS / "cookie" / "sleep.png").read_bytes())


class LocalHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.model = Companion(Path(self.temp.name) / "state.json")
        self.commands = queue.Queue()
        self.preview = {"lock": threading.Lock(), "png": b"testfakepng"}
        self.server = PhoneServer(self.model, self.commands, self.preview,
                                  port=0, bind="127.0.0.1",
                                  security_file=Path(self.temp.name) / "paired.json")
        self.server.start()
        self.addCleanup(self.server.stop)
        self.url = "http://127.0.0.1:" + str(self.server.port)
        self.stopping = threading.Event()
        def worker():
            while not self.stopping.is_set():
                try: action, data, reply = self.commands.get(timeout=.1)
                except queue.Empty: continue
                try: self.model.apply(action, data); reply.put({"ok": True})
                except ValueError as e: reply.put({"ok": False, "error": str(e)})
        self.thread = threading.Thread(target=worker, daemon=True)
        self.thread.start()
        self.addCleanup(self.stopping.set)

    def fetch(self, path, payload=None, token=None):
        headers = {}
        if payload is not None: headers["Content-Type"] = "application/json"
        if token: headers["X-Bunnygram-Token"] = token
        req = request.Request(self.url + path, data=json.dumps(payload).encode() if payload is not None else None,
                              headers=headers)
        try:
            with request.urlopen(req, timeout=3) as response:
                return response.status, json.loads(response.read())
        except error.HTTPError as ex:
            return ex.code, json.loads(ex.read())

    def test_auth_and_phone_pet_switching(self):
        code, val = self.fetch("/api/health")
        self.assertEqual(code, 200)
        code, val = self.fetch("/api/status")
        self.assertEqual(code, 401)
        code, val = self.fetch("/api/pair", {"code": "wrong"})
        self.assertEqual(code, 403)
        code, val = self.fetch("/api/pair", {"code": self.server.pairing.code})
        self.assertEqual(code, 200)
        token = val["token"]
        code, val = self.fetch("/api/action", {"action": "switch_pet", "pet": "cookie"}, token)
        self.assertEqual(code, 200, str(val))
        code, val = self.fetch("/api/status", token=token)
        self.assertEqual(code, 200)
        self.assertEqual(val["pet"], "cookie")
        code, val = self.fetch("/api/action", {"action": "switch_pet", "pet": "bee"}, token)
        self.assertEqual(code, 200)
        code, val = self.fetch("/api/status", token=token)
        self.assertEqual(val["pet"], "bee")
        self.assertEqual(len(val["pets"]), 6)

    def test_invalid_action_and_mail_validation(self):
        _, data = self.fetch("/api/pair", {"code": self.server.pairing.code})
        token = data["token"]
        code, data = self.fetch("/api/action", {"action": "switch_pet", "pet": "dragon"}, token)
        self.assertEqual(code, 400)
        code, data = self.fetch("/api/action", {"action": "send_mail", "text": "A tiny letter", "from": "Me"}, token)
        self.assertEqual(code, 200)
        code, state = self.fetch("/api/status", token=token)
        self.assertEqual(state["unread"], 1)
        self.assertEqual(state["mail"][0]["text"], "A tiny letter")


if __name__ == "__main__": unittest.main()
