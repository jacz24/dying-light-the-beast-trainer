"""The app's cheats that write each second or each frame (moved out of overlay.py in session 7; no change in behaviour).

Cheats is a mixin for overlay.App: it uses the App's state (self.p, self.mods, self.v switches, self.factor sliders,
self.base, self.player, the vtables, self.hms, self.near, self.kinds) and self.writer() / self.save_settings().
- cheats(): once a second, the game's player variables (playervars.py) and the melee durability (items.py).
- no_reload(): each frame, the magazine of the gun in hand.
- one_hit(): each frame, one-hit melee through the health element (the nuke's write).
- fury(): once a second, infinite fury (beast mode).
- restore(): at the end, the player variables back to the game's values.
"""
from items import DURABILITY, LOADED, held_gun, melee_durability
from nuke import fire
from playervars import CHEATS, SCALED, apply, scale, var_array
from radar import AI_POS, alive, health, health_module, read
from track import flat, sane

# PlayerFuryModule (session 7, watched through one beast mode): +0x14 the points (0 to FuryMaxPoints = 100), +0x18 the
# length of beast mode (34 s while it runs, else 0), +0x1c a timer: the time left while it runs, the 10 s 'charged'
# time when the meter is full, else -1 or 0. Beast mode ended when the timer ran out, with 5.45 points still left.
FURY_VT = "gamedll_ph_x64_rwdi.dll+0x2981ed0"
FURY_POINTS, FURY_LENGTH, FURY_LEFT, FURY_MAX = 0x14, 0x18, 0x1c, 100.0

CHEAT_TEXT = {"ammo": "Infinite ammo and arrows (writes)", "stamina": "Infinite stamina (writes)",
              "durability": "No durability loss, melee weapons (writes)", "reload": "No reload, gun in hand (writes)",
              "immortal": "Immortality: the game's own switch (writes)",
              "fall": "No fall damage: FallDamageResistance 1.0 (writes)"}
ONEHIT = 5         # m: one-hit melee range
SLIDERS = {"jump": "Super jump", "speed": "Speed, walk and sprint"}  # playervars.SCALED; x1 = off
SLIDER_START = 2.0  # the user's choice (session 7), until the first change is saved


class Cheats:
    def restore(self):
        """At the end (F1, Quit, the window closed, an error; not taskkill): the player-variable cheats back to the
        game's values (session 7). The switches and sliders stay saved, so the cheats come back at the next start."""
        arr = var_array(self.p, self.mods) if self.pw else None  # no write handle: nothing was written
        done = []
        try:
            for cheat in CHEATS:
                if arr and self.cheat_was.get(cheat):
                    apply(self.pw, self.mods, arr, cheat, False)
                    done.append(cheat)
            for cheat, rows in SCALED.items():
                if arr and any(n in self.base for n in rows):
                    scale(self.pw, self.mods, arr, cheat, 1, self.base)
                    done.append(cheat)
            if arr:
                self.base.clear()
        except (OSError, RuntimeError) as e:  # the game closed, or the guard refused: the saved base stays
            print(f"  restore stopped: {e}", flush=True)
        self.save_settings()
        print(f"  cheats off in the game: {', '.join(done) or 'none were on'}", flush=True)

    def cheats(self):
        """Once a second: the game's own player variables for the switches that are on (playervars.py); a switch
        turned off writes the defaults back once. The game may reset a variable, so 'on' writes again each second."""
        arr = var_array(self.p, self.mods)
        for cheat in CHEATS:
            on = self.v[cheat].get()
            if arr and (on or self.cheat_was.get(cheat)):
                try:
                    apply(self.writer(), self.mods, arr, cheat, on)
                except RuntimeError as e:  # the guard found no player variable there: never write blind
                    print(f"  {cheat}: {e}", flush=True)
                    self.v[cheat].set(False)
                    on = False
            self.cheat_was[cheat] = on
        had = dict(self.base)
        for cheat, rows in SCALED.items():  # the sliders: base x factor each second; x1 writes the base back once
            f = self.factor[cheat].get()
            if arr and (f != 1 or any(n in self.base for n in rows)):
                try:
                    scale(self.writer(), self.mods, arr, cheat, f, self.base)
                except RuntimeError as e:
                    print(f"  {cheat}: {e}", flush=True)
                    self.factor[cheat].set(1)
                    continue
                if f == 1:  # forget the base, so the next write reads a fresh one (a skill may raise it meanwhile)
                    for n in rows:
                        self.base.pop(n, None)
        if self.base != had:
            self.save_settings()
        if not self.v["durability"].get() or not self.passed("durability"):
            self.dura.clear()
            return
        for o in self.melee:  # keep each melee weapon at its value when the switch went on, or after a repair
            if (d := melee_durability(self.p, o, self.item_vt, self.melee_vt)) is None:
                continue
            keep = self.dura.setdefault(o, d)
            if d < keep:
                self.writer().write_f32(o + DURABILITY, keep)
            elif d > keep:
                self.dura[o] = d

    def fury(self):
        """Once a second (the switch): the fury points full, so beast mode can start at any time; while it runs, the
        time left back to the full length, so it does not end. Session 7: a write of 100 to the points held."""
        if not self.v["fury"].get() or not self.passed("fury") or not alive(self.p, self.furym, self.fvt):
            return
        length = self.p.f32(self.furym + FURY_LENGTH)
        self.writer().write_f32(self.furym + FURY_POINTS, FURY_MAX)
        if length > 0:  # beast mode runs; when idle the timer counts the 'charged' time, so leave it
            self.writer().write_f32(self.furym + FURY_LEFT, length)

    def no_reload(self):
        """Each frame: keep the magazine of the gun in hand at its count when the switch went on (a fast gun can empty
        it within a second). A reload or a bigger count raises the saved value."""
        if not self.v["reload"].get() or not self.passed("reload"):
            self.loaded.clear()
            return
        try:
            gun = held_gun(self.p, self.p.u64(self.player + 0x8), self.inv_vt, self.fire_vt)
            n = self.p.u32(gun + LOADED) if gun else None
        except OSError:
            return
        if n is None:
            return
        keep = self.loaded.setdefault(gun, n)
        if n < keep:
            self.writer().write(gun + LOADED, keep.to_bytes(4, "little"))
        elif n > keep:
            self.loaded[gun] = n

    def one_hit(self, me):
        """Each frame (the switch): an enemy within ONEHIT m whose health dropped since the last frame, while no gun is
        in hand, gets health 0 (the nuke's write). Session 7: the game's MeleeDamageMul only names a buff target
        ('Player_MeleeDamageMul'; the summed value was not found), so this works through the health instead."""
        if not self.v["onehit"].get() or not self.passed("health") or not sane(me):  # me: None while the game closes
            self.hp_was.clear()
            return
        p = self.p
        try:
            gun = held_gun(p, p.u64(self.player + 0x8), self.inv_vt, self.fire_vt)
        except OSError:
            return
        if gun:
            self.hp_was.clear()  # a gun hit is not melee
            return
        for a in self.near:
            if not (el := self.hms.get(a)) or not sane(v := read(p, a + AI_POS)) or flat(me, v) > ONEHIT or not (
                    hp := health(p, el)):
                continue
            was, self.hp_was[a] = self.hp_was.get(a, hp[0]), hp[0]
            if 0 < hp[0] < was and (hm := health_module(p, a, self.hmvt)):
                fire(self.writer(), [(0, hm, el, hp)])
                print(f"  one-hit: {self.kinds.get(a)} {was:.0f} -> {hp[0]:.0f}, set to 0", flush=True)
