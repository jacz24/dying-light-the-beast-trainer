"""Step 3: find what points to an address, up to a pointer inside a game DLL. Read-only.

Run: python findptr.py 0x17fc96d82b0 [depth] [max-offset]    or    python findptr.py selftest
A pointer in a DLL's data section stays fixed when the game restarts. A pointer on the heap does not.
shortcut: scans writable private and image memory only (not mapped memory) and aligned 8-byte values only.
Add mapped memory or unaligned values if no chain is found.
"""
import os
import sys
from bisect import bisect_left, bisect_right
from concurrent.futures import ThreadPoolExecutor

import numpy as np

import mem
from watch import EXE

PRIVATE, IMAGE = 0x20000, 0x1000000
WRITABLE = 0x04 | 0x08 | 0x40 | 0x80  # READWRITE, WRITECOPY, EXECUTE_READWRITE, EXECUTE_WRITECOPY
CHUNK = 8 << 20
MAX_TARGETS = 3000  # per level: keeps the number of windows small
# shortcut: objects only in regions up to 128 MB. Session 6: 1663 objects of 15 classes sat in 213 regions of 9 MB or
# less plus the 64 MB AI heap; none in the 8.5 GB of larger regions (graphics and streaming buffers). Session 7: the AI
# heap grew to 80 MB in a gunfire ambush, so 64 MB skipped it; 128 MB adds 16 regions, 1.56 GB. Raise it if the AI
# count drops to 0 after a long fight, or pass max_region=None if a class is ever missing.
OBJECT_REGION_MAX = 128 << 20
THREADS = 4  # session 6: 4 threads with reused buffers copied 4.1 to 9.9 GB/s, one copy at a time 1.0 to 2.0 GB/s


def merge(ranges):
    """Join overlapping [lo, hi] ranges."""
    out = []
    for lo, hi in sorted(ranges):
        if out and lo <= out[-1][1]:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return out


