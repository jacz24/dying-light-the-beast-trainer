"""Step 3: name the C++ objects that live near an address, from the class names (RTTI) in the game DLLs. Read-only.

Run: python rtti.py 0x17fc96d82b0 [span]
Every object starts with a pointer to its class's vtable. The 8 bytes before a vtable point to a Complete
Object Locator, and that points to the class name. This reads that chain for every pointer near the address.
"""
import json
import re
import struct
import sys
from collections import Counter, defaultdict

import numpy as np

import mem
from findptr import modules, scan
from watch import EXE


def demangle(raw):
    """'.?AVCEntity@cbs@@' -> 'cbs::CEntity'. Template names are left as they are."""
    s = raw[4:-2] if raw.endswith("@@") else raw[4:]
    return raw if s.startswith("?") else "::".join(reversed(s.split("@")))


def vtable_name(p, mods, v):
    """Class name if v is a vtable address, else None."""
    def module(x):
        return next(((b, s) for b, s, n in mods if b <= x < b + s), None)

    if module(v) is None:
        return None
    try:
        col = p.u64(v - 8)
        m = module(col)
        if m is None:
            return None
        sig, _, _, td, _, self_rva = struct.unpack("<6I", p.read(col, 24))
        if sig != 1 or col != m[0] + self_rva:  # a real locator has signature 1 and knows its own address
            return None
        raw = p.read(m[0] + td + 16, 200).split(b"\0")[0].decode("ascii", "replace")  # shortcut: names over 200 bytes fail
    except OSError:
        return None
    return demangle(raw) if raw.startswith(".?A") else None


def classes_near(p, mods, addr, span):
    """[(address, vtable, class name)] for each aligned pointer within `span` bytes of addr that is a vtable."""
    out = []
    for base, size, protect, kind, res in p.regions():
        lo, hi = max(base, (addr - span) & ~7), min(base + size, addr + span)
        if lo >= hi:
            continue
        try:
            data = p.read(lo, (hi - lo) & ~7)
        except OSError:
            continue
        for i, (v,) in enumerate(struct.iter_unpack("<Q", data)):
            name = vtable_name(p, mods, v) if v > 0x10000 else None
            if name:
                out.append((lo + i * 8, v, name))
    return out


def image(p, base, size):
    """A module as one flat buffer, so that an offset in it is an RVA. Unreadable gaps stay zero."""
    buf = bytearray(size)
    for rb, rs, protect, kind, res in p.regions():
        lo, hi = max(rb, base), min(rb + rs, base + size)
        for off in range(lo, hi, 8 << 20):
            n = min(8 << 20, hi - off)
            try:
                buf[off - base:off - base + n] = p.read(off, n)
            except OSError:
                pass
    return bytes(buf)


