"""Step 6, teleport: F9 marks where you stand, F10 puts you back there.

Run: python teleport.py            dry run, read-only: prints the model and the source position twice a second.
     python teleport.py --write    F9 marks the position, F10 teleports to the mark. WRITES GAME MEMORY. Hold F1 to end.
The game must run (not the pause menu). The mark is a place where the player stood, so it is not inside a wall.
Chain (session 3, lane C, static): PlayerFallHelperModule +0x8 -> PlayerDI_PH +0xf0 -> +0x20 -> CBulletPhysicsCharacter
(engine_x64_rwdi.dll+0x18ae850). It holds the feet position (x, feet, z) at +0xfb8, +0xfd0, +0x1054, +0x10dc.
Session 5: a lift of the btRigidBody (+0x158, origin +0x40) did nothing: the game rewrites it. A probe lifted one copy at
a time: only +0xfd0 held. The game copied it to the other three within 4 ms and the model rose; the other three went back
within 5 ms. So +0xfd0 is the source, and a teleport writes only it.
"""
import ctypes
import math
import struct
import sys
import time

import mem
from findptr import modules
from godmode import find_module
from radar import PLAYER_VT, alive, player_pos
from rtti import parse_addr
from track import sane
from watch import EXE, key_down

BPC_VT = "engine_x64_rwdi.dll+0x18ae850"  # CBulletPhysicsCharacter
SOURCE = 0xfd0                            # in CBulletPhysicsCharacter: (x, feet, z), the copy the game follows
# Speeds in CBulletPhysicsCharacter (session 9, velfind.py and velprobe.py): +0x1328 the up speed (m/s; a write of 8 in
# the air gave a second lift of 1.70 m; on the ground the game sets it to 0 each frame); +0xfc4/+0xfcc the level speed
# (x, z; +0xfc8 always 0). The btRigidBody (+0x158) holds (x, up, z) at +0x2f0 in the same frame.
UP_SPEED, LEVEL_SPEED, BODY_PTR, BODY_SPEED = 0x1328, 0xfc4, 0x158, 0x2f0
VK_F9, VK_F10 = 0x78, 0x79
u = ctypes.windll.user32


def character(p, player, bvt):
    """The player's CBulletPhysicsCharacter, or None."""
    try:
        c = p.u64(p.u64(p.u64(player + 0x8) + 0xf0) + 0x20)
        return c if p.u64(c) == bvt else None
    except OSError:
        return None


def teleport(pw, c, pos):
    """Write (x, feet, z) into the source position (pw: a write handle). One write, so no frame sees half of it."""
    pw.write(c + SOURCE, struct.pack("<3f", *pos))


def pressed(vk):
    """True once per key press: waits for the release."""
    if not u.GetAsyncKeyState(vk) & 0x8000:
        return False
    while u.GetAsyncKeyState(vk) & 0x8000:
        time.sleep(0.01)
    return True


if __name__ == "__main__":
    write = sys.argv[1:] == ["--write"]
    p = mem.Process(EXE, write=write)
    mods = modules(p)
    pvt, bvt = parse_addr(mods, PLAYER_VT), parse_addr(mods, BPC_VT)
    player, mark, shown = None, None, 0
    while not key_down():
        if not alive(p, player, pvt):  # the start, or a death, a sleep or a load made a new player
            print("scanning for the player (about 75 s)...", flush=True)
            if (player := find_module(p, pvt)) is None:
                sys.exit("expected 1 PlayerFallHelperModule. Load a save first.")
            print(f"{'WRITE mode: F9 marks, F10 teleports to the mark' if write else 'Dry run'}. Hold F1 to end.",
                  flush=True)
        me, c = player_pos(p, player), character(p, player, bvt)
        if not sane(me) or c is None:
            time.sleep(0.5)
            continue
        src = p.vec3(c + SOURCE)
        if write and pressed(VK_F9):
            mark = src
            print(f"  F9: marked {mark[0]:.2f} {mark[1]:.2f} {mark[2]:.2f}", flush=True)
        if write and pressed(VK_F10):
            if mark is None:
                print("  F10: no mark yet. Press F9 first.", flush=True)
            else:
                d0 = math.dist(me, mark)
                teleport(p, c, mark)
                time.sleep(1.0)  # then check that the model is at the mark and stayed there
                print(f"  F10: teleported {d0:.1f} m. 1 s later the model is {math.dist(player_pos(p, player), mark):.2f} m "
                      f"from the mark", flush=True)
        if time.time() >= shown:
            print(f"  model {me[0]:8.2f} {me[1]:7.3f} {me[2]:8.2f}  |  source +{SOURCE:#x} {src[0]:8.2f} {src[1]:7.3f} "
                  f"{src[2]:8.2f}" + (f"  |  mark {math.dist(me, mark):.1f} m away" if mark else ""), flush=True)
            shown = time.time() + 0.5
        time.sleep(0.02)
