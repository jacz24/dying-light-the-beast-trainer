"""Step 4: the camera. Finds the game camera and turns a world position into a screen position. Read-only.

Run: python camera.py    (elevated terminal, a save loaded). Hold F1 for half a second to end.
Every half second it prints the screen position of the 3 nearest AI.
Test: put the crosshair on a zombie. Its x must be near the screen center. Its y is lower: the AI position is at the feet.
"""
import ctypes
import ctypes.wintypes as wt
import struct
import sys
import time

import numpy as np

import mem
from findptr import modules, scan
from rtti import parse_addr
from radar import AI_POS, HUMAN_VT, PLAYER_VT, alive, heap_of, humans_in, player_pos, read
from track import flat, sane
from watch import EXE, key_down

CAMERA_VT = "engine_x64_rwdi.dll+0x177daf0"  # CBaseCamera (6 objects). CRendererCamera (+0x177e120) has the same layout.
CAM_WORLD = 0x40   # 3x4 row-major camera world matrix; the eye position is its last column (+0x4c, +0x5c, +0x6c)
VIEW_PROJ = 0xc0   # 4x4 row-major view x projection: clip = M @ (x, y, z, 1). +0x10 is the view, +0x80 the projection.
EYE = 1.5          # m. The eye sat 1.5 m above the player model.


def eye(p, cam):
    r = struct.unpack("<12f", p.read(cam + CAM_WORLD, 0x30))
    return r[3], r[7], r[11]


def active_camera(p, cams, me):
    """The CBaseCamera whose eye is nearest to the player's head, or None if none is within 3 m."""
    best = min(((flat(me, e) + abs(e[1] - me[1] - EYE), c) for c in cams if alive(p, c, cams[c]) and sane(e := eye(p, c))),
               default=(99, None))
    return best[1] if best[0] < 3 else None


def find_all(p, mods):
    """One scan of all memory (about 75 s) for the player, the AI and the cameras.
    Returns ((player vt, HumanAI vt, camera vt), player or None, [HumanAI], {camera: camera vt})."""
    pvt, hvt, cvt = (parse_addr(mods, t) for t in (PLAYER_VT, HUMAN_VT, CAMERA_VT))
    found, _ = scan(p, [(pvt, pvt), (hvt, hvt), (cvt, cvt)])
    player = next((h for h, v in found if v == pvt), None)
    return (pvt, hvt, cvt), player, [h for h, v in found if v == hvt], {h: cvt for h, v in found if v == cvt}


def view_proj(p, cam):
    return np.array(struct.unpack("<16f", p.read(cam + VIEW_PROJ, 0x40)), dtype=np.float64).reshape(4, 4)


def w2s(vp, pos, width, height):
    """Screen pixel (x, y) of a world position, or None when it is behind the camera."""
    c = vp @ (pos[0], pos[1], pos[2], 1.0)
    if c[3] < 0.1:
        return None
    return (c[0] / c[3] + 1) * width / 2, (1 - c[1] / c[3]) * height / 2


def game_window(pid):
    """(window handle, client width, client height) of the game's visible window."""
    u = ctypes.WinDLL("user32")
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def each(h, _):
        owner = wt.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(owner))
        if owner.value == pid and u.IsWindowVisible(h):
            r = wt.RECT()
            u.GetClientRect(h, ctypes.byref(r))
            found.append((h, r.right, r.bottom))
        return True

    u.EnumWindows(each, 0)
    return max(found, key=lambda f: f[1] * f[2]) if found else None


# a camera at the origin that looks down -z (the game's convention): a point ahead is at the center, a point behind is None
_vp = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, -1, -0.05], [0, 0, -1, 0]], dtype=np.float64)
assert w2s(_vp, (0, 0, -10), 3440, 1440) == (1720, 720)
assert w2s(_vp, (0, 0, 10), 3440, 1440) is None
assert w2s(_vp, (10, 0, -10), 3440, 1440)[0] == 3440  # 45 degrees right is the right edge when the x scale is 1

if __name__ == "__main__":
    p = mem.Process(EXE)
    win = game_window(p.pid)
    if win is None:
        sys.exit("game window not found")
    _, W, H = win
    print(f"game window {W}x{H}. Scanning for the player, the AI and the cameras (about 75 s)...", flush=True)
    (pvt, hvt, cvt), player, humans, cams = find_all(p, modules(p))
    if player is None or not humans or not cams:
        sys.exit(f"found player={player}, {len(humans)} AI, {len(cams)} cameras. Load a save first.")
    heap = heap_of(p, humans[0])
    print(f"{len(cams)} cameras, {len(humans)} AI. Put the crosshair on a zombie. Hold F1 to end.", flush=True)
    t0, next_pick, cam = time.time(), 0, None
    while not key_down():
        t = time.time() - t0
        me = player_pos(p, player)
        if not alive(p, player, pvt) or not sane(me):
            sys.exit("the player object is gone (death, sleep or a load). Run camera.py again.")
        if t >= next_pick:
            cam, next_pick = active_camera(p, cams, me), t + 1
            humans = humans_in(p, heap, hvt)
        if cam is None:
            print(f"  {t:5.1f} s  no camera within 3 m of the player's head", flush=True)
            time.sleep(0.5)
            continue
        vp = view_proj(p, cam)
        ais = sorted((flat(me, v), v) for h in humans if sane(v := read(p, h + AI_POS)))[:3]
        cells = []
        for d, v in ais:
            s = w2s(vp, v, W, H)
            cells.append(f"{d:4.0f} m " + (f"at ({s[0]:5.0f},{s[1]:5.0f})" if s else "behind you"))
        print(f"  {t:5.1f} s  camera {cam:#x}  " + " | ".join(cells), flush=True)
        time.sleep(0.5)
