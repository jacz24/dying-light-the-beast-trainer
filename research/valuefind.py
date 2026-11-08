"""Read-only exact-value search, in steps (durability, magazine count, ...).
  python -m research.valuefind scan <value>     one pass over writable memory: floats within 1 of value and int32 == value.
  python -m research.valuefind filter <value>   keep only the places that now hold the new value. Prints the survivors when few.
Candidates are saved next to this script (valuefind.npz)."""
import os
import sys
import time

sys.path.insert(0, r"C:\dev\Github\Aimbot")
import numpy as np

import mem
from findptr import CHUNK, IMAGE, PRIVATE, WRITABLE, modules
from rtti import classes_near
from watch import EXE

SAVE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "valuefind.npz")
p = mem.Process(EXE)


def scan(v):
    F, I = [], []
    with np.errstate(all="ignore"):
        for base, size, protect, kind, res in p.regions():
            if kind not in (PRIVATE, IMAGE) or not protect & WRITABLE:
                continue
            for off in range(0, size, CHUNK):
                n = min(CHUNK, size - off)
                try:
                    raw = p.read(base + off, n)
                except OSError:
                    continue
                a0 = np.uint64(base + off)
                F.append(a0 + np.flatnonzero(np.abs(np.frombuffer(raw, "<f4") - v) <= 1).astype(np.uint64) * 4)
                I.append(a0 + np.flatnonzero(np.frombuffer(raw, "<i4") == int(v)).astype(np.uint64) * 4)
    return np.concatenate(F), np.concatenate(I)


def keep(addrs, match):
    """The addresses whose 4 bytes still pass match(float32 array, int32 array) -> bool array. Reads page by page."""
    if len(addrs) == 0:
        return addrs
    addrs = np.sort(addrs)
    pages = addrs >> np.uint64(12)
    starts = list(np.flatnonzero(np.r_[True, pages[1:] != pages[:-1]])) + [len(addrs)]
    out = []
    for s, e in zip(starts, starts[1:]):
        lo = int(pages[s]) << 12
        try:
            raw = p.read(lo, 4096)
        except OSError:
            continue
        idx = ((addrs[s:e] - np.uint64(lo)) // np.uint64(4)).astype(np.int64)
        with np.errstate(all="ignore"):
            ok = match(np.frombuffer(raw, "<f4")[idx], np.frombuffer(raw, "<i4")[idx])
        out.append(addrs[s:e][ok])
    return np.concatenate(out) if out else addrs[:0]


def show(label, addrs, fmt):
    print(f"{label}: {len(addrs)} places", flush=True)
    if len(addrs) <= 30:
        mods = modules(p)
        for a in addrs:
            a = int(a)
            near = [(h, n) for h, vt, n in classes_near(p, mods, a, 0x1000) if h <= a]
            print(f"  {a:#x}  {fmt(a)}  in {near[-1][1]} +{a - near[-1][0]:#x}" if near else f"  {a:#x}  {fmt(a)}", flush=True)


if __name__ == "__main__":
    step, v = sys.argv[1], float(sys.argv[2])
    t0 = time.time()
    if step == "scan":
        F, I = scan(v)
    else:
        d = np.load(SAVE)
        F = keep(d["F"], lambda f, i: np.abs(f - v) <= 1)
        I = keep(d["I"], lambda f, i: i == int(v))
    np.savez(SAVE, F=F, I=I)
    print(f"{step} {v:g} done in {time.time() - t0:.0f} s", flush=True)
    show("floats within 1", F, lambda a: f"{p.f32(a):.3f}")
    show("int32 equal", I, lambda a: f"{p.u32(a)}")
