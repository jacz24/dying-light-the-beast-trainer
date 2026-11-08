"""Version safety (session 8): what the app checks, so a game update cannot make it write into the wrong place.

resolve(), at the start: each vtable constant is checked by its class name, and a moved one is found by name
(rtti.resolve_vtables, 0.5 s; 6.8 s after an update); the player-variable offsets come by name from the game's code, and
the path to them from a code signature (playervars.resolve_offsets). Before session 8 only the class was checked, so a
moved variable offset could write another variable of the same class.
SelfCheck, from the first slow update on: a read-only check per feature of the fields it writes. The user's choice: a
feature does not write while its check fails or cannot run yet, the check runs again each second, the first pass is
final. Each strong check failed in a test with its field moved by a few bytes. The weak ones only test ranges (a moved
fury field passed): reload and durability write back an earlier value of the same field; fury writes 100 into one
float of its own module.
"""
import struct
import time

from aim import LOOK_PITCH, LOOK_VT, LOOK_YAW, PDI_VIEW, view
from camera import CAM_WORLD, CAMERA_VT
from cheats import FURY_LEFT, FURY_MAX, FURY_POINTS, FURY_VT
from daynight import DAYNIGHT_VT, TIME, hhmm
from godmode import PLAYER_HEALTH_VT, player_health
from items import FIREARM_VT, INVENTORY_VT, ITEM_VT, LOADED, MELEE_VT, held_gun
from loot import LOOT
from lootstate import KIND as LOOT_KIND, SEARCH_TIME
from playervars import CHEATS, OFFSETS, PATH, PLAYER_STATE, SCALED, VARS, resolve_offsets
from radar import EL_CUR, EL_MAX, HEALTH, HEALTH_VT, HUMAN_VT, PLAYER_VT, alive, health_module
from rtti import parse_addr, resolve_vtables
from teleport import BODY_PTR, BODY_SPEED, BPC_VT, LEVEL_SPEED, SOURCE, UP_SPEED, character
from track import flat, sane
from waypoint import LEVEL_VT, WAYPOINT_VT, waypoint

LOOT_CLASS = {"search": "Container", "pickup": "ComplexContainer", "body": "BodyContainer",
              "collectable": "CollectableObject"}
CLASSES = {PLAYER_VT: "PlayerFallHelperModule", HUMAN_VT: "HumanAI", HEALTH_VT: "HumanHealthModule",
           CAMERA_VT: "CBaseCamera", PLAYER_HEALTH_VT: "PlayerHealthModule", ITEM_VT: "ItemDescWithContext",
           MELEE_VT: "ItemDescMelee", INVENTORY_VT: "InventoryItem", FIREARM_VT: "ItemDescFirearm",
           LOOK_VT: "LookController", DAYNIGHT_VT: "DayNightCycle", BPC_VT: "CBulletPhysicsCharacter",
           LEVEL_VT: "LevelDI", WAYPOINT_VT: "Locations::WaypointLocation", FURY_VT: "PlayerFuryModule",
           **{v: LOOT_CLASS[label] for v, (label, color) in LOOT.items()}}
FEATURES = ("god", "teleport", "waypoint", "noclip", "aim", "health", "clock", "fury", "reload", "durability", "search")


def resolve(p, mods):
    """At the start, before any parse_addr() of a vtable. Raises if a moved class is not found once by name."""
    t = time.time()
    moved = resolve_vtables(p, mods, CLASSES)
    resolve_offsets(p, mods)
    missing = [n for rows in CHEATS.values() for n, v in rows if n not in OFFSETS] + [
        n for rows in SCALED.values() for n in rows if n not in OFFSETS]
    same = PATH and PATH["state"] == parse_addr(mods, PLAYER_STATE) and PATH["vars"] == VARS
    print(f"version check in {time.time() - t:.1f} s: {len(CLASSES)} classes "
          + (f"({len(moved)} moved, found by name: {', '.join(moved.values())})" if moved else "where they were")
          + "; player variables by name: " + (f"MISSING {missing} (their cheats refuse)" if missing else "all found")
          + "; the path to them: " + ("as before" if same else "MOVED, from the code signature" if PATH
                                      else "signature NOT found, the old constant (the guard checks each write)"),
          flush=True)


