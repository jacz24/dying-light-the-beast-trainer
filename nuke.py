"""Step 7: the nuke. Sets the health of every HumanAI within RADIUS of the player to 0.

Run: python nuke.py            dry run, read-only: lists what a nuke would hit, then ends
     python nuke.py --write    hold F7 to nuke (each press once), hold F1 to end. WRITES GAME MEMORY.
The user allowed game memory writes on 2026-11-03, after a dry run. Back up the save first:
HumanAI also covers human NPCs, and a dead quest NPC can block a quest. Session 6 (the user's choice): the nuke hits
zombies and hostile humans (bandits, Baron's soldiers); it skips friendly NPCs (aikind.NPC) and AI with an unreadable
type. Sessions 3 to 5 it hit zombie types only.
"""
import ctypes
import sys
import time

import mem
from aikind import NPC, is_zombie, kind
from findptr import modules
from radar import (EL_CUR, HEALTH, HEALTH_VT, HUMAN_VT, PLAYER_VT, AI_POS, alive, find_objects, health,
                   health_element, health_module, heap_of, humans_in, in_world, player_pos, read)
from rtti import parse_addr
from track import flat, sane
from watch import EXE, key_down

RADIUS = 50  # m, ground distance
VK_F7 = 0x76


def targets(p, me, humans, hvt, hmvt):
    """[(distance, health module, health element, (current, maximum))] for each living enemy within RADIUS."""
    out = []
    for a in humans:
        if not alive(p, a, hvt) or not in_world(p, a) or not sane(v := read(p, a + AI_POS)) or (d := flat(me, v)) > RADIUS:
            continue
        if is_zombie(k := kind(p, a)) is None or k == NPC:
            continue  # a friendly NPC (trader, quest giver) or an unreadable type
        if (hm := health_module(p, a, hmvt)) and (el := health_element(p, hm)) and (hp := health(p, el)) and hp[0] > 0:
            out.append((d, hm, el, hp))
    return sorted(out)


def fire(pw, ts):
    """Set the real health of each target to 0 (pw: a write handle). The game then kills the AI by itself (session 2)."""
    for d, hm, el, hp in ts:
        for off in EL_CUR:
            pw.write_f32(el + off, 0.0)
        pw.write_f32(hm + HEALTH, 0.0)  # the display copy, so it shows 0 at once


def f7_down():
    return bool(ctypes.windll.user32.GetAsyncKeyState(VK_F7) & 0x8000)


if __name__ == "__main__":
    write = sys.argv[1:] == ["--write"]
    p = mem.Process(EXE, write=write)
    mods = modules(p)
    pvt, hvt, hmvt = (parse_addr(mods, t) for t in (PLAYER_VT, HUMAN_VT, HEALTH_VT))
    print("scanning for the player and the AI (about 75 s)...", flush=True)
    player, humans = find_objects(p, pvt, hvt)
    if player is None or not humans:
        sys.exit("player or AI not found. Load a save first.")
    heap = heap_of(p, humans[0])
    if not write:
        ts = targets(p, player_pos(p, player), humans_in(p, heap, hvt), hvt, hmvt)
        print(f"dry run: a nuke now would hit {len(ts)} AI within {RADIUS} m:")
        for d, hm, el, (cur, mx) in ts:
            print(f"  {d:5.1f} m  health {cur:7.1f} / {mx:7.1f}")
        sys.exit()
    print(f"nuke armed: hold F7 to set the health of every zombie within {RADIUS} m to 0. Hold F1 to end.", flush=True)
    while not key_down():
        if not alive(p, player, pvt):
            print("  the player object is gone. Rescanning, about 75 s...", flush=True)
            player, found = find_objects(p, pvt, hvt)
            heap = heap_of(p, found[0]) if found else heap
            continue
        if f7_down():
            me = player_pos(p, player)
            ts = targets(p, me, humans_in(p, heap, hvt), hvt, hmvt) if sane(me) else []
            fire(p, ts)
            time.sleep(1)  # then check whether the game kept the 0 or put the health back
            left = sum(1 for d, hm, el, hp in ts if (h := health(p, el)) and h[0] > 0)
            print(f"  nuke: wrote 0 to {len(ts)} AI; after 1 s, {left} have health above 0 again", flush=True)
            while f7_down():
                time.sleep(0.01)
        time.sleep(0.02)
