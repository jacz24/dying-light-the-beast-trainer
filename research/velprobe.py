"""Session 9: the velocity probe, for flying and NoClip. Which speed field does the game use?

velfind.py (read-only, 45 s of walks and jumps) found in CBulletPhysicsCharacter:
  +0x1328         the up speed (m/s), new at each game frame; gravity takes 0.185 m/s a frame (about 18.5 m/s2 at 100
                  frames a second); its x and z neighbours stay 0. +0x1300 and +0x1304 hold it one frame later.
  +0xfc4, +0xfcc  the level speed (x, z; +0xfc8 is always 0), just before the position source +0xfd0.
  btRigidBody (+0x158) +0x2f0..+0x2f8: (x, up, z), the same values in the same frame (+0x3a0: a copy); +0x3e4: -9.81 or 0.
  +0x3f8..+0x400: a copy that changes every third frame.
Run: python -m research.velprobe [up|body]           dry run, read-only: the fields 4 times a second; F12 prints what --write
                                            would write. Ends after 10 minutes, or hold F1.
     python -m research.velprobe [up|body] --write   F12 writes 8 m/s into that up-speed field once (WRITES GAME MEMORY), then
                                            prints the height for 1.5 s. Expected if it is the source: a jump of 1.7 m.
"""
import sys
import time

import mem
from findptr import modules
from godmode import find_module
from radar import PLAYER_VT
from rtti import parse_addr
from teleport import BODY_PTR, BODY_SPEED, BPC_VT, LEVEL_SPEED as WALK_SPEED, SOURCE, UP_SPEED, character, pressed
from watch import EXE, key_down

FIELDS = {"up": lambda p, c: c + UP_SPEED, "body": lambda p, c: p.u64(c + BODY_PTR) + BODY_SPEED + 4}
VK_F12, KICK = 0x7b, 8.0

if __name__ == "__main__":
    which = next((a for a in sys.argv[1:] if a in FIELDS), "up")
    write = "--write" in sys.argv
    p = mem.Process(EXE, write=write)
    mods = modules(p)
    player = find_module(p, parse_addr(mods, PLAYER_VT))
    c = character(p, player, parse_addr(mods, BPC_VT)) if player else None
    if c is None:
        sys.exit("player not found")
    body = p.u64(c + BODY_PTR)
    target = FIELDS[which](p, c)
    print(f"{time.strftime('%H:%M:%S')} ready: {'WRITE' if write else 'dry run'}, field '{which}' at {target:#x}. "
          f"F12 {'writes' if write else 'shows'} {KICK} m/s. F1 or 10 minutes ends.", flush=True)
    end, shown = time.time() + 600, 0
    while time.time() < end and not key_down():
        if pressed(VK_F12):
            before = p.f32(target)
            if not write:
                print(f"  F12 (dry run): would write {KICK} into {target:#x}, which reads {before:.2f}", flush=True)
                continue
            p.write_f32(target, KICK)
            t0, h0 = time.time(), p.f32(c + SOURCE + 4)
            print(f"  F12: wrote {KICK} into {target:#x} (it read {before:.2f}); height {h0:.2f}", flush=True)
            while (t := time.time() - t0) < 1.5:
                print(f"   +{t:4.2f} s  height {p.f32(c + SOURCE + 4) - h0:+6.2f} m  {which} {p.f32(target):6.2f}", flush=True)
                time.sleep(0.1)
        elif time.time() >= shown:
            src, walk = p.vec3(c + SOURCE), p.vec3(c + WALK_SPEED)
            print(f"  height {src[1]:7.2f}  up {p.f32(c + UP_SPEED):6.2f}  level ({walk[0]:5.2f}, {walk[2]:5.2f})  "
                  f"body ({', '.join(f'{x:5.2f}' for x in p.vec3(body + BODY_SPEED))})", flush=True)
            shown = time.time() + 0.25
        time.sleep(0.005)