def close(a, b, tol):
    return abs(a - b) <= tol


class SelfCheck:
    """A mixin for overlay.App. self.checks: {feature: (True | False | None, text)}; None = cannot tell yet."""

    def passed(self, feature):
        return self.checks.get(feature, (None,))[0] is True

    def self_check(self, me):
        """Once a second (slow()): each check that has not passed yet runs again; a change is printed; returns the panel
        text (the features that failed, with why, and the ones that wait)."""
        for f in FEATURES:
            if self.passed(f):
                continue
            try:
                r = getattr(self, "check_" + f)(me)
            except OSError as e:
                r = (None, f"unreadable ({e})")
            if r[0] != self.checks.get(f, (None,))[0] or f not in self.checks:
                print(f"  self-check {f}: {({True: 'passed', False: 'FAILED, off', None: 'waits'})[r[0]]}: {r[1]}",
                      flush=True)
            self.checks[f] = r
        failed = [f"{f} ({r[1]})" for f, r in self.checks.items() if r[0] is False]
        waits = [f for f, r in self.checks.items() if r[0] is None]
        return (f"Self-check: {sum(r[0] is True for r in self.checks.values())} of {len(FEATURES)} passed"
                + (f"\nFAILED, off: {'; '.join(failed)}" if failed else "") + (f"\nwaits: {', '.join(waits)}" if waits else ""))

    def check_god(self, me):
        """Both health elements: the three current copies agree, 0 <= current <= maximum < 1e5."""
        hp = player_health(self.p, self.phm) if alive(self.p, self.phm, self.phvt) else None
        if not hp:
            return None, "no player health module yet"
        good = all(max(c) - min(c) < 0.01 and 0 <= c[0] <= mx and 1 <= mx < 1e5 for c, mx in hp)
        return good, " | ".join(f"{'/'.join(f'{x:.1f}' for x in c)} of {mx:.0f}" for c, mx in hp)

    def check_teleport(self, me):
        """The source the teleport writes (CBulletPhysicsCharacter +0xfd0) is at the feet of the model."""
        if (c := character(self.p, self.player, self.char_vt)) is None:
            return False, "no CBulletPhysicsCharacter at PlayerDI_PH +0xf0 +0x20"
        src = self.p.vec3(c + SOURCE)
        return flat(src, me) < 0.5 and close(src[1], me[1], 0.5), f"source {flat(src, me):.2f} m from the feet"

    def check_noclip(self, me):
        """The speeds NoClip sets to 0 (session 9): the up speed has zero x and z neighbours, and the level speed equals
        the btRigidBody's while the player moves (it waits for a walk, so two zeros cannot pass it)."""
        p = self.p
        if (c := character(p, self.player, self.char_vt)) is None:
            return False, "no CBulletPhysicsCharacter at PlayerDI_PH +0xf0 +0x20"
        x, up, z = p.vec3(c + UP_SPEED - 4)
        if x != 0 or z != 0 or not abs(up) < 300:
            return False, f"up speed {up:.2f} with neighbours {x:.2f}, {z:.2f} (expected 0)"
        level, body = p.vec3(c + LEVEL_SPEED), p.vec3(p.u64(c + BODY_PTR) + BODY_SPEED)
        if abs(level[0]) + abs(level[2]) < 1:
            return None, "walk a few steps (the level speed is compared while you move)"
        good = level[1] == 0 and close(level[0], body[0], 0.2) and close(level[2], body[2], 0.2)  # 2 reads: a frame apart
        return good, f"level speed ({level[0]:.2f}, {level[2]:.2f}), rigid body ({body[0]:.2f}, {body[2]:.2f})"

    def check_waypoint(self, me):
        """The waypoint object has its class (waypoint() checks it); its position is a sane place."""
        way = waypoint(self.p, self.level, self.way_vt) if alive(self.p, self.level, self.level_vt) else None
        if way is None:
            return None, "no waypoint on the map"
        return sane(way) and abs(way[1]) < 2000, f"{flat(me, way):.0f} m away, height {way[1]:.0f}"

    def check_aim(self, me):
        """Both angle stores that turn() writes equal the camera's angles (the camera can lag one frame)."""
        p = self.p
        if self.cam is None or not alive(p, self.look, self.look_vt):
            return None, "no camera at the player's head"
        _, yaw, pitch = view(struct.unpack("<12f", p.read(self.cam + CAM_WORLD, 0x30)))
        wy, wp = struct.unpack("<2f", p.read(p.u64(self.player + 0x8) + PDI_VIEW, 8))
        d = max(abs((p.f32(self.look + LOOK_YAW) - yaw + 180) % 360 - 180), abs(p.f32(self.look + LOOK_PITCH) - pitch),
                abs((wy - yaw + 180) % 360 - 180), abs(wp - pitch))
        return d < 1.0, f"the view angles are {d:.2f} deg from the camera"

    def check_health(self, me):
        """The nuke and one-hit write the health element and the display copy. Up to 10 AI with health: the three
        current copies agree, 0 <= current <= maximum < 1e6, and the display copy equals the element on most of them."""
        rows = []
        for a, el in list(self.hms.items())[:10]:
            cur, mx = struct.unpack("<3f", self.p.read(el + EL_CUR[0], 12)), self.p.f32(el + EL_MAX)
            hm = health_module(self.p, a, self.hmvt)
            rows.append((max(cur) - min(cur) < 0.01 and 0 <= cur[0] <= mx and 1 <= mx < 1e6,
                         hm is not None and close(self.p.f32(hm + HEALTH), cur[0], 1)))
        if not rows:
            return None, "no AI with health near"
        good, shown = sum(r[0] for r in rows), sum(r[1] for r in rows)
        return good == len(rows) and 2 * shown > len(rows), f"{good} of {len(rows)} elements sane, {shown} display copies equal"

    def check_clock(self, me):
        """The three copies of the time of day agree and lie in [0, 1)."""
        if not alive(self.p, self.dnc, self.dn_vt):
            return None, "no DayNightCycle yet"
        t = [self.p.f32(self.dnc + o) for o in TIME]
        spread = max(abs((x - t[0] + 0.5) % 1 - 0.5) for x in t)
        return all(0 <= x < 1 for x in t) and spread < 0.01, f"{hhmm(t[0])}, copies within {spread:.5f}"

    def check_fury(self, me):
        """Weak: the points, the length and the timer lie in their ranges."""
        if not alive(self.p, self.furym, self.fvt):
            return None, "no PlayerFuryModule yet"
        pts, length, left = struct.unpack("<3f", self.p.read(self.furym + FURY_POINTS, 12))
        return (0 <= pts <= FURY_MAX and 0 <= length <= 100 and -1 <= left <= 100,
                f"points {pts:.1f}, length {length:.0f}, timer {left:.1f}")

    def check_reload(self, me):
        """Weak: the gun in hand (a class-checked chain) has a magazine count from 0 to 500."""
        gun = held_gun(self.p, self.p.u64(self.player + 0x8), self.inv_vt, self.fire_vt)
        if gun is None:
            return None, "no gun in hand"
        n = self.p.u32(gun + LOADED)
        return n <= 500, f"magazine {n}"

    def check_durability(self, me):
        """Weak: the melee items (a class-checked type) read a durability from 0 to 1e4 (the scan keeps only those)."""
        return (True, f"{len(self.melee)} melee weapons") if self.melee else (None, "no melee weapon found yet")

    def check_search(self, me):
        """The loot that instant search writes (search and body): kind 0 to 2 and a search time of 0, 0.1 or 1 s."""
        p, rows = self.p, []
        for o, v in self.loot_objs:
            if self.lvt[v][0] in ("search", "body") and alive(p, o, v):
                rows.append(p.u32(o + LOOT_KIND) in (0, 1, 2) and any(
                    close(p.f32(o + SEARCH_TIME), x, 1e-4) for x in (0.0, 0.1, 1.0)))
        if len(rows) < 5:
            return None, f"{len(rows)} search and body loot objects known"
        return sum(rows) >= 0.9 * len(rows), f"{sum(rows)} of {len(rows)} loot objects: kind 0 to 2, time 0, 0.1 or 1 s"
