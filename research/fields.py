"""Step 3: find which field of a class holds a world position, by testing every instance. Read-only.

Run: python -m research.fields 0x17fc96d82b0 cbs::CEntity 0x140 [radius]     (needs instances.json from rtti.py)
For each 4-byte offset, count the instances whose three floats there (x, height, z) lie near the player.
The player position is read live from the first address. Height must be within 100, x and z within `radius`.
"""
import json
import sys

import numpy as np

import mem
from watch import EXE


def best_offsets(arr, ref, radius, rise=100.0):
    """arr: (instances, floats). Returns [(byte offset, count)] for offsets where some instance holds a nearby vec3."""
    ok = ((np.abs(arr[:, :-2] - ref[0]) < radius) & (np.abs(arr[:, 1:-1] - ref[1]) < rise)
          & (np.abs(arr[:, 2:] - ref[2]) < radius))
    counts = ok.sum(axis=0)
    return [(int(k) * 4, int(counts[k])) for k in np.argsort(-counts)[:6] if counts[k]]


a = np.array([[0, 1, 2, 3, 99.0], [0, 1, 2, 3, 98.0]], dtype=np.float32)
assert best_offsets(a, (1, 2, 3), 0.5) == [(4, 2)]

if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    p = mem.Process(EXE)
    ref = p.vec3(int(sys.argv[1], 16))
    name, size = sys.argv[2], int(sys.argv[3], 16)
    radius = float(sys.argv[4]) if len(sys.argv) > 4 else 300.0
    insts = json.load(open("instances.json"))[name]
    arr = np.zeros((len(insts), size // 4), dtype=np.float32)
    for i, addr in enumerate(insts):
        try:
            arr[i] = np.frombuffer(p.read(addr, size), dtype="<f4")
        except OSError:
            pass  # stays zero
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    print(f"{name}: {len(insts)} instances, player at {tuple(round(c, 2) for c in ref)}, radius {radius}")
    for off, count in best_offsets(arr, ref, radius):
        rows = np.flatnonzero((np.abs(arr[:, off // 4] - ref[0]) < radius) & (np.abs(arr[:, off // 4 + 2] - ref[2]) < radius))
        sample = [tuple(round(float(c), 1) for c in arr[r, off // 4:off // 4 + 3]) for r in rows[:4]]
        print(f"  offset {off:#x}: {count} of {len(insts)} near the player, e.g. {sample}")
