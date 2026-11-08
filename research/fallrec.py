"""Read-only (session 8): what happens to the player's height after a long teleport? Run: python -m research.fallrec, then press F8 once.
20 samples a second; after a jump of more than 50 m between two samples it prints 20 s of height (every 0.25 s) against
the waypoint and the fall helper's last safe position (PlayerFallHelperModule +0x1b40). Runs 1 hour, or hold F1 to end."""
import math
import sys
import time

import mem
from findptr import modules, scan
from radar import PLAYER_VT, alive, player_pos
from rtti import parse_addr
from teleport import BPC_VT, SOURCE, character
from track import flat
from waypoint import LEVEL_VT, WAYPOINT_VT, waypoint
from watch import EXE, key_down

p = mem.Process(EXE)
mods = modules(p)
pvt, bvt, lvt, wvt = (parse_addr(mods, t) for t in (PLAYER_VT, BPC_VT, LEVEL_VT, WAYPOINT_VT))


def find():
    found = scan(p, [(v, v) for v in (pvt, lvt)])[0]
    return next(h for h, v in found if v == pvt), next(h for h, v in found if v == lvt)


player, level = find()
print(f"{time.strftime('%H:%M:%S')} ready: recording", flush=True)
end, last, after, way = time.time() + 3600, None, None, None
while time.time() < end and not key_down():
    if not alive(p, player, pvt):
        player, level = find()
        print(f"{time.strftime('%H:%M:%S')} new player object (death or load)", flush=True)
        continue
    me = player_pos(p, player)
    c = character(p, player, bvt)
    src = p.vec3(c + SOURCE) if c else None
    safe = p.vec3(player + 0x1b40)
    w = waypoint(p, level, wvt)
    way = w or way
    now = time.time()
    if last and flat(me, last) > 50:
        after, t0, nxt = now + 20, now, now  # a free fall of 400 m (session 8 saw -375) takes about 9 s
        print(f"{time.strftime('%H:%M:%S')} JUMP {flat(me, last):.0f} m to {tuple(round(x, 1) for x in me)}; waypoint "
              f"{tuple(round(x, 1) for x in way) if way else None}", flush=True)
    if after and now <= after and now >= nxt:
        print(f"   +{now - t0:4.2f} s  height {me[1]:8.2f}  source {src[1] if src else float('nan'):8.2f}  "
              f"{flat(me, way) if way else float('nan'):6.1f} m from the waypoint  last safe "
              f"{tuple(round(x, 1) for x in safe)}", flush=True)
        nxt = now + 0.25
    last = me
    time.sleep(0.05)
