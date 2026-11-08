"""The app's movement cheats: the teleports (moved out of overlay.py in session 9; no change in behaviour) and NoClip.

Movement is a mixin for overlay.App: it uses the App's state (self.p, self.player, self.level, self.mark, self.cam, the
vtables, self.text, self.jump_scans) and self.pressed() / self.passed() / self.writer().
- teleport_keys(): each frame, F9 marks where you stand, F10 teleports to the mark, F8 to the map waypoint.
- go_waypoint(): F8 or the panel button.
- long_jump(): a teleport over LONG_JUMP m asks for a full scan and a rescan later (the new area streams in).
- flight(): each frame (session 9). F3 NoClip: the app moves the teleport source along the view and writes it, and sets
  the up and level speeds to 0, so no fall speed builds up (it was 160 m/s in a fall through the map); it goes through
  walls (the user: works). F2 flying: the app writes only the speeds, so walls stop the player.
  python overlay.py --dry-fly: both only print what they would write.
"""
import ctypes
import math
import struct
import sys
import time

from camera import CAM_WORLD
from radar import alive, player_pos
from teleport import LEVEL_SPEED, SOURCE, UP_SPEED, character, teleport
from track import flat, sane
from waypoint import waypoint

LONG_JUMP, SETTLE = 200, 10  # m, s: a teleport this far asks for a full scan this much later (long_jump())
VK_F2, VK_F3, VK_F8, VK_F9, VK_F10 = 0x71, 0x72, 0x77, 0x78, 0x79
FLY_SPEED, FAST = 10.0, 4.0  # m/s, and the Shift factor (the user's choice, session 9)
FLY_KEYS = {"w": 0x57, "a": 0x41, "s": 0x53, "d": 0x44, "up": 0x20, "down": 0x11, "fast": 0x10}  # Space, Ctrl, Shift
DRY = "--dry-fly" in sys.argv
FLY_OFF = "Flying (F2) and NoClip (F3) off. On: W/S along the view, A/D sideways, Space up, Ctrl down, Shift x4"
u = ctypes.windll.user32


def fly_step(pos, m, keys, dt):
    """(x, height, z) after dt s of flight: W/S along the view (m: the 3x4 row-major camera world matrix; the camera
    looks down its -z column), A/D level sideways (its x column), Space/Ctrl straight up/down."""
    f = (-m[2], -m[6], -m[10])
    n = math.hypot(m[0], m[8]) or 1.0
    r = (m[0] / n, 0.0, m[8] / n)
    fw, side, up = keys["w"] - keys["s"], keys["d"] - keys["a"], keys["up"] - keys["down"]
    step = FLY_SPEED * (FAST if keys["fast"] else 1) * dt
    return tuple(p + step * (fw * fi + side * ri + up * (i == 1)) for i, (p, fi, ri) in enumerate(zip(pos, f, r)))


# a camera that looks down +x (forward (1, 0, 0), right +z, up +y): its z column is (-1, 0, 0), its x column (0, 0, 1)
_M = (0, 0, -1, 0, 0, 1, 0, 0, 1, 0, 0, 0)
_K = dict.fromkeys(FLY_KEYS, False)
assert fly_step((0, 0, 0), _M, _K | {"w": True}, 1) == (10, 0, 0)
assert fly_step((0, 0, 0), _M, _K | {"d": True, "fast": True}, 0.5) == (0, 0, 20)
assert fly_step((1, 2, 3), _M, _K | {"up": True, "s": True}, 1) == (-9, 12, 3)


