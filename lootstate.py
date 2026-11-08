"""Loot state: already searched or taken? And the search time. Read-only.

Run: python lootstate.py    (elevated terminal, a save loaded). One scan (about 75 s), then it lists the loot within
30 m with its state. Test: run it, search one 'search' container, run it again: that container must go 1 -> 5.

Found statically in session 3 (game paused), from the fields of all loaded loot objects:
- +0x388 state, in Container and ComplexContainer (a shared base class): 1 = near the player, 2 = far (dormant),
  5 = searched or taken. The 4 Container objects with 5 have 0 items left (+0x4d0) of 1 or 3 (+0x4d4); every other
  Container still had all its items. All 16 ComplexContainer with 5 sat within 30 m, where the user had looted.
  The game's search-time function reads it too: 'if kind == 0 and state == 1: return 0'.
- +0x508 kind: 1 = search (hold the key), 2 = quick (all bodies, some containers), 0 = pickup (ComplexContainer).
- +0x1f8 search time in seconds: 1.0 for kind 1 (a copy of +0x57c), 0.1 for kind 2 (a copy of +0x580), 0 for pickups.
BodyContainer has state 1 on every object (taken bodies not seen yet); CollectableObject has another layout.
"""
import math
import sys

STATE, LOOTED = 0x388, 5
KIND = 0x508          # 0 pickup, 1 search, 2 quick
SEARCH_TIME = 0x1f8   # float seconds; the game returns 0 for kind 2, and for kind 0 in state 1
ITEMS_LEFT, ITEMS_START = 0x4d0, 0x4d4  # Container only


def looted(p, obj):
    """True when the player already searched or took this Container or ComplexContainer."""
    try:
        return p.u32(obj + STATE) == LOOTED
    except OSError:
        return False


ITEM = 0x318  # in the model (+0x8) of a ComplexContainer: the item's mesh, 0 while no item lies there


def no_item(p, obj):
    """True for an active pickup (state 1, ComplexContainer) whose model holds no item. Session 8, ice cream truck: the
    game set a taken pickup back from 5 to 1 when the player came back (5 of 5, at about 9 m) and spawned a new item only
    sometimes; when it did, the model's +0x318 got a pointer (5 of 5), and each take cleared it (6 of 6). A dormant pickup
    (state 2) reads 0 too, before the game decides, so it stays shown. Container models read 0 always: not for them."""
    try:
        return p.u32(obj + STATE) == 1 and not p.u64(p.u64(obj + 0x8) + ITEM)
    except OSError:
        return False


def emptied(p, obj):
    """True when a BodyContainer has no items left. Its state stays 1 after a search, so the state cannot tell.
    Candidate (session 5): the one fresh corpse the user looted read 0 of 2 items; the unlooted ones read 1/1, 2/2."""
    try:
        return p.u32(obj + ITEMS_LEFT) == 0
    except OSError:
        return False


if __name__ == "__main__":
    import mem
    from findptr import modules, scan
    from loot import loot_pos, loot_vtables
    from radar import PLAYER_VT, player_pos
    from rtti import parse_addr
    from watch import EXE

    p = mem.Process(EXE)
    mods = modules(p)
    lvt, pvt = loot_vtables(mods), parse_addr(mods, PLAYER_VT)
    print("scanning (about 75 s)...", flush=True)
    found, _ = scan(p, [(v, v) for v in [pvt, *lvt]])
    player = next((h for h, v in found if v == pvt), None)
    if player is None:
        sys.exit("player not found. Load a save first.")
    me = player_pos(p, player)
    rows = sorted((math.dist(pos, me), h, lvt[v][0]) for h, v in found if v in lvt and (pos := loot_pos(p, h)))
    for d, h, label in rows:
        if d > 30:
            break
        print(f"  {d:5.1f} m  {label:11} {h:#x}  state {p.u32(h + STATE)}  kind {p.u32(h + KIND)}  "
              f"search {p.f32(h + SEARCH_TIME):.2f} s  items {p.u32(h + ITEMS_LEFT)}/{p.u32(h + ITEMS_START)}"
              + ("  LOOTED" if looted(p, h) else ""))
