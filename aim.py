"""Step 5, read-only part of the aimbot: how far the crosshair is from the nearest living AI's head (the head bone,
head.py), as yaw and pitch.

Run: python aim.py    (elevated terminal, a save loaded). Prints twice a second. Hold F1 to end. No writes, no input.
     python aim.py --write    also: each F11 press turns the view once onto the nearest head, then prints the
                              angles and the error 0.3 s later. WRITES GAME MEMORY (the view angles). Session 6: the
                              app (overlay.py) does the same each frame while F11 is held (hold to track).
The view comes from the active camera (camera.py). The game's own view angles (session 3, static match, game paused):
LookController +0x6c yaw and +0x70 pitch, in degrees (a copy at +0x74 / +0x78; also PlayerDI_PH +0xbb0 / +0xbb4).
They read (-89.375, -50.5) while the camera gave (-89.38, -50.50) with the formulas in view().
Session 5, round 1: a write to +0x6c/+0x70 alone held on 6 presses and went back on 7. A probe (writes, sampled many
times a frame) showed why: each frame the game rebuilds +0x6c from +0x74, and copies +0x6c to +0x74 later in the frame;
a write held only when it landed between the two (2 of 6 in the probe). PlayerDI_PH +0xbb0 is a wrapped read-only copy.
So turn() writes both pairs (+0x6c..+0x78) in one write. The yaw is not wrapped by the game (-453.75 seen).
"""
import ctypes
import math
import struct
import sys
import time

import mem
from camera import CAM_WORLD, CAMERA_VT, active_camera
from findptr import modules, scan
from head import head_pos
from radar import (AI_POS, HEALTH_VT, HUMAN_VT, PLAYER_VT, alive, health, health_element, health_module, heap_of,
                   humans_in, in_world, player_pos, read)
from rtti import parse_addr
from track import flat, sane
from watch import EXE, key_down

HEAD = 1.6      # m above the feet: only a fallback when head.py finds no head bone
MAX_DIST = 60   # m, ground distance
LOOK_VT = "gamedll_ph_x64_rwdi.dll+0x2995548"  # LookController: 1 object; no global or PlayerDI_PH pointer to it (session 5)
LOOK_YAW, LOOK_PITCH = 0x6c, 0x70              # degrees; +0x74/+0x78 = the copy the game rebuilds them from
PDI_VIEW = 0xbb0  # PlayerDI_PH: wrapped yaw, pitch, yaw, pitch. Session 5: an exact-value search over all memory, with
                  # three turns, kept only 3 yaw places: LookController +0x6c, +0x74 and PlayerDI_PH +0xbb8
PITCH_LIMIT = 85.0  # the game's own limit is not known; stay inside it
VK_F11 = 0x7a


def view(m):
    """(eye, yaw, pitch) in degrees, in the game's convention, from a 3x4 row-major camera world matrix (12 floats).
    The camera looks down its -z axis. Yaw = atan2(forward z, forward x); it grows when the view turns right."""
    f = (-m[2], -m[6], -m[10])
    return (m[3], m[7], m[11]), math.degrees(math.atan2(f[2], f[0])), math.degrees(math.asin(max(-1.0, min(1.0, f[1]))))


def angles(eye, target):
    """(yaw, pitch) in degrees of the line from eye to target, in the game's convention (see view())."""
    d = [t - e for t, e in zip(target, eye)]
    return math.degrees(math.atan2(d[2], d[0])), math.degrees(math.atan2(d[1], math.hypot(d[0], d[2])))


def aim_error(m, target):
    """(yaw error, pitch error) in degrees from the crosshair to target. + yaw = turn right, + pitch = look up."""
    eye, yaw, pitch = view(m)
    ty, tp = angles(eye, target)
    return (ty - yaw + 180) % 360 - 180, tp - pitch


def living_head(p, me, a, hvt, hmvt):
    """(distance, head position) of a living AI within MAX_DIST, or None (freed, parked, dead, too far)."""
    if not alive(p, a, hvt) or not in_world(p, a) or not sane(v := read(p, a + AI_POS)) or (d := flat(me, v)) > MAX_DIST:
        return None
    if not ((hm := health_module(p, a, hmvt)) and (el := health_element(p, hm)) and (hp := health(p, el)) and hp[0] > 0):
        return None
    return d, head_pos(p, a) or (v[0], v[1] + HEAD, v[2])


def nearest(p, me, m, humans, hvt, hmvt):
    """(distance, (yaw error, pitch error), AI, head) for the nearest living AI within MAX_DIST in front of the camera,
    or None. The user's choice (session 6): nearest in distance, zombies and humans, no angle limit."""
    best = None
    for a in humans:
        if (t := living_head(p, me, a, hvt, hmvt)) and abs((err := aim_error(m, t[1]))[0]) < 90 and (
                best is None or t[0] < best[0]):
            best = (t[0], err, a, t[1])
    return best


def aimed(yaw, ang):
    """The view angles that look along ang (target yaw, pitch), from the game's yaw now: the yaw stays in the game's
    unwrapped range (the nearest turn), the pitch within PITCH_LIMIT. Absolute angles, not yaw + error: the camera can
    lag the LookController by a frame, and an error from a stale camera would be added twice when it runs each frame."""
    return yaw + (ang[0] - yaw + 180) % 360 - 180, max(-PITCH_LIMIT, min(PITCH_LIMIT, ang[1]))


