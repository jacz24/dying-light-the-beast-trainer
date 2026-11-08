"""The ESP app: a transparent, click-through overlay on the game, plus a control panel that ties the tools together.

Run: python overlay.py [--tk]   (elevated terminal, a save loaded, the game in windowed mode). The panel opens at once;
the overlay starts after the first scan (about 12 s).
The overlay is a raylib (OpenGL) window: per-pixel alpha, vsync, drawn by the GPU (paint.py). --tk: the old tkinter
canvas, slower (47 to 72 redraws a second with many boxes, see overlaybench.py). One loop on the main thread drives
both windows: the overlay frame (raylib waits for vsync), then root.update() for the panel.
Overlay, only while the game is the active window: a box, health bar, distance and head dot per AI (magenta = zombie,
orange = Volatile, blue = human, green = friendly NPC, gray = unknown type), and a labeled circle per loot object (loot already searched or
taken is hidden).
The switches and the loot distance are saved in overlay_settings.json at each change and come back at the next start
(except "Armed": the nuke always starts disarmed).
Panel: a switch per layer and per loot type, the loot distance, instant search, the player's health, god mode, the
player-variable cheats (ammo, stamina, immortality, no fall damage), no durability loss, no reload, one-hit melee,
the jump and speed sliders, the time of day (game clock, hold day or night, Day and Night buttons), the nuke, the aim
readout and smart aim.
Keys: F6 shows or hides the overlay, F7 fires the nuke when it is armed, hold F1 for half a second to end,
F9 marks where you stand, F10 teleports to the mark (teleport.py), hold F11 to track the nearest head (aim.py).
Read-only, except the cheats, the nuke, F10, F11 and the clock: they write game memory only while their switch or
slider is on (F10, F11, the buttons: at each press). At the end (F1, Quit, an error) the player variables go back to
the game's values (restore()).
One background scan finds everything (player, AI, cameras, loot, player health module): at the start, after a death
or a sleep, and after each 50 m walked (loot streams in and out). After the first, a scan reads only the reservations
that held objects plus new regions (1 to 2.5 s); every 10th is full. The panel and the overlay keep running meanwhile.
A new corpse is found within a second, through its dead HumanAI (BODY_LINK), not at the next scan.
Session 8: version safety (selfcheck.py); a teleport over 200 m asks for a full scan 10 s and a rescan 30 s later.
Session 9: the teleports moved to movement.py (a mixin, like cheats.py); F2 flying, F3 NoClip (movement.py; --dry-fly:
no writes).
"""
import ctypes
import ctypes.wintypes as wt
import json
import math
import os
import struct
import sys
import threading
import time
import tkinter as tk
from collections import defaultdict

ctypes.windll.shcore.SetProcessDpiAwareness(2)  # physical pixels, the same as the game

import mem
from aikind import NPC, is_zombie, kind
from aim import LOOK_VT, aim_error, angles, living_head, nearest, turn, view
from camera import CAM_WORLD, CAMERA_VT, active_camera, game_window, view_proj, w2s
from cheats import CHEAT_TEXT, FURY_VT, ONEHIT, SLIDER_START, SLIDERS, Cheats
from daynight import DAYNIGHT_VT, TIME, hhmm, set_time
from findptr import modules, scan
from godmode import PLAYER_HEALTH_VT, heal, player_health
from head import head_pos
from items import FIREARM_VT, INVENTORY_VT, ITEM_VT, MELEE_VT, held_gun, melee_durability
from loot import LOOT, loot_pos, loot_vtables, model_pos, spawned
from lootstate import SEARCH_TIME, emptied, looted, no_item
from movement import FLY_OFF, Movement
from nuke import RADIUS, fire, targets
from paint import RlPaint, TkPaint
from radar import (AI_POS, HEALTH_VT, HUMAN_VT, PLAYER_VT, alive, health, health_element, health_module, heap_of,
                   humans_in, in_world, player_pos, read)
from rtti import parse_addr
from selfcheck import SelfCheck, resolve
from teleport import BPC_VT
from track import flat, sane
from watch import EXE, key_down
from waypoint import LEVEL_VT, WAYPOINT_VT, waypoint

