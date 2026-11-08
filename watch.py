"""Step 2: find the player position among the Cheat Engine candidates. Read-only.

Capture: python watch.py capture candidates2.CT run1.pkl   (hold F1 for half a second, 6 presses)
Analyse: python watch.py analyse run1.pkl                  (offline: no game needed, repeat at will)
  phase 1  climb a ledge and drop, again and again
  phase 2  walk straight on open ground
  phase 3  stand still and spin the camera
The raw readings are saved, so a new idea for a filter needs no new run in the game.
"""
import ctypes
import math
import pickle
import re
import sys
import time
from collections import defaultdict

from mem import Process

EXE = "DyingLightGame_TheBeast_x64_rwdi.exe"
VK_F1 = 0x70  # the quit key of every script (F8 until session 5: it sat next to the nuke key F7)
user32 = ctypes.WinDLL("user32")
# Offsets of the two flat axes from the vertical float. Floats side by side, or a column-major 3x4 matrix (16 bytes apart).
LAYOUTS = {"z-up": (-8, -4), "y-up": (-4, 4), "z-up-col": (-32, -16), "y-up-col": (-16, 16)}
OFFSETS = sorted({0, *(d for offs in LAYOUTS.values() for d in offs)})


def key_down():
    return bool(user32.GetAsyncKeyState(VK_F1) & 0x8000)


def wait_key():
    """Block until F1 is pressed, then until it is released."""
    while not key_down():
        time.sleep(0.01)
    while key_down():
        time.sleep(0.01)


def load(path):
    """Addresses from a Cheat Engine .CT file."""
    return [int(a, 16) for a in re.findall(r"<Address>([0-9A-Fa-f]+)</Address>", open(path).read())]


def finite(vals):
    """Drop NaN, inf, and values too big to be a position."""
    return [v for v in vals if math.isfinite(v) and abs(v) < 1e6]


def span(vals):
    """max - min of the readings; infinite when no reading is usable."""
    v = finite(vals)
    return max(v) - min(v) if v else math.inf


def moves_straight(vals, need=3.0):
    """True when the readings travelled at least `need` in one direction.
    Net change close to the total range: a swinging value (animation) fails, a walk passes."""
    v = finite(vals)
    return len(v) > 1 and span(v) >= need and abs(v[-1] - v[0]) >= 0.8 * span(v)


def record(p, addrs):
    """Read every address about 10 times a second until F1 is pressed."""
    series, t0, sweeps = defaultdict(list), time.time(), 0
    while not key_down():
        for a in addrs:
            try:
                series[a].append(p.f32(a))
            except OSError:
                pass
        sweeps += 1
        nxt = time.time() + 0.1
        while time.time() < nxt and not key_down():  # poll the key so a short press is not missed
            time.sleep(0.01)
    while key_down():
        time.sleep(0.01)
    print(f"  phase ended: {sweeps} sweeps in {time.time() - t0:.1f} s", flush=True)
    return dict(series)


def find_positions(up, s2, s3, need=3.0, still=0.02):
    """A vec3 fits when, in the walk phase, at least one flat axis travelled `need` in one direction,
    and in the camera phase all three axes stayed within `still`.
    `up` holds the address of the vertical float. LAYOUTS lists where the flat axes sit."""
    hits = []
    for a in up:
        for name, offs in LAYOUTS.items():
            flat = [a + d for d in offs]
            if any(moves_straight(s2.get(x, []), need) for x in flat) and \
                    all(span(s3.get(x, [])) <= still for x in (*flat, a)):
                hits.append((name, a))
    return hits


def capture(table, out):
    p = Process(EXE)
    addrs = load(table)
    print(f"{len(addrs)} addresses. PRESS 1: start phase 1 (climb a ledge, drop, repeat).", flush=True)
    wait_key()
    print("phase 1 recording. PRESS 2 ends it.", flush=True)
    s1 = record(p, addrs)
    up = [a for a, v in s1.items() if span(v) > 0.1]  # the float moved when the height changed
    cells = sorted({a + d for a in up for d in OFFSETS})
    print(f"{len(up)} moved with height. Go to open ground. PRESS 3 starts phase 2 (walk straight).", flush=True)
    wait_key()
    print("phase 2 recording. PRESS 4 ends it.", flush=True)
    s2 = record(p, cells)
    print("PRESS 5 starts phase 3 (stand still, spin the camera).", flush=True)
    wait_key()
    print("phase 3 recording. PRESS 6 ends it.", flush=True)
    s3 = record(p, cells)
    pickle.dump({"s1": s1, "s2": s2, "s3": s3}, open(out, "wb"))
    print(f"saved {out}", flush=True)


def ends(vals):
    v = finite(vals)
    return (round(v[0], 1), round(v[-1], 1)) if v else None


def analyse(path):
    d = pickle.load(open(path, "rb"))
    s1, s2, s3 = d["s1"], d["s2"], d["s3"]
    up = [a for a, v in s1.items() if span(v) > 0.1]
    hits = find_positions(up, s2, s3)
    groups = defaultdict(list)  # copies of one value share one entry
    for name, a in hits:
        v1 = finite(s1[a])
        key = (name, tuple(ends(s2.get(a + o, [])) for o in LAYOUTS[name]), (round(min(v1), 1), round(max(v1), 1)))
        groups[key].append(a)
    print(f"{len(up)} moved with height. {len(hits)} fit a position, {len(groups)} different values.")
    for (name, flat, vert), found in sorted(groups.items(), key=lambda g: -len(g[1]))[:30]:
        print(f"  {name}  flat axes start->end {flat}  height range {vert}  x{len(found)}  first at {found[0]:#x}")


assert span([1.0, 3.0, 2.0, float("nan")]) == 2.0 and span([float("nan")]) == math.inf
assert moves_straight([0, 1, 2, 3, 4]) and not moves_straight([0, 3, 0, 3, 0]) and not moves_straight([1, 1.1, 1])
assert find_positions([100], {92: [0, 2, 4, 6], 96: [1, 1, 1, 1]}, {92: [5, 5], 96: [5, 5], 100: [5, 5]}) == [("z-up", 100)]

if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "capture":
        capture(sys.argv[2], sys.argv[3])
        analyse(sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == "analyse":
        analyse(sys.argv[2])
    else:
        sys.exit(__doc__)
