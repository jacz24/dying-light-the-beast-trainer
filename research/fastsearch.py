"""Step 7, instant loot search, first test: set the search time of the unsearched 'search' containers near you to 0.

Run: python -m research.fastsearch            dry run, read-only: lists the 'search' containers within 10 m, then ends.
     python -m research.fastsearch --write    writes 0.0 to the search time of each unsearched one. WRITES GAME MEMORY.
                                     Then it watches them for 10 minutes: search one in the game.
Session 5, round 1: the user searched another container than the one prepared, so the test did not occur. It did show
the state live: the searched container went 1 -> 5 and its items 1 -> 0. The prepared one kept 0.0 for 10 minutes.
Session 3 (lane C, static): Container +0x1f8 = search time in seconds (1.0, a copy of +0x57c), +0x508 kind
(1 = hold the key), +0x388 state (5 = searched). The game's function at gamedll+0x10B3470 returns +0x1f8.
Expected: the search ends at once and the state goes 1 -> 5. If the time goes back to 1.0 (from +0x57c) before the
search, write +0x57c too in the next test.
"""
import math
import sys
import time

import mem
from findptr import modules, scan
from loot import loot_pos, loot_vtables
from lootstate import ITEMS_LEFT, KIND, SEARCH_TIME, STATE, looted
from radar import PLAYER_VT, player_pos
from rtti import parse_addr
from watch import EXE

NEAR = 10.0    # m
WATCH = 600    # s: long enough to do the teleport and aim tests in the same round


def row(p, h):
    """(search time, state, items left) of a container."""
    return round(p.f32(h + SEARCH_TIME), 3), p.u32(h + STATE), p.u32(h + ITEMS_LEFT)


if __name__ == "__main__":
    write = sys.argv[1:] == ["--write"]
    p = mem.Process(EXE, write=write)
    mods = modules(p)
    pvt = parse_addr(mods, PLAYER_VT)
    cvt = next(v for v, (label, color) in loot_vtables(mods).items() if label == "search")  # Container
    print("scanning for the player and the containers (about 75 s)...", flush=True)
    found, _ = scan(p, [(pvt, pvt), (cvt, cvt)])
    player = next((h for h, v in found if v == pvt), None)
    if player is None:
        sys.exit("player not found. Load a save first.")
    me = player_pos(p, player)
    near = sorted((d, h) for h, v in found if v == cvt and (pos := loot_pos(p, h)) and (d := math.dist(pos, me)) < NEAR)
    for d, h in near:
        t, state, items = row(p, h)
        print(f"  {d:4.1f} m  {h:#x}  kind {p.u32(h + KIND)}  search {t:.2f} s  state {state}  items {items}"
              + ("  LOOTED" if looted(p, h) else ""))
    todo = [h for d, h in near if p.u32(h + KIND) == 1 and not looted(p, h)]
    if not todo:
        sys.exit(f"no unsearched 'search' container within {NEAR} m. Stand next to one.")
    if not write:
        sys.exit(f"dry run: --write would set the search time of {len(todo)} containers to 0.")
    for h in todo:
        p.write_f32(h + SEARCH_TIME, 0.0)
    print(f"wrote 0.0 to the search time of {len(todo)} containers. Search one now (hold the key). "
          f"Watching for {WATCH} s.", flush=True)
    last, start = {}, time.time()
    while time.time() < start + WATCH:
        for h in todo:
            try:
                now = row(p, h)
            except OSError:
                now = "gone (freed by the game)"
            if now != last.get(h):
                print(f"  {time.time() - start:5.1f} s  {h:#x}  " + (now if isinstance(now, str) else
                      f"search time {now[0]:.2f} s  state {now[1]}  items left {now[2]}"), flush=True)
                last[h] = now
        time.sleep(0.02)
