"""Find the 'already looted' state: record the loot objects while the player loots, then list the fields that changed
while the player stood next to that object. Read-only.

Run: python -m research.lootwatch            scan (about 75 s), record until F9, then analyze
     python -m research.lootwatch analyze    analyze the saved file again
F9 ends it (not F1), so the overlay and the nuke keep running.
Records each loot object within NEAR m of the player: its first SPAN bytes, and INNER bytes of each object that its
first 0x200 bytes point to (the state can live one pointer away). Only the changes are kept.
"""
import math
import pickle
import struct
import sys
import time
from collections import defaultdict

import numpy as np

OUT = __file__.replace(".py", ".pkl")
NEAR, SPAN, INNER = 40, 0x400, 0x100
NOISY = 30    # a field that changed more often than this is a timer or a counter, not a looted flag
REACH = 4.0   # m. A change counts when the player was this close to the object.
VK_F9 = 0x78


def record():
    import ctypes
    import mem
    from findptr import modules, scan
    from loot import loot_pos, loot_vtables
    from radar import PLAYER_VT, player_pos
    from rtti import parse_addr
    from track import flat, sane
    from watch import EXE

    p = mem.Process(EXE)
    mods = modules(p)
    lvt, pvt = loot_vtables(mods), parse_addr(mods, PLAYER_VT)
    print("scanning (about 75 s)...", flush=True)
    found, _ = scan(p, [(v, v) for v in [pvt, *lvt]])
    player = next(h for h, v in found if v == pvt)
    me = player_pos(p, player)
    objs = {h: (lvt[v][0], pos) for h, v in found if v in lvt and sane(pos := loot_pos(p, h)) and flat(me, pos) < NEAR}
    blocks = []  # (object, pointer offset in the object or None for the object itself, address, size)
    for h in objs:
        blocks.append((h, None, h, SPAN))
        for i, (ptr,) in enumerate(struct.iter_unpack("<Q", p.read(h, 0x200))):
            if 0x10000 < ptr < 1 << 47 and ptr != h:
                blocks.append((h, i * 8, ptr, INNER))

    def snap():
        out = []
        for h, off, a, n in blocks:
            try:
                out.append(np.frombuffer(p.read(a, n), "<u4"))
            except OSError:
                out.append(None)
        return out

    prev = snap()
    keep = [i for i, b in enumerate(prev) if b is not None]
    blocks, prev = [blocks[i] for i in keep], [prev[i] for i in keep]
    changes, track, t0 = defaultdict(list), [], time.time()
    print(f"{len(objs)} loot objects within {NEAR} m, {len(blocks)} memory blocks. RECORDING now. Search two 'search' "
          "containers and take two 'pickup' items, one at a time. Then push F9.", flush=True)
    while not ctypes.windll.user32.GetAsyncKeyState(VK_F9) & 0x8000:
        t = time.time() - t0
        track.append((t, player_pos(p, player)))
        cur = snap()
        for b, (a, c) in enumerate(zip(prev, cur)):
            if c is None:
                continue  # unreadable now (freed); keep the old bytes
            for k in np.flatnonzero(a != c):
                lst = changes[(b, int(k))]
                if len(lst) <= NOISY:
                    lst.append((t, int(a[k]), int(c[k])))
            prev[b] = c
        time.sleep(0.2)
    pickle.dump({"objs": objs, "blocks": blocks, "changes": dict(changes), "track": track}, open(OUT, "wb"))
    print(f"saved {len(track)} samples over {track[-1][0]:.0f} s", flush=True)


def as_float(u):
    return struct.unpack("<f", struct.pack("<I", u))[0]


def analyze():
    d = pickle.load(open(OUT, "rb"))
    objs, blocks, changes, track = d["objs"], d["blocks"], d["changes"], d["track"]
    ts = [t for t, _ in track]

    def dist_at(t, pos):
        me = track[min(range(len(ts)), key=lambda i: abs(ts[i] - t))][1]
        return math.hypot(me[0] - pos[0], me[2] - pos[2]) if me else 1e9

    visited = {h for h, (_, pos) in objs.items() if any(m and math.hypot(m[0] - pos[0], m[2] - pos[2]) < REACH for _, m in track)}
    print(f"{len(track)} samples over {ts[-1]:.0f} s. You came within {REACH} m of {len(visited)} loot objects: "
          + ", ".join(sorted(objs[h][0] for h in visited)))
    # the vtable (first 8 bytes of the object) changed: the game freed the object, and every byte after it is noise
    freed = {blocks[b][0]: lst[0][0] for (b, k), lst in changes.items() if blocks[b][1] is None and k in (0, 1)}
    print(f"{len(freed)} loot objects were freed: " + ", ".join(
        f"{objs[h][0]} at {t:.0f}s ({dist_at(t, objs[h][1]):.1f} m from you)" for h, t in freed.items()))
    near, far = defaultdict(list), defaultdict(set)  # (label, pointer offset, byte offset) -> changes
    for (b, k), lst in changes.items():
        h, off, a, n = blocks[b]
        label, pos = objs[h]
        if h in freed:
            continue
        key = (label, off, k * 4)
        if len(lst) > NOISY:
            far[key].add(h)
        elif dist_at(lst[0][0], pos) <= REACH:
            near[key].append((h, lst))
        else:
            far[key].add(h)
    print("fields that changed next to the player (few times), and in how many other objects they changed anyway:")
    rank = sorted(near.items(), key=lambda kv: (len(far[kv[0]]), -len({h for h, _ in kv[1]})))
    for (label, off, byte), hits in rank[:25]:
        where = f"+{byte:#x}" if off is None else f"+{off:#x} -> +{byte:#x}"
        h, lst = hits[0]
        steps = ", ".join(f"{t:.0f}s {o:#x}->{n:#x} ({as_float(o):.3g}->{as_float(n):.3g})" for t, o, n in lst[:3])
        print(f"  {label:11} {where:16} near {len({x for x, _ in hits})} objects, elsewhere {len(far[(label, off, byte)])}."
              f"  e.g. {h:#x}: {steps}")


assert as_float(0x3f800000) == 1.0

if __name__ == "__main__":
    if sys.argv[1:] != ["analyze"]:
        record()
    analyze()