def scan(p, windows, max_region=OBJECT_REGION_MAX, memo=None):
    """Aligned 8-byte values in writable private/image memory that fall inside any [lo, hi] window, in regions up to
    max_region bytes (None: all). Returns ([(holder address, value)] sorted by address, bytes that could not be read).
    Session 6: 75 s -> see NOTES; the old form read 17.75 GB one 8 MB copy at a time and searchsorted every value.
    memo (session 7): a dict the caller keeps between scans with the same windows. An empty one gives a full scan and
    fills it; later scans read only the regions of a reservation (AllocationBase) that held a hit before, plus regions
    that are new or changed size (a region is known by its base and size). memo['read'] = the bytes this scan read.
    Session 7, simulated on full-scan snapshots: this missed 0 and 18 of about 2000 objects and read 1.75 of 9.35 GB;
    the first rule, only the regions that held a hit, missed 108 and 282 (new loot goes into old regions).
    shortcut: an object in a reservation that never held a hit is missed; clear the memo for a full scan."""
    spans = merge(windows)
    los = np.array([s[0] for s in spans], dtype=np.uint64)
    his = np.array([s[1] for s in spans], dtype=np.uint64)
    lo_all, hi_all = los[0], his[-1]
    rows = [(base, size, res) for base, size, protect, kind, res in p.regions()
            if kind in (PRIVATE, IMAGE) and protect & WRITABLE and (max_region is None or size <= max_region)]
    if memo is not None:
        now, live = {r[:2] for r in rows}, {r[2] for r in rows}
        if memo:
            rows = [r for r in rows if r[2] in memo["hot"] or r[:2] not in memo["seen"]]
        memo["seen"], memo["read"] = now, sum(r[1] for r in rows)
    chunks = [(base + off, min(CHUNK, size - off)) for base, size, res in rows for off in range(0, size, CHUNK)]

    def work(part):
        buf, found, skipped = np.empty(CHUNK // 8, dtype="<u8"), [], 0
        for addr, n in part:
            if not p.read_into(addr, buf, n):
                skipped += n
                continue
            arr = buf[:n // 8]
            k = np.flatnonzero((arr >= lo_all) & (arr <= hi_all))  # cheap test first: almost every value fails it
            v = arr[k]
            i = np.searchsorted(los, v, side="right") - 1  # the last window that starts at or below the value
            ok = (i >= 0) & (v <= his[np.maximum(i, 0)])
            found += [(addr + int(j) * 8, int(x)) for j, x in zip(k[ok], v[ok])]
        return found, skipped

    with ThreadPoolExecutor(THREADS) as ex:
        parts = list(ex.map(work, [chunks[t::THREADS] for t in range(THREADS)]))
    found = sorted(f for found, _ in parts for f in found)
    if memo is not None:  # the reservations that hold a hit now; a hot reservation that is gone drops out
        bases = [r[0] for r in rows]  # rows come from p.regions(), in address order
        memo["hot"] = memo.get("hot", set()) & live | {rows[bisect_right(bases, h) - 1][2] for h, v in found}
    return found, sum(s for _, s in parts)


def chain(parent, holder):
    """Offsets from a holder down to the target. parent: holder -> (what it points near, offset)."""
    offs = []
    while holder in parent:
        holder, off = parent[holder]
        offs.append(off)
    return offs


def walk(p, start, offs):
    """Follow the chain the way a Cheat Engine pointer path does."""
    addr = start
    for off in offs:
        addr = p.u64(addr) + off
    return addr


def modules(p):
    rows = mem._walk(mem.TH32CS_SNAPMODULE | mem.TH32CS_SNAPMODULE32, p.pid, mem.MODULEENTRY32W,
                     mem.k32.Module32FirstW, mem.k32.Module32NextW)
    return [(m.modBaseAddr, m.modBaseSize, m.szModule) for m in rows]


def chase(p, target, depth, maxoff):
    mods = modules(p)
    static = lambda h: next((f"{n}+{h - b:#x}" for b, s, n in mods if b <= h < b + s), None)
    print(f"target {target:#x} now holds {tuple(round(c, 2) for c in p.vec3(target))} (x, height, z if this is the position)",
          flush=True)
    level, parent, seen = [target], {}, {target}
    for d in range(1, depth + 1):
        found, skipped = scan(p, [(t - maxoff, t) for t in level], max_region=None)
        ts = sorted(level)
        nxt, hits = [], []
        for h, v in found:
            i = bisect_left(ts, v)  # the first target at or above the value
            if i < len(ts) and ts[i] - v <= maxoff and h not in seen:
                seen.add(h)
                parent[h] = (ts[i], ts[i] - v)
                (hits if static(h) else nxt).append(h)
        print(f"depth {d}: {len(found)} pointers found, {len(hits)} inside a DLL, {len(nxt)} on the heap, "
              f"{skipped / 1e6:.0f} MB unreadable", flush=True)
        for h in hits[:15]:
            offs = chain(parent, h)
            print(f"  {static(h)}  offsets {[hex(o) for o in offs]}  ->  walk gives {walk(p, h, offs):#x}"
                  f"  {'OK' if walk(p, h, offs) == target else 'MISMATCH'}")
        if hits or not nxt:
            return hits
        level = nxt[:MAX_TARGETS]
    print("no pointer inside a DLL within the depth limit")
    return []


def selftest():
    import ctypes
    x, y = (ctypes.c_uint64 * 4)(), (ctypes.c_uint64 * 4)()
    y[2] = ctypes.addressof(x) + 8  # a pointer 8 bytes into x
    p = mem.Process(os.path.basename(sys.executable), pid=os.getpid())  # by name alone it can pick a launcher stub
    win = [(ctypes.addressof(x), ctypes.addressof(x) + 0x10)]
    found, _ = scan(p, win)
    assert (ctypes.addressof(y) + 16, ctypes.addressof(x) + 8) in found, found
    va = mem.k32.VirtualAlloc
    va.restype, va.argtypes = ctypes.c_void_p, [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_ulong, ctypes.c_ulong]
    res = va(None, 3 << 12, 0x2000, 4)  # reserve 3 pages; commit pages 0 and 2: two regions of one reservation
    first, last = (va(res + i * 4096, 4096, 0x1000, 4) for i in (0, 2))
    ctypes.c_uint64.from_address(first).value = ctypes.addressof(x)
    memo = {}
    assert (ctypes.addressof(y) + 16, ctypes.addressof(x) + 8) in scan(p, win, memo=memo)[0], "an empty memo: full scan"
    assert res in memo["hot"]
    full = memo["read"]
    ctypes.c_uint64.from_address(last).value = ctypes.addressof(x)  # an old region of a hot reservation, no hit before
    big = (ctypes.c_uint64 * (1 << 19))()  # 4 MB: a new region of its own
    big[5] = ctypes.addressof(x)
    again, _ = scan(p, win, memo=memo)
    assert (ctypes.addressof(y) + 16, ctypes.addressof(x) + 8) in again, "a hot region is read again"
    assert (last, ctypes.addressof(x)) in again, "the other regions of a hot reservation are read"
    assert (ctypes.addressof(big) + 40, ctypes.addressof(x)) in again, "a new region is read"
    assert memo["read"] < full, (memo["read"], full)
    print(f"selftest OK (rescan read {memo['read'] / 1e6:.0f} MB of {full / 1e6:.0f} MB)")


assert merge([(0, 10), (5, 20), (30, 40)]) == [[0, 20], [30, 40]]
assert chain({5: (3, 1), 3: (1, 2)}, 5) == [1, 2]

if __name__ == "__main__":
    if sys.argv[1:2] == ["selftest"]:
        selftest()
    elif len(sys.argv) >= 2:
        chase(mem.Process(EXE), int(sys.argv[1], 16),
              int(sys.argv[2]) if len(sys.argv) > 2 else 5, int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x800)
    else:
        sys.exit(__doc__)