def turn(pw, look, pdi, ang):
    """Write the view angles for ang into every copy (pw: a write handle; pdi: the PlayerDI_PH). Round 2 wrote only the
    LookController: in some game states every write went back to the old unwrapped yaw, the value in PlayerDI_PH +0xbb8."""
    yaw, pitch = aimed(pw.f32(look + LOOK_YAW), ang)
    pw.write(pdi + PDI_VIEW, struct.pack("<4f", (yaw + 180) % 360 - 180, pitch, yaw, pitch))
    pw.write(look + LOOK_YAW, struct.pack("<4f", yaw, pitch, yaw, pitch))
    return yaw, pitch


assert aimed(-89.375, (-79.375, -45.5)) == (-79.375, -45.5)
assert aimed(-453.75, (-113.75, 0))[0] == -473.75 and aimed(0, (0, 110))[1] == PITCH_LIMIT  # no wrap; pitch limit

# a camera at the origin that looks down +x (right is +z, up is +y), the game's right-handed layout
_m = (0, 0, -1, 0, 0, 1, 0, 0, 1, 0, 0, 0)
assert view(_m)[1:] == (0.0, 0.0)
assert all(abs(a - b) < 1e-9 for a, b in zip(aim_error(_m, (10, 0, 10)), (45, 0)))   # ahead and to the right
assert all(abs(a - b) < 1e-9 for a, b in zip(aim_error(_m, (10, 10, 0)), (0, 45)))   # ahead and up
assert abs(aim_error(_m, (-10, 0, 0))[0]) == 180                                      # behind
assert all(abs(a - b) < 1e-9 for a, b in zip(angles((1, 2, 3), (11, 12, 13)), (45, math.degrees(math.atan2(10, 200 ** 0.5)))))

if __name__ == "__main__":
    write = sys.argv[1:] == ["--write"]
    p = mem.Process(EXE, write=write)
    mods = modules(p)
    pvt, hvt, cvt, lvt = (parse_addr(mods, t) for t in (PLAYER_VT, HUMAN_VT, CAMERA_VT, LOOK_VT))
    print("scanning for the player, the AI, the cameras and the LookController (about 75 s)...", flush=True)
    found, _ = scan(p, [(v, v) for v in (pvt, hvt, cvt, lvt)])
    player, look = (next((h for h, v in found if v == t), None) for t in (pvt, lvt))
    humans, cams = [h for h, v in found if v == hvt], {h: cvt for h, v in found if v == cvt}
    if player is None or look is None or not humans or not cams:
        sys.exit(f"found player={player}, LookController={look}, {len(humans)} AI, {len(cams)} cameras. Load a save first.")
    heap, hmvt = heap_of(p, humans[0]), parse_addr(mods, HEALTH_VT)
    print(f"aim {'WRITE mode: press F11 to turn onto the nearest head' if write else 'dry run'} on. Hold F1 to end.",
          flush=True)
    shown = 0
    while not key_down():
        press = write and ctypes.windll.user32.GetAsyncKeyState(VK_F11) & 0x8000
        if not press and time.time() < shown:
            time.sleep(0.02)
            continue
        me = player_pos(p, player)
        if not alive(p, player, pvt) or not alive(p, look, lvt) or not sane(me):
            sys.exit("the player object is gone (death, sleep or a load). Run aim.py again.")
        cam = active_camera(p, cams, me)
        m = struct.unpack("<12f", p.read(cam + CAM_WORLD, 0x30)) if cam else None
        t = nearest(p, me, m, humans_in(p, heap, hvt), hvt, hmvt) if m else None
        if press and t:
            before = (p.f32(look + LOOK_YAW), p.f32(look + LOOK_PITCH))
            wrote = turn(p, look, p.u64(player + 0x8), angles(view(m)[0], t[3]))  # PlayerFallHelperModule +0x8 = PlayerDI_PH
            time.sleep(0.3)  # then check whether the game kept the angles and the camera followed
            t2 = nearest(p, me, struct.unpack("<12f", p.read(cam + CAM_WORLD, 0x30)), humans_in(p, heap, hvt), hvt, hmvt)
            print(f"  F11: LookController {before[0]:.2f}/{before[1]:.2f} -> wrote {wrote[0]:.2f}/{wrote[1]:.2f}, "
                  f"0.3 s later {p.f32(look + LOOK_YAW):.2f}/{p.f32(look + LOOK_PITCH):.2f}; error "
                  + (f"{t2[1][0]:+.2f} right, {t2[1][1]:+.2f} up" if t2 else "none (no target)"), flush=True)
            while ctypes.windll.user32.GetAsyncKeyState(VK_F11) & 0x8000:
                time.sleep(0.01)
        if time.time() >= shown:
            if m is None:
                print("  no camera within 3 m of the player's head", flush=True)
            else:
                _, yaw, pitch = view(m)
                print(f"  view yaw {yaw:8.2f} pitch {pitch:6.2f}  |  " + (
                    f"nearest AI {t[0]:4.1f} m: turn {t[1][0]:+7.2f} deg right, {t[1][1]:+6.2f} deg up" if t
                    else f"no living AI within {MAX_DIST} m in front"), flush=True)
            shown = time.time() + 0.5
        time.sleep(0.02)  # F11 held with no target: do not spin
