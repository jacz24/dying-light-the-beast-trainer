"""Step 3: walk the graph of named C++ objects from a start object and report fields that hold a position. Read-only.

Run: python -m research.graph 0x17fcabbc150 0x17fc96d82b0 [depth] [bytes]
  start      object to begin at
  position   address of a known x, height, z: its live value is the reference
A field counts when three floats in a row are within 2 of the reference.
"""
import struct
import sys
from collections import deque

import mem
from findptr import modules
from rtti import vtable_name
from watch import EXE


def near_pos(data, ref, tol=2.0):
    """[(offset, floats)] where three consecutive floats lie within tol of ref."""
    fl = struct.unpack(f"<{len(data) // 4}f", data[:len(data) // 4 * 4])
    return [(i * 4, fl[i:i + 3]) for i in range(len(fl) - 2)
            if all(abs(fl[i + k] - ref[k]) <= tol for k in range(3))]


def walk(p, mods, start, ref, depth, size):
    """Breadth first over objects whose first qword is a known vtable. Returns (visited, hits)."""
    seen, parent, queue, hits = {start}, {}, deque([(start, 0)]), []
    names = {}

    def path(o):
        steps = []
        while o in parent:
            o, off = parent[o]
            steps.append(f"{names.get(o, '?')}+{off:#x}")
        return " -> ".join(reversed(steps)) or "(start)"

    while queue:
        obj, d = queue.popleft()
        for n in (size, 0x400, 0x100):  # shortcut: falls back to a smaller read when the full read crosses a gap
            try:
                data = p.read(obj, n)
                break
            except OSError:
                data = None
        if data is None:
            continue
        names[obj] = vtable_name(p, mods, struct.unpack_from("<Q", data)[0]) or "?"
        hits += [(obj, off, fl) for off, fl in near_pos(data, ref)]
        if d == depth:
            continue
        for i, (v,) in enumerate(struct.iter_unpack("<Q", data[:len(data) // 8 * 8])):
            if v in seen or not 0x10000 < v < 1 << 47:
                continue
            try:
                head = p.u64(v)
            except OSError:
                continue
            if head > 0x10000 and vtable_name(p, mods, head):
                seen.add(v)
                parent[v] = (obj, i * 8)
                queue.append((v, d + 1))
    return names, hits, path


assert near_pos(struct.pack("<5f", 0, 10.0, 20.0, 30.0, 0), (10.5, 20.5, 30.5)) == [(4, (10.0, 20.0, 30.0))]

if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    p = mem.Process(EXE)
    mods = modules(p)
    ref = p.vec3(int(sys.argv[2], 16))
    print(f"reference position {tuple(round(c, 2) for c in ref)}")
    names, hits, path = walk(p, mods, int(sys.argv[1], 16), ref,
                             int(sys.argv[3]) if len(sys.argv) > 3 else 3,
                             int(sys.argv[4], 16) if len(sys.argv) > 4 else 0x2000)
    ref = p.vec3(int(sys.argv[2], 16))  # read again: the player may have moved during the walk
    gap = lambda fl: max(abs(fl[k] - ref[k]) for k in range(3))
    hits.sort(key=lambda h: gap(h[2]))
    print(f"{len(names)} named objects visited. {len(hits)} position-like fields. Reference now {tuple(round(c, 2) for c in ref)}")
    print("closest to the reference:")
    for obj, off, fl in hits[:20]:
        print(f"  gap {gap(fl):5.2f}  {names[obj]} at {obj:#x} +{off:#x}  {tuple(round(c, 2) for c in fl)}   via {path(obj)}")
    print("\nall hits by class:")
    for name in sorted({names[h[0]] for h in hits}):
        mine = [h for h in hits if names[h[0]] == name]
        print(f"  {len(mine):3}  {name}  best gap {min(gap(h[2]) for h in mine):.2f}  offsets {sorted({h[1] for h in mine})[:8]}")