HEIGHT = 1.75      # m from the AI position (the feet) to the top of the box
MAX_DIST = 100     # m, AI boxes
RESCAN = 50        # m walked since the last scan before a new one (loot objects stream in and out)
FULL_EVERY = 10    # every 10th scan reads all memory: a rescan missed 0 to 123 items (not loot) in session 7, and a
                   # melee weapon picked up there would stay without durability protection until a full scan
HAS_STATE = ("search", "pickup")  # Container and ComplexContainer have the looted state (lootstate.py); the others do not
FAST = ("search", "body")  # loot with a search time at +0x1f8 (a fresh corpse: kind 1, 1.0 s, session 5)
BODY_LINK = 0x2558  # HumanAI -> its BodyContainer once dead (session 5: 3 of 3 dead AI, no living one; it points back)
KIND_COLOR = {True: "#ff00ff", False: "#40c0ff", None: "#a0a0a0"}  # is_zombie(): zombie, human, unknown type
TYPE_COLOR = {"Volatile": "#ff8000", NPC: "#30d030"}  # type name prefix -> its own color, before KIND_COLOR
SWITCHES = {"overlay": True, "boxes": True, "bars": True, "heads": True,
            "search": True, "pickup": True, "body": True, "collectable": True, "fast": False, "god": False, "armed": False,
            "ammo": False, "stamina": False, "durability": False, "reload": False, "smart": False, "immortal": False,
            "fall": False, "onehit": False, "fury": False}
HOLD = {"day": 0.5, "night": 0.0}  # always day / always night: the game clock held at 12:00 or 00:00
HERE = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))  # the exe's folder
SETTINGS = os.path.join(HERE, "overlay_settings.json")  # (a one-file exe runs from a temporary folder)
NOT_SAVED = ("armed",)  # the nuke starts disarmed after each start, so a stray F7 cannot fire it
BG, FG, BUTTON = "#1e1e1e", "#e0e0e0", "#3a3a3a"
VK_F6, VK_F7, VK_F11, VK_LBUTTON = 0x75, 0x76, 0x7a, 0x01
u = ctypes.windll.user32

assert {label for label, color in LOOT.values()} <= SWITCHES.keys(), "each loot label needs a panel switch"


def load_settings(path=SETTINGS):
    """The saved switches and loot distance, or {} (no file yet, or a broken one: then the defaults apply)."""
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def client_rect(hwnd):
    """(x, y, width, height) of the game's client area on the screen."""
    pt, r = wt.POINT(0, 0), wt.RECT()
    u.ClientToScreen(hwnd, ctypes.byref(pt))
    u.GetClientRect(hwnd, ctypes.byref(r))
    return pt.x, pt.y, r.right, r.bottom


