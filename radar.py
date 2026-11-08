"""Step 3: a text radar. Lists the AI (people and zombies) around the player, live. Read-only.

Run: python radar.py     (elevated terminal, a save loaded). Hold F1 for half a second to end.
It finds the player and the AI by their class (vtable), so it works after a game restart.
It prints a line about every 2 seconds and, at the end, which AI moved and how fast.
"""
import math
import struct
import sys
import time

import numpy as np

import mem
from findptr import modules, scan
from rtti import parse_addr
from track import fastest, flat, sane
from watch import EXE, key_down

PLAYER_VT = "gamedll_ph_x64_rwdi.dll+0x2996e10"  # PlayerFallHelperModule. Stable after a restart, for this game build.
HUMAN_VT = "gamedll_ph_x64_rwdi.dll+0x293e8e0"   # HumanAI: one per person or zombie, in 0x4000-byte slots of one heap block
AI_POS = 0x1cc0      # live position in a HumanAI object (session 2: it walked with chasing zombies)
MODEL_MATRIX = 0xf0  # 3x4 row-major world matrix in a CModelObject. PlayerFallHelperModule+0x1b40 lags, do not use it.
NEAR = 150           # m. Track only AI within this ground distance.
HEALTH_VT = "gamedll_ph_x64_rwdi.dll+0x2a34308"  # HumanHealthModule
AI_HEALTH = (0x5e8, 0x228)  # HumanAI +0x5e8 -> object +0x228 -> HumanHealthModule (session 2: all 58 modules matched)
HEALTH = 0x28        # in a HumanHealthModule: only a display COPY of the current health; the game rewrites it
HEALTH_EL = 0x18     # HumanHealthModule +0x18 -> table; its first entry -> the lifecs element with the real health
EL_CUR = (0x1c, 0x20, 0x24)  # element: three copies of the real current health. Writing all three to 0 kills (session 2).
EL_MAX = 0x30        # element: the maximum health (also at +0x2c and +0x34)
PROXY = 0x208        # HumanAI -> 0x58 bytes into its CoAIProxy. Null in dormant slots, but ALSO in AI woken by gunfire.
FLAGS, SPAWNED = 0x20, 0x400  # HumanAI flag word: 0x85 dormant (pooled), 0x487 spawned into the world


def in_world(p, human):
    """False for a dormant HumanAI slot: the game keeps a pool of frozen AI with vtable, position and full health near
    the player, and wakes some on gunfire. Session 6: 4 slots that woke went +0x20 0x85 -> 0x487; of 121 AI, 96 of 97
    frozen ones had 0x85, 11 of 13 moving ones had 0x487 (the 3 exceptions: two lay still, one went dormant again).
    The first fix used +0x208 != 0 and hid the AI woken by gunfire (they have no CoAIProxy)."""
    try:
        return bool(p.u32(human + FLAGS) & SPAWNED)
    except OSError:
        return False


def read(p, addr):
    try:
        return p.vec3(addr)
    except OSError:
        return None


def player_pos(p, player):
    """PlayerFallHelperModule -> +0x8 PlayerDI_PH -> +0x8 CModelObject -> world matrix translation."""
    try:
        r = struct.unpack("<12f", p.read(p.u64(p.u64(player + 0x8) + 0x8) + MODEL_MATRIX, 0x30))
    except OSError:
        return None
    return r[3], r[7], r[11]


def alive(p, obj, vt):
    """An object is valid while it starts with its class vtable. The game frees objects (death, fast travel, a load,
    a sleep) and reuses the memory for other data, so an old address can read as garbage."""
    try:
        return obj is not None and p.u64(obj) == vt
    except OSError:
        return False


def health_module(p, human, hmvt):
    """The HumanHealthModule of a HumanAI, or None (idle slots have none)."""
    try:
        hm = p.u64(p.u64(human + AI_HEALTH[0]) + AI_HEALTH[1])
    except OSError:
        return None
    return hm if alive(p, hm, hmvt) else None


def health_element(p, hm):
    """The lifecs element that holds the real health of a HumanHealthModule, or None."""
    try:
        return p.u64(p.u64(hm + HEALTH_EL)) or None
    except OSError:
        return None