def find_vtables(p, mods, wanted):
    """{class name: [primary vtable address]} for the wanted class names (as demangle() writes them).
    Chain: type name string -> type descriptor -> locator that names it -> the vtable slot that holds the locator."""
    found = defaultdict(list)
    for base, size, mod in mods:
        if not mod.lower().endswith("_rwdi.dll"):  # shortcut: game modules only
            continue
        img = image(p, base, size)
        td = {m.start() - 16: demangle(m.group(0)[:-1].decode())  # the descriptor starts 16 bytes before its name
              for m in re.finditer(rb"\.\?A[VU][A-Za-z0-9_@$?]+?@@\x00", img)
              if demangle(m.group(0)[:-1].decode()) in wanted}
        if not td:
            continue
        u32 = np.frombuffer(img[:size // 4 * 4], dtype="<u4")
        cols = {}  # locator address -> class name. Locator: signature 1, offset 0, cdOffset, td, class desc, self (all RVAs)
        for i in np.flatnonzero(np.isin(u32, list(td))):
            if 3 <= i < len(u32) - 2 and u32[i - 3] == 1 and u32[i - 2] == 0 and u32[i + 2] == (i - 3) * 4:
                cols[base + (i - 3) * 4] = td[int(u32[i])]
        if not cols:
            continue
        u64 = np.frombuffer(img[:size // 8 * 8], dtype="<u8")
        for j in np.flatnonzero(np.isin(u64, list(cols))):
            found[cols[int(u64[j])]].append(base + (int(j) + 1) * 8)
    return dict(found)


FOUND = {}  # session 8: 'module.dll+0x...' vtable constant -> its class's vtable in the running build (resolve_vtables)


def resolve_vtables(p, mods, classes):
    """Session 8, version safety. classes: {'module.dll+0x...' vtable constant: class name}. A constant whose address
    still names its class is kept (no cost). The others are found by class name (find_vtables(), 8.5 s), so a game
    update that moves a vtable costs one slow start, never a scan for the wrong class; parse_addr() then gives the found
    address. Raises if a moved class is found 0 or 2+ times. Returns {constant: class name} of the moved ones."""
    moved = {c: n for c, n in classes.items() if vtable_name(p, mods, parse_addr(mods, c)) != n}
    vts = find_vtables(p, mods, set(moved.values())) if moved else {}
    if bad := [n for n in moved.values() if len(vts.get(n, [])) != 1]:
        raise RuntimeError(f"not found once by class name in this game build: {bad}")
    FOUND.update((c, vts[n][0]) for c, n in moved.items())
    return moved


def parse_addr(mods, text):
    """'0x7ff...' or 'module.dll+0x1234' -> absolute address. The module form survives a game restart; a vtable that
    resolve_vtables() found by class name wins over its constant."""
    if text in FOUND:
        return FOUND[text]
    if "+" not in text:
        return int(text, 16)
    name, off = text.rsplit("+", 1)
    return next(b for b, s, n in mods if n.lower() == name.lower()) + int(off, 16)


def owners(p, mods, vtable, maxoff=0x40):
    """Find every object that starts with this vtable, then every pointer to those objects.
    Each pointer is matched to the named object that sits just below it."""
    insts = [h for h, v in scan(p, [(vtable, vtable)])[0]]
    print(f"{len(insts)} objects start with this vtable: {[hex(i) for i in insts[:10]]}", flush=True)
    if not insts:
        return
    for h, v in scan(p, [(i - maxoff, i) for i in insts])[0]:
        below = [c for c in classes_near(p, mods, h, 0x2000) if c[0] <= h]
        where = next((f"{n}+{h - b:#x}" for b, s, n in mods if b <= h < b + s), "heap")
        owner = max(below)[::2] if below else None  # (address, class name) of the nearest named object below
        print(f"  pointer at {h:#x} ({where}) -> object {v:#x}"
              + (f"; sits {h - owner[0]:#x} bytes into {owner[1]}" if owner else "; no named object nearby"))


assert demangle(".?AVCEntity@cbs@@") == "cbs::CEntity"
assert demangle(".?AV?$Foo@H@@") == ".?AV?$Foo@H@@"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == "instances":  # python rtti.py instances CLevel cbs::CEntity ...  (saves instances.json)
        p = mem.Process(EXE)
        mods = modules(p)
        vts = find_vtables(p, mods, set(sys.argv[2:]))
        for name in sys.argv[2:]:
            print(f"{name}: vtables {[next(f'{n}+{v - b:#x}' for b, s, n in mods if b <= v < b + s) for v in vts.get(name, [])]}")
        by_vt = {v: name for name, vs in vts.items() for v in vs}
        found, skipped = scan(p, [(v, v) for v in by_vt])
        result = defaultdict(list)
        for holder, v in found:
            result[by_vt[v]].append(holder)
        json.dump(result, open("instances.json", "w"))
        print(f"\n{len(found)} objects found ({skipped / 1e6:.0f} MB unreadable). Saved instances.json")
        for name in sys.argv[2:]:
            xs = result.get(name, [])
            print(f"  {len(xs):6}  {name}  {[hex(x) for x in xs[:4]]}")
        sys.exit()
    if sys.argv[1] == "owners":  # python rtti.py owners gamedll_ph_x64_rwdi.dll+0x2996e10
        p = mem.Process(EXE)
        mods = modules(p)
        owners(p, mods, parse_addr(mods, sys.argv[2]))
        sys.exit()
    addr = int(sys.argv[1], 16)
    span = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x10000
    p = mem.Process(EXE)
    mods = modules(p)
    found = classes_near(p, mods, addr, span)
    print(f"{len(found)} objects with a class name within {span:#x} bytes of {addr:#x}")
    for ad, v, name in found[:60]:
        mod = next(f"{n}+{v - b:#x}" for b, s, n in mods if b <= v < b + s)
        print(f"  {ad:#x} ({ad - addr:+#x})  {name}  vtable {mod}")
    print("\nmost common classes:")
    for name, n in Counter(f[2] for f in found).most_common(15):
        print(f"  {n:4}  {name}")
