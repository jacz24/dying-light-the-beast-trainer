"""Record health objects while the player hits zombies, then list the floats that went down in steps. Read-only.

Run: python -m research.healthwatch            scan (about 75 s), record until F1, then analyze
     python -m research.healthwatch analyze    analyze the saved file again
Also prints where HumanAI objects point at a health object (the link for the overlay).
"""
import struct
import sys
import time
from collections import Counter

import numpy as np

OUT = __file__.replace(".py", ".npz")
SPAN = 0x200   # bytes recorded per object
CLASSES = {"HumanHealthModule", "CoHealth", "PlayerHealthModule"}


def record():
    import mem
    from findptr import modules, scan
    from rtti import find_vtables, parse_addr
    from radar import HUMAN_VT
    from watch import EXE, key_down

    p = mem.Process(EXE)
    mods = modules(p)
    vts = find_vtables(p, mods, set(CLASSES))
    by_vt = {v: name for name, vs in vts.items() for v in vs}
    for name, vs in vts.items():
        print(name, [next(f"{n}+{v - b:#x}" for b, s, n in mods if b <= v < b + s) for v in vs])
    hvt = parse_addr(mods, HUMAN_VT)
    print("scanning (about 75 s)...", flush=True)
    found, _ = scan(p, [(v, v) for v in by_vt] + [(hvt, hvt)])
    humans = [h for h, v in found if v == hvt]
    objs = sorted((h, v) for h, v in found if v != hvt)
    addrs = np.array([h for h, v in objs], dtype=np.uint64)

    links = Counter()  # (offset in HumanAI, class) for each qword that points exactly at a health object
    for h in humans:
        q = np.frombuffer(p.read(h, 0x4000), dtype="<u8")
        for i in np.flatnonzero(np.isin(q, addrs)):
            links[(int(i) * 8, by_vt[dict(objs)[int(q[i])]])] += 1
    print(f"{len(humans)} HumanAI. Pointers from HumanAI to health objects (offset, class, count):",
          [(hex(o), c, n) for (o, c), n in links.most_common(6)])

    print(f"{len(objs)} health objects. Recording. Hit one or two zombies a few times (kill one if you can), then hold F1.", flush=True)
    rows, ts, t0 = [], [], time.time()
    while not key_down():
        row = np.full((len(objs), SPAN // 4), np.nan, dtype=np.float32)
        for k, (a, v) in enumerate(objs):
            try:
                b = p.read(a, SPAN)
            except OSError:
                continue
            if struct.unpack_from("<Q", b)[0] == v:  # else freed (a dead zombie) or reused
                row[k] = np.frombuffer(b, dtype="<f4")
        rows.append(row)
        ts.append(time.time() - t0)
        time.sleep(0.12)
    np.savez(OUT, t=np.array(ts), v=np.stack(rows), addrs=addrs,
             names=np.array([by_vt[v] for a, v in objs]))
    print(f"saved {len(ts)} samples")


def analyze():
    d = np.load(OUT)
    t, v, addrs, names = d["t"], d["v"], d["addrs"], d["names"]
    with np.errstate(invalid="ignore"):
        dv = np.diff(v, axis=0)
        drops = (dv < -0.01).sum(axis=0)        # (objects, floats)
        changes = (np.abs(dv) > 0.01).sum(axis=0)
        start = v[0]
        ok = (drops >= 1) & (changes <= 40) & (start > 0) & (start <= 1e5)
    print(f"{len(t)} samples over {t[-1]:.0f} s, {len(addrs)} objects")
    groups = Counter()
    for n, k in zip(*np.nonzero(ok)):
        groups[(str(names[n]), int(k) * 4)] += 1
    print("class + offset: objects whose float went down in steps (and changed at most 40 times)")
    for (name, off), cnt in groups.most_common(15):
        k = off // 4
        rows = [n for n in range(len(addrs)) if names[n] == name and ok[n, k]]
        best = max(rows, key=lambda n: drops[n, k])
        s = v[:, best, k]
        s = s[~np.isnan(s)]
        steps = [round(float(x), 2) for i, x in enumerate(s) if i == 0 or x != s[i - 1]]
        print(f"  {name}+{off:#x}: {cnt} objects; e.g. {int(addrs[best]):#x}: {steps[:14]}")


if __name__ == "__main__":
    if sys.argv[1:] != ["analyze"]:
        record()
    analyze()
