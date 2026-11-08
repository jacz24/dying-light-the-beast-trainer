"""Read-only restart test: do the stored offsets still hold after a full game restart? One scan, then each fact."""
import struct
import sys
from collections import Counter

sys.path.insert(0, r"C:\dev\Github\Aimbot")
import mem
from aikind import kind
from aim import LOOK_PITCH, LOOK_VT, LOOK_YAW, view
from camera import CAM_WORLD, CAMERA_VT, active_camera
from daynight import DAYNIGHT_VT, TIME, hhmm
from findptr import modules, scan
from godmode import PLAYER_HEALTH_VT, player_health
from head import head_pos
from items import FIREARM_VT, INVENTORY_VT, ITEM_VT, MELEE_VT
from loot import loot_vtables
from playervars import CHEATS, OFFSETS, SCALED, resolve_offsets, var_array
from radar import (AI_POS, HEALTH_VT, HUMAN_VT, PLAYER_VT, health, health_element, health_module, heap_of, humans_in,
                   in_world, player_pos, read)
from rtti import parse_addr, vtable_name
from teleport import BPC_VT, SOURCE, character
from track import flat, sane
from watch import EXE

fails = 0


def ok(label, cond, info=""):
    global fails
    fails += not cond
    print(f"  {'OK  ' if cond else 'FAIL'} {label}  {info}", flush=True)


p = mem.Process(EXE)
mods = modules(p)
print(f"game pid {p.pid}; module bases: " + ", ".join(f"{n} {b:#x}" for b, s, n in mods if "rwdi" in n.lower()))
want = {PLAYER_VT: "PlayerFallHelperModule", HUMAN_VT: "HumanAI", HEALTH_VT: "HumanHealthModule",
        CAMERA_VT: "CBaseCamera", PLAYER_HEALTH_VT: "PlayerHealthModule", ITEM_VT: "ItemDescWithContext",
        MELEE_VT: "ItemDescMelee", INVENTORY_VT: "InventoryItem", FIREARM_VT: "ItemDescFirearm",
        LOOK_VT: "LookController", DAYNIGHT_VT: "DayNightCycle", BPC_VT: "CBulletPhysicsCharacter"}
vt = {k: parse_addr(mods, k) for k in want}
print("1. vtable offsets -> class names")
for k, name in want.items():
    got = vtable_name(p, mods, vt[k]) or ""
    ok(f"{k} = {name}", got == name or got.endswith("::" + name), got)
lvt = loot_vtables(mods)
for v, (label, color) in lvt.items():
    got = vtable_name(p, mods, v) or ""
    ok(f"loot {label}", got.endswith(("Container", "CollectableObject")), got)

print("2. one scan (about 15 s)")
found, _ = scan(p, [(v, v) for v in (*vt.values(), *lvt)])
count = Counter(v for h, v in found)
first = {v: next(h for h, x in found if x == v) for v in count}
for k, name in want.items():
    print(f"     {name:24} {count[vt[k]]}")
for v, (label, color) in lvt.items():
    print(f"     loot {label:19} {count[v]}")
player = first.get(vt[PLAYER_VT])
ok("player found", player is not None)
if player is None:
    sys.exit("load a save first")
me = player_pos(p, player)
ok("player position (model matrix)", sane(me), str(tuple(round(c, 1) for c in me)) if me else "")
c = character(p, player, vt[BPC_VT])
src = p.vec3(c + SOURCE) if c else None
ok("teleport source = the feet", src is not None and flat(src, me) < 0.5 and abs(src[1] - me[1]) < 0.5, str(src))

print("3. AI")
heap = heap_of(p, first[vt[HUMAN_VT]])
ais = humans_in(p, heap, vt[HUMAN_VT])
ok("AI heap holds every HumanAI", len(ais) == count[vt[HUMAN_VT]], f"heap {heap[1] >> 20} MB: {len(ais)} of {count[vt[HUMAN_VT]]}")
near = sorted((flat(me, v), a, v) for a in ais if in_world(p, a) and sane(v := read(p, a + AI_POS)) and flat(me, v) < 50)
ok("spawned AI within 50 m", len(near) > 0, f"{len(near)}")
with_hp = heads = 0
for d, a, feet in near[:12]:
    hp = health(p, el) if (hm := health_module(p, a, vt[HEALTH_VT])) and (el := health_element(p, hm)) else None
    hd = head_pos(p, a)
    with_hp += hp is not None
    heads += hd is not None
    print(f"     {d:5.1f} m  {str(kind(p, a)):16} health {f'{hp[0]:.0f}/{hp[1]:.0f}' if hp else '-':>10}  "
          f"head {f'{hd[1] - feet[1]:.2f} m up' if hd else '-'}")
ok("health element path", with_hp > 0, f"{with_hp} of {min(12, len(near))}")
ok("head bone", heads > 0, f"{heads} of {min(12, len(near))}")

print("4. camera, view angles, clock, player health, player variables")
cams = {h: vt[CAMERA_VT] for h, v in found if v == vt[CAMERA_VT]}
cam = active_camera(p, cams, me)
m = struct.unpack("<12f", p.read(cam + CAM_WORLD, 0x30)) if cam else None
ok("active camera at the head", m is not None, f"eye {m[7] - me[1]:.2f} m above the feet" if m else "")
look = first.get(vt[LOOK_VT])
if m and look:
    eye, yaw, pitch = view(m)
    ly, lp = p.f32(look + LOOK_YAW), p.f32(look + LOOK_PITCH)
    ok("LookController = camera angles", abs((ly - yaw + 180) % 360 - 180) < 0.5 and abs(lp - pitch) < 0.5,
       f"look {ly:.2f}/{lp:.2f}, camera {yaw:.2f}/{pitch:.2f}")
dnc = first.get(vt[DAYNIGHT_VT])
ok("game clock", dnc is not None and 0 <= p.f32(dnc + TIME[0]) < 1, hhmm(p.f32(dnc + TIME[0])) if dnc else "")
phm = first.get(vt[PLAYER_HEALTH_VT])
hp = player_health(p, phm) if phm else None
ok("player health elements", bool(hp), " | ".join(f"{cur[0]:.0f} of {mx:.0f}" for cur, mx in hp) if hp else "")
arr = var_array(p, mods)
ok("player variable array", arr is not None, f"{arr:#x}" if arr else "")
resolve_offsets(p, mods)
known = [n for rows in CHEATS.values() for n, v in rows] + [n for rows in SCALED.values() for n in rows]
missing = [n for n in known if n not in OFFSETS]
ok("player variables found by name", not missing, f"{len(known) - len(missing)} of {len(known)}; missing {missing}")
print(f"{'ALL OK' if not fails else f'{fails} FAILED'}")