class Movement:
    mode, fly = None, None  # None, "flying" or "NoClip"; fly: the position NoClip holds

    def teleport_keys(self, me):
        """Each frame: F9 marks where you stand, F10 teleports to the mark, F8 to the map waypoint."""
        p = self.p
        if self.pressed(VK_F9) and (c := character(p, self.player, self.char_vt)):
            self.mark = p.vec3(c + SOURCE)
            self.text["tele"].set(f"mark at {self.mark[0]:.0f} {self.mark[1]:.0f} {self.mark[2]:.0f}")
        if self.pressed(VK_F10) and self.mark and self.passed("teleport") and (c := character(p, self.player, self.char_vt)):
            self.long_jump(me, self.mark)
            self.go(c, self.mark)
            self.text["tele"].set(f"{time.strftime('%H:%M:%S')}: teleported to the mark")
        if self.pressed(VK_F8):
            self.go_waypoint()

    def go(self, c, pos):
        """The teleport write; NoClip then holds the new place, not the old one."""
        teleport(self.writer(), c, pos)
        self.fly = tuple(pos)

    def go_waypoint(self):
        """F8 or the button: teleport to the map waypoint (waypoint.py), 1 m above its height (the cheat table adds 1 m
        too). The same write as F10 (teleport.py, session 5). Session 9: the waypoint height is not always a surface (at a
        tall building the player fell 50 m into water, also with the area loaded); NoClip is the way out."""
        p = self.p
        way = waypoint(p, self.level, self.way_vt) if alive(p, self.level, self.level_vt) else None
        c = character(p, self.player, self.char_vt) if way and alive(p, self.player, self.pvt) else None
        if c is None or not (self.passed("teleport") and self.passed("waypoint")):
            self.text["tele"].set("no waypoint on the map" if way is None else "player not found" if c is None
                                  else "waits for the self-check (teleport, waypoint)")
            return
        self.long_jump(player_pos(p, self.player), way)
        self.go(c, (way[0], way[1] + 1, way[2]))
        self.text["tele"].set(f"{time.strftime('%H:%M:%S')}: teleported to the map waypoint")

    def long_jump(self, me, to):
        """Before a teleport over LONG_JUMP m: a full scan SETTLE s later, then a rescan 3 x SETTLE s later (slow() starts
        them). Session 8: after a jump, the rescan found 121 loot objects, the full scan at 10 s 337, a rescan at about
        30 s 420 (a full scan then: 417): the new area streams in for longer than 10 s."""
        if sane(me) and flat(me, to) > LONG_JUMP:
            self.jump_scans = [(time.time() + SETTLE, True), (time.time() + 3 * SETTLE, False)]
            print(f"  teleport of {flat(me, to):.0f} m: a full scan in {SETTLE} s, a rescan in {3 * SETTLE} s", flush=True)

    def flight(self):
        """Each frame: F2 flying, F3 NoClip (one at a time; the same key again turns it off). The keys count only while
        the game is the active window. NoClip moves the held position and writes it into the teleport source with both
        speeds at 0. Flying writes only the speeds (level +0xfc4, up +0x1328), so the game's physics moves the player and
        walls stop it; on the ground the game sets the up speed to 0, so Space (the game's jump) takes off."""
        p, c = self.p, character(self.p, self.player, self.char_vt)
        for vk, mode in ((VK_F2, "flying"), (VK_F3, "NoClip")):
            if self.pressed(vk):
                self.mode = None if self.mode == mode or c is None else mode
                self.fly = p.vec3(c + SOURCE) if c else None
                self.fly_c, self.fly_t, self.fly_shown = c, time.time(), 0
                print(f"  {mode} {'on' if self.mode else 'off'}{' (dry run: no writes)' if DRY and self.mode else ''}",
                      flush=True)
                self.text["fly"].set(FLY_OFF)
        if self.mode is None:
            return
        if c != self.fly_c or self.cam is None or not (self.passed("teleport") and self.passed("noclip")):
            self.mode = None  # a new player (a death, a load), or a check that has not passed: off, never a blind write
            self.text["fly"].set("Flight off: waits for the self-check (teleport, noclip; walk a few steps)"
                                 if c == self.fly_c else "Flight off: new player")
            print(f"  {self.text['fly'].get()}", flush=True)
            return
        now = time.time()
        dt, self.fly_t = min(now - self.fly_t, 0.1), now  # a stall (a scan, a window drag) does not jump the player
        active = u.GetForegroundWindow() == self.game
        keys = {k: active and bool(u.GetAsyncKeyState(vk) & 0x8000) for k, vk in FLY_KEYS.items()}
        m = struct.unpack("<12f", p.read(self.cam + CAM_WORLD, 0x30))
        if self.mode == "NoClip":
            self.fly = fly_step(self.fly, m, keys, dt)
            speed, what = (0.0, 0.0, 0.0), f"position {', '.join(f'{x:.2f}' for x in self.fly)}"
        else:
            speed = fly_step((0, 0, 0), m, keys, 1)  # m/s: one second of the same step
            what = f"speed {', '.join(f'{x:.1f}' for x in speed)}"
        self.text["fly"].set(f"{self.mode} on (F{2 if self.mode == 'flying' else 3})")
        if DRY:
            if now >= self.fly_shown:
                src = p.vec3(c + SOURCE)
                print(f"  {self.mode} (dry run): would write {what}; you are at {', '.join(f'{x:.2f}' for x in src)}, "
                      f"up speed {p.f32(c + UP_SPEED):.2f}", flush=True)
                self.fly_shown = now + 0.25
            return
        w = self.writer()
        w.write(c + LEVEL_SPEED, struct.pack("<3f", speed[0], 0, speed[2]))
        w.write_f32(c + UP_SPEED, speed[1])
        if self.mode == "NoClip":
            teleport(w, c, self.fly)