class App(Cheats, Movement, SelfCheck):
    def __init__(self, p, use_tk=False):
        self.p, self.pw, self.mods = p, None, modules(p)  # pw: the write handle, opened at the first write
        resolve(p, self.mods)  # version safety (session 8): vtables by class name, player variables by name
        self.game = game_window(p.pid)[0]
        self.pvt, self.hvt, self.cvt, self.hmvt, self.phvt = (parse_addr(self.mods, t) for t in (
            PLAYER_VT, HUMAN_VT, CAMERA_VT, HEALTH_VT, PLAYER_HEALTH_VT))
        self.lvt = loot_vtables(self.mods)
        self.body_vt = next(v for v, (label, color) in self.lvt.items() if label == "body")
        self.char_vt, self.mark = parse_addr(self.mods, BPC_VT), None
        self.item_vt, self.melee_vt, self.melee, self.dura = parse_addr(self.mods, ITEM_VT), parse_addr(self.mods, MELEE_VT), [], {}
        self.inv_vt, self.fire_vt, self.loaded = parse_addr(self.mods, INVENTORY_VT), parse_addr(self.mods, FIREARM_VT), {}
        self.look_vt, self.look, self.lock, self.errs = parse_addr(self.mods, LOOK_VT), None, None, []
        self.dn_vt, self.dnc = parse_addr(self.mods, DAYNIGHT_VT), None
        self.level_vt, self.way_vt, self.level = parse_addr(self.mods, LEVEL_VT), parse_addr(self.mods, WAYPOINT_VT), None
        self.fvt, self.furym = parse_addr(self.mods, FURY_VT), None
        self.player, self.heap, self.humans, self.cams, self.loot_objs, self.phm = None, None, [], {}, [], None
        self.job, self.scan_at, self.cam, self.rect, self.next_slow = None, None, None, None, 0
        self.hms, self.kinds, self.loot, self.keys_was, self.running = {}, {}, [], {}, True
        self.cheat_was, self.checks = {}, {}  # checks: the self-check per feature (selfcheck.py, session 8)
        self.memo, self.scans, self.jump_scans = {}, 0, []  # findptr.scan() memo (session 7); long_jump()
        self.near, self.hp_was = [], {}  # one-hit melee: enemies within 3 x ONEHIT m, and their health at the last frame
        self.root, self.rect = tk.Tk(), client_rect(self.game)
        if use_tk:
            self.paint = TkPaint(self.root, self.rect)
        else:
            self.root.withdraw()  # the root only owns the panel; the overlay is the raylib window
            self.paint = RlPaint(self.rect)
        self.build_panel()
        self.root.update()
        u.SetForegroundWindow(self.game)
        print("panel open. Scanning memory (about 12 s). Hold F1 to end.", flush=True)
        try:
            while self.running:
                self.paint.begin()  # an empty overlay: nothing stays while the game is not active or the scan runs
                self.tick()
                self.paint.end()  # raylib: waits for vsync
                self.root.update()  # the panel, and the redraw of the tk overlay
                if use_tk:  # 15 ms gave 64 redraws a second and a visible lag; one redraw's reads take 0.6 ms
                    time.sleep(0.005)
        finally:
            self.restore()
            self.root.destroy()

    def build_panel(self):
        top = tk.Toplevel(self.root, bg=BG)
        top.title("Aimbot study")
        top.attributes("-topmost", True)
        top.geometry("+8+60")  # the free strip left of the game window (its client area starts at x = 347)
        top.protocol("WM_DELETE_WINDOW", self.stop)
        saved = load_settings()
        self.v = {k: tk.BooleanVar(value=on if k in NOT_SAVED else bool(saved.get(k, on))) for k, on in SWITCHES.items()}
        self.text = {k: tk.StringVar(value="") for k in ("status", "check", "health", "nuke", "aim", "tele", "way", "clock")}
        self.text["fly"] = tk.StringVar(value=FLY_OFF)
        dist = saved.get("loot_dist")
        self.loot_dist = tk.IntVar(value=min(100, max(10, dist)) if isinstance(dist, int) else 30)
        self.factor = {k: tk.DoubleVar(value=f if isinstance(f := saved.get(k), (int, float)) and 1 <= f <= 4
                                       else SLIDER_START) for k in SLIDERS}
        self.hold = tk.StringVar(value=h if (h := saved.get("clock_hold")) in HOLD else "off")
        base = saved.get("base")  # the slider variables' values before the first write; kept here if the app was killed
        self.base = {k: float(v) for k, v in base.items() if isinstance(v, (int, float))} if isinstance(base, dict) else {}
        for var in (*self.v.values(), self.loot_dist, *self.factor.values(), self.hold):
            var.trace_add("write", lambda *_: self.save_settings())
        style = dict(bg=BG, fg=FG, activebackground=BG, activeforeground=FG)

        def add(w, pady=0):
            w.pack(fill="x", padx=10, pady=pady)

        def title(text):
            add(tk.Label(top, text=text, font=("Segoe UI", 10, "bold"), anchor="w", **style), pady=(8, 0))

        def check(key, text, fg=FG):
            add(tk.Checkbutton(top, text=text, variable=self.v[key], anchor="w", selectcolor=BUTTON, **{**style, "fg": fg}))

        def line(key):
            add(tk.Label(top, textvariable=self.text[key], anchor="w", justify="left", wraplength=300, **style))

        def button(text, command):
            add(tk.Button(top, text=text, command=command, bg=BUTTON, fg=FG, activebackground="#555555",
                          activeforeground=FG, relief="flat"), pady=4)

        line("status")
        line("check")
        title("Overlay (F6)")
        for k, text in (("overlay", "Show the overlay"),
                        ("boxes", "AI boxes (magenta zombie, orange Volatile, blue human, green friendly NPC)"),
                        ("bars", "Health bars"), ("heads", "Head dots")):
            check(k, text)
        title("Loot")
        for label, color in self.lvt.values():
            check(label, label, color)
        add(tk.Scale(top, from_=10, to=100, orient="horizontal", label="Loot distance (m)", variable=self.loot_dist,
                     troughcolor=BUTTON, highlightthickness=0, bg=BG, fg=FG, activebackground=BG))
        check("fast", "Instant search within the loot distance (writes)")
        title("Player")
        line("health")
        check("god", "God mode (writes game memory)")
        for k, text in CHEAT_TEXT.items():
            check(k, text)
        check("onehit", f"One-hit melee: an enemy within {ONEHIT} m that loses health while no gun is in hand dies "
                        "(writes)")
        check("fury", "Infinite fury: beast mode at any time, and it does not run out (writes)")
        for k, text in SLIDERS.items():
            add(tk.Scale(top, from_=1, to=4, resolution=0.25, orient="horizontal", label=f"{text} (x1 = off; writes)",
                         variable=self.factor[k], troughcolor=BUTTON, highlightthickness=0, bg=BG, fg=FG,
                         activebackground=BG))
        title("Teleport (F9 mark, F10 go, F8 map waypoint: writes)")
        line("tele")
        line("way")
        button("Teleport to the map waypoint (F8)", self.go_waypoint)
        line("fly")
        title("Time of day (writes)")
        line("clock")
        for value, text in (("off", "Clock runs"), ("day", "Always day (holds 12:00)"),
                            ("night", "Always night (holds 00:00)")):
            add(tk.Radiobutton(top, text=text, variable=self.hold, value=value, anchor="w", selectcolor=BUTTON, **style))
        button("Day (12:00)", lambda: self.set_clock(0.5))
        button("Night (00:00)", lambda: self.set_clock(0.0))
        title("Nuke (F7)")
        check("armed", f"Armed: kill zombies and hostile humans within {RADIUS} m, never NPCs (writes)")
        button("Nuke now", self.nuke)
        line("nuke")
        title("Aim (hold F11: track the nearest head; writes)")
        check("smart", "Smart aim: lock on while the fire button is held with a gun in hand (writes)")
        line("aim")
        button("Quit (or hold F1)", self.stop)

    def stop(self):
        self.running = False

    def save_settings(self):
        """At each change of a switch, slider or the loot distance, so a crash or a kill loses nothing."""
        data = ({k: v.get() for k, v in self.v.items() if k not in NOT_SAVED} | {"loot_dist": self.loot_dist.get()}
                | {k: v.get() for k, v in self.factor.items()} | {"clock_hold": self.hold.get(), "base": self.base})
        try:
            with open(SETTINGS, "w") as f:
                json.dump(data, f, indent=1)
        except OSError as e:
            print(f"  settings not saved: {e}", flush=True)

    def scan_all(self, full=False):
        """One scan in a background thread, so the panel and the overlay keep running: a full one (about 12 s) at the
        start, every FULL_EVERY scans and when asked, else a rescan of the reservations that held objects (1 to 2 s)."""
        if self.job and self.job.is_alive():
            return
        me = player_pos(self.p, self.player) if alive(self.p, self.player, self.pvt) else None
        self.scan_at = me if sane(me) else None  # count the walk to the next scan from here
        self.scans += 1
        if full or self.scans % FULL_EVERY == 0:  # an empty memo: the scan reads all memory
            self.memo.clear()

        def job():
            t0, rescan, by = time.time(), bool(self.memo), defaultdict(list)
            single = (self.pvt, self.phvt, self.look_vt, self.dn_vt, self.level_vt, self.fvt)  # one object each
            windows = [(v, v) for v in (*single, self.hvt, self.cvt, self.item_vt, *self.lvt)]
            found = scan(self.p, windows, memo=self.memo)[0]
            if rescan and not set(single) <= {v for h, v in found}:  # e.g. a new player after a death, in an old region
                self.memo.clear()
                rescan, found = False, scan(self.p, windows, memo=self.memo)[0]
            for h, v in found:
                by[v].append(h)
            self.melee = [o for o in by[self.item_vt] if melee_durability(self.p, o, self.item_vt, self.melee_vt)]
            if by[self.hvt]:
                self.heap = heap_of(self.p, by[self.hvt][0])
            self.cams = {h: self.cvt for h in by[self.cvt]}
            self.loot_objs = [(h, v) for v in self.lvt for h in by[v]]
            self.phm = next(iter(by[self.phvt]), None)
            self.look = next(iter(by[self.look_vt]), None)
            self.dnc = next(iter(by[self.dn_vt]), None)
            self.level, self.furym = next(iter(by[self.level_vt]), None), next(iter(by[self.fvt]), None)
            self.player = next(iter(by[self.pvt]), None)  # last: the tick starts to draw when the player is alive
            print(f"  {time.strftime('%H:%M:%S')} {'rescan' if rescan else 'full scan'} done in {time.time() - t0:.1f} s, "
                  f"{self.memo['read'] / 1e9:.2f} GB read: player {'found' if self.player else 'NOT found'}, {len(by[self.hvt])} AI, "
                  f"{len(self.cams)} cameras, {len(self.loot_objs)} loot objects, "
                  f"LookController {'found' if self.look else 'NOT found'}", flush=True)

        self.job = threading.Thread(target=job, daemon=True)
        self.job.start()

    def place(self):
        rect = client_rect(self.game)
        if rect != self.rect:
            self.rect = rect
            self.paint.place(rect)

    def pressed(self, vk):
        """True once per key press, not while the key is held."""
        down = bool(u.GetAsyncKeyState(vk) & 0x8000)
        was, self.keys_was[vk] = self.keys_was.get(vk, False), down
        return down and not was

    def writer(self):
        """The write handle, opened at the first write (god mode or the nuke)."""
        if self.pw is None:
            self.pw = mem.Process(EXE, pid=self.p.pid, write=True)
        return self.pw

    def tick(self):
        """One frame, between paint.begin() and paint.end(): the keys, the slow update, god mode, the overlay."""
        if key_down():
            self.stop()
            return
        p, now = self.p, time.time()
        if self.pressed(VK_F6):
            self.v["overlay"].set(not self.v["overlay"].get())
        if self.pressed(VK_F7):
            self.nuke()
        if not alive(p, self.player, self.pvt):  # the start, a death, a sleep or a load made a new player
            if not p.running():  # session 9: else 16,151 empty scans in 2.7 minutes after the game closed
                print("  the game has ended", flush=True)
                self.stop()
                return
            self.scan_all()
            self.text["status"].set("Scanning memory (about 12 s)...")
            return
        me = player_pos(p, self.player)
        self.teleport_keys(me)
        self.flight()
        if now >= self.next_slow and sane(me):
            self.slow(me)
            self.next_slow = now + 1
        if self.v["god"].get() and self.passed("god") and alive(p, self.phm, self.phvt) and (hp := player_health(p, self.phm)):
            heal(self.writer(), self.phm, hp)
        self.no_reload()
        self.one_hit(me)
        self.track(me)
        if self.v["overlay"].get() and self.cam is not None and sane(me) and u.GetForegroundWindow() == self.game:
            self.draw(me, view_proj(p, self.cam))

    def slow(self, me):
        """Once a second: new AI, their health and type, the camera, the window, the loot list, the panel texts."""
        p = self.p
        every = humans_in(p, self.heap, self.hvt) if self.heap else []
        self.humans = [a for a in every if in_world(p, a)]  # parked (despawned) AI keep full health: no box, no aim
        self.cheats()
        self.fury()
        way = waypoint(p, self.level, self.way_vt) if alive(p, self.level, self.level_vt) else None
        self.text["way"].set(f"map waypoint {flat(me, way):.0f} m away, height {way[1]:.0f} (you: {me[1]:.0f})" if way
                             else "no waypoint on the map")
        known = {o for o, v in self.loot_objs}
        for a in every:  # a corpse made after the last full scan; a dead AI can be parked already
            try:
                b = p.u64(a + BODY_LINK)
            except OSError:
                continue
            if b not in known and alive(p, b, self.body_vt):
                self.loot_objs.append((b, self.body_vt))
        self.hms = {a: el for a in self.humans  # no None: a dying AI can have a module but no element (session 7 crash)
                    if (hm := health_module(p, a, self.hmvt)) and (el := health_element(p, hm))}
        self.kinds = {a: kind(p, a) for a in self.humans}  # the type name ('Biter', 'Volatile', ...) or None
        living = [a for a, el in self.hms.items() if (hp := health(p, el)) and hp[0] > 0]
        self.near = [a for a in living if self.kinds.get(a) not in (None, NPC) and sane(v := read(p, a + AI_POS))
                     and flat(me, v) < 3 * ONEHIT]  # a running zombie covers less than 10 m in the second until the next update
        self.cam = active_camera(p, self.cams, me)
        self.text["check"].set(self.self_check(me))  # before the writes below; it needs hms and the camera
        self.place()
        if self.scan_at is None:
            self.scan_at = me
        elif flat(me, self.scan_at) > RESCAN:
            self.scan_all()
        if self.jump_scans and time.time() >= self.jump_scans[0][0] and not self.job.is_alive():
            self.scan_all(full=self.jump_scans.pop(0)[1])
        dist, near, hidden = self.loot_dist.get(), [], 0
        for o, v in self.loot_objs:
            label, color = self.lvt[v]
            where = model_pos if label == "body" else loot_pos  # bodies are reused; their own matrix keeps an old place
            if alive(p, o, v) and sane(pos := where(p, o)) and flat(me, pos) < dist and (label == "body" or spawned(p, o)):
                if label in HAS_STATE and looted(p, o) or label == "body" and emptied(p, o) or label == "pickup" and no_item(p, o):
                    hidden += 1
                else:
                    near.append((pos, label, color))
                    if label in FAST and self.v["fast"].get() and self.passed("search") and p.f32(o + SEARCH_TIME) > 0:
                        self.writer().write_f32(o + SEARCH_TIME, 0.0)  # session 5: the game keeps the 0 (fastsearch.py)
        self.loot = near  # loot does not move, so its position is read once a second, not at each redraw
        kinds = [is_zombie(self.kinds.get(a)) for a in living]
        self.text["status"].set(f"{len(living)} living AI: {kinds.count(True)} zombies, {kinds.count(False)} humans, "
                                f"{kinds.count(None)} unknown\n{len(near)} loot within {dist} m, {hidden} looted (hidden)"
                                + ("\nscan running..." if self.job.is_alive() else ""))
        if alive(p, self.dnc, self.dn_vt):
            if (hold := self.hold.get()) in HOLD and self.passed("clock"):  # the Day/Night buttons' write, once a second
                set_time(self.writer(), self.dnc, HOLD[hold])
            self.text["clock"].set(f"Game clock {hhmm(p.f32(self.dnc + TIME[0]))}")
        hp = player_health(p, self.phm) if alive(p, self.phm, self.phvt) else None
        self.text["health"].set("Health " + " | ".join(f"{cur[0]:.0f} of {mx:.0f}" for cur, mx in hp) if hp
                                else "Health module not found yet")
        if self.cam is None:
            self.text["aim"].set("no camera at the player's head")
            return
        t = nearest(p, me, struct.unpack("<12f", p.read(self.cam + CAM_WORLD, 0x30)), living, self.hvt, self.hmvt)
        self.text["aim"].set(f"nearest AI {t[0]:.0f} m: turn {t[1][0]:+.1f} deg right, {t[1][1]:+.1f} deg up" if t
                             else "no living AI in front within 60 m")

    def track(self, me):
        """Each frame while F11 is held, or the fire button with a gun in hand (the smart switch): turn the view onto
        one AI's head. The user's choice (session 6): the nearest in distance in front, zombies and humans (unknown types
        skipped), no angle limit, instant. The lock holds until the AI dies or goes past 60 m, or the key goes up.
        Only while the game is the active window, so a click in the panel never turns the view."""
        p = self.p
        hold = u.GetForegroundWindow() == self.game and (u.GetAsyncKeyState(VK_F11) & 0x8000 or self.v["smart"].get() and (
            u.GetAsyncKeyState(VK_LBUTTON) & 0x8000) and held_gun(p, p.u64(self.player + 0x8), self.inv_vt, self.fire_vt))
        if not hold or self.cam is None or not alive(p, self.look, self.look_vt) or not self.passed("aim") or not sane(me):
            if len(self.errs) > 1:  # the first frame is the snap; after it, how far the head drifted between two turns
                drift = sorted(self.errs[1:])
                print(f"  track: {len(self.errs)} frames; crosshair to head before each turn: median "
                      f"{drift[len(drift) // 2]:.2f} deg, max {drift[-1]:.2f} deg", flush=True)
            self.lock, self.errs = None, []
            return
        m = struct.unpack("<12f", p.read(self.cam + CAM_WORLD, 0x30))
        t = self.lock and living_head(p, me, self.lock, self.hvt, self.hmvt)
        if not t:
            known = [a for a in self.humans if is_zombie(k := self.kinds.get(a)) is not None and k != NPC]
            if not (n := nearest(p, me, m, known, self.hvt, self.hmvt)):
                self.lock = None
                return
            self.lock, t = n[2], (n[0], n[3])
            print(f"  track: locked on {self.kinds.get(self.lock)} at {t[0]:.1f} m", flush=True)
        self.errs.append(math.hypot(*aim_error(m, t[1])))
        turn(self.writer(), self.look, p.u64(self.player + 0x8), angles(view(m)[0], t[1]))

    def set_clock(self, frac):
        """Jump the game clock (daynight.py). Session 6: the game logic follows at once (night XP, Volatiles, the night
        speed); the light followed within about 4 minutes."""
        if not alive(self.p, self.dnc, self.dn_vt) or not self.passed("clock"):
            self.text["clock"].set("Day/night object not found or not self-checked yet")
            return
        set_time(self.writer(), self.dnc, frac)
        self.text["clock"].set(f"{time.strftime('%H:%M:%S')}: set the game clock to {hhmm(frac)}")

    def nuke(self):
        if not (armed := self.v["armed"].get()) or not self.passed("health"):
            self.text["nuke"].set("Waits for the self-check of the AI health." if armed else "Not armed: tick 'Armed' first.")
            return
        me = player_pos(self.p, self.player) if alive(self.p, self.player, self.pvt) else None
        ts = targets(self.p, me, self.humans, self.hvt, self.hmvt) if sane(me) else []
        fire(self.writer(), ts)
        self.text["nuke"].set(f"{time.strftime('%H:%M:%S')}: wrote 0 to {len(ts)} enemies within {RADIUS} m")

    def draw(self, me, vp):
        w, h, g, on = self.rect[2], self.rect[3], self.paint, {k: v.get() for k, v in self.v.items()}
        for pos, label, color in self.loot:
            if on[label] and (s := w2s(vp, pos, w, h)) is not None:
                g.circle(s[0], s[1], 6, color)
                g.text(s[0] + 9, s[1], f"{label} {flat(me, pos):.0f} m", color, "w", 9)
        for a in self.humans:
            if not alive(self.p, a, self.hvt) or not sane(v := read(self.p, a + AI_POS)) or (d := flat(me, v)) > MAX_DIST:
                continue
            hp = health(self.p, el) if (el := self.hms.get(a)) else None
            if hp and hp[0] <= 0:
                continue  # dead
            feet, head = w2s(vp, v, w, h), w2s(vp, (v[0], v[1] + HEIGHT, v[2]), w, h)
            if feet is None or head is None:
                continue  # behind the camera
            name = self.kinds.get(a)
            color = next((c for t, c in TYPE_COLOR.items() if name and name.startswith(t)), None) or KIND_COLOR[
                is_zombie(name)]  # a prefix: 'Volatile_Permadeath' is a Volatile too (session 6)
            half = (feet[1] - head[1]) * 0.2
            left, top, bottom = feet[0] - half, head[1], feet[1]
            if on["boxes"]:
                g.rect(left, top, feet[0] + half, bottom, color)
                g.text(feet[0], bottom + 3, f"{d:.0f} m", color, "n", 10)
            if on["bars"] and hp and hp[1] > 0:  # left of the box; black is see-through in tk, so the empty part is dark red
                full = top + (bottom - top) * (1 - min(hp[0] / hp[1], 1))
                g.fill(left - 7, top, left - 3, bottom, "#600000")
                g.fill(left - 7, full, left - 3, bottom, "#00e000")
            if on["heads"] and (hd := head_pos(self.p, a)) and (s := w2s(vp, hd, w, h)) is not None:
                g.circle(s[0], s[1], 4, "#ffffff")


if __name__ == "__main__":
    try:
        App(mem.Process(EXE), "--tk" in sys.argv)
    except (RuntimeError, OSError) as e:  # the game is not running, no admin rights, or a class not found after an update
        print(f"Stopped: {e}")
        if getattr(sys, "frozen", False):  # a double-clicked exe: keep the window open
            try:
                input("Press Enter to close.")
            except EOFError:  # no console input (Windows calls NUL a terminal, so isatty() cannot tell)
                pass