def health(p, el):
    """(current, maximum) real health from a health element, or None."""
    try:
        f = struct.unpack("<5f", p.read(el + EL_CUR[1], EL_MAX + 4 - EL_CUR[1]))  # +0x20 .. +0x30
    except OSError:
        return None
    return f[0], f[-1]


def find_objects(p, pvt, hvt):
    """(player object or None, [HumanAI objects]). One scan of all memory, about 75 s."""
    found, _ = scan(p, [(pvt, pvt), (hvt, hvt)])  # an object starts with its vtable pointer
    players = [h for h, v in found if v == pvt]
    return (players[0] if len(players) == 1 else None), [h for h, v in found if v == hvt]


def heap_of(p, addr):
    """(base, size) of the memory region that holds addr. All HumanAI objects sat in one 64 MB region."""
    return next((b, s) for b, s, protect, kind, res in p.regions() if b <= addr < b + s)


def humans_in(p, heap, hvt):
    """HumanAI objects in the AI heap. Takes about 0.04 s, so it can run every second. The heap grows (session 7:
    64 -> 80 MB during a gunfire ambush, and the AI in the new 16 MB had no box), so its size is read again each time."""
    try:
        q = np.frombuffer(p.read(heap[0], p.region_size(heap[0])), "<u8")
    except OSError:
        return []
    return [heap[0] + int(i) * 8 for i in np.flatnonzero(q == hvt)]


if __name__ == "__main__":
    p = mem.Process(EXE)
    pvt, hvt = (parse_addr(modules(p), t) for t in (PLAYER_VT, HUMAN_VT))
    print("scanning memory for the player and the AI (about 75 s)...", flush=True)
    player, humans = find_objects(p, pvt, hvt)
    if player is None or not humans:
        sys.exit(f"expected 1 player object and some HumanAI, found {player} and {len(humans)}. Load a save first. "
                 "If it still fails, the game build changed: the vtable offsets in this file need a new rtti.py run.")
    # shortcut: assumes all HumanAI stay in this one region. If a new zombie never shows up, search all regions.
    heap = heap_of(p, humans[0])
    print(f"player object at {player:#x}, {len(humans)} AI, AI heap {heap[0]:#x} ({heap[1] >> 20} MB).")
    print(f"radar on. Shows AI within {NEAR} m. Hold F1 to end.", flush=True)
    series, ids, t0, shown, rescan = {}, {}, time.time(), 0, 0
    while not key_down():
        if not alive(p, player, pvt):
            print("  the player object is gone (death, fast travel, sleep or a load). Rescanning, about 75 s...", flush=True)
            player, found = find_objects(p, pvt, hvt)
            heap = heap_of(p, found[0]) if found else heap
            continue  # the next pass checks the new player object
        t = time.time() - t0
        if t >= rescan:
            humans, rescan = humans_in(p, heap, hvt), t + 1  # catches AI that spawn later
        me = player_pos(p, player)
        if not sane(me):
            time.sleep(0.1)
            continue
        # ids: a stable number per HumanAI object
        active = {ids.setdefault(a, len(ids)): v for a in humans
                  if alive(p, a, hvt) and sane(v := read(p, a + AI_POS)) and flat(me, v) < NEAR}
        for i, v in active.items():
            series.setdefault(i, []).append((t, v))
        if t >= shown:
            near = sorted((flat(me, v), i) for i, v in active.items())[:5]
            print(f"  {t:6.1f} s  me=({me[0]:.0f},{me[1]:.0f},{me[2]:.0f})  near={len(active)}  nearest: "
                  + ", ".join(f"#{i} {d:.0f} m" for d, i in near), flush=True)
            shown += 2
        time.sleep(0.1)
    while key_down():
        time.sleep(0.01)
    if not series:
        sys.exit("no AI was seen near the player")
    print(f"\n{len(series)} AI were near at some time:")
    for i, s in sorted(series.items()):
        path = sum(math.dist(a[1], b[1]) for a, b in zip(s, s[1:]))
        print(f"  #{i:3}  {len(s):4} samples  first {tuple(round(c, 1) for c in s[0][1])}  last {tuple(round(c, 1) for c in s[-1][1])}"
              f"  path {path:6.1f}  fastest {fastest(s):.2f} per s")
