"""Step 4: god mode. Keeps the player's real health at its maximum.

Run: python godmode.py            dry run, read-only: prints the player's health twice a second. Hold F1 to end.
     python godmode.py --write    also writes the maximum into the current health. WRITES GAME MEMORY.
Session 3 (game paused, static): PlayerHealthModule holds its lifecs health elements inside the object, not behind a
pointer like HumanHealthModule. The elements at +0x10 and +0x80 both read 164.2 / 475, and the HUD health bar was
34.3 % full (164.2 / 475 = 34.6 %). Which element the game really uses is not tested, so --write sets both.
The cheat table's lead agrees: PlayerDI_PH +0x1c8 (mask 48 bits; the top 16 bits are the count) -> module list,
entry 0x56 = this module, and its "+0x2c current, +0x3c maximum" are the first element's fields.
Test before the first --write: run the dry run, take one zombie hit, and check which numbers drop.
"""
import struct
import sys
import time

import mem
from findptr import modules, scan
from radar import alive
from rtti import parse_addr
from watch import EXE, key_down

PLAYER_HEALTH_VT = "gamedll_ph_x64_rwdi.dll+0x29a2418"  # PlayerHealthModule: 1 object, its +0x8 is PlayerDI_PH
ELEMENTS = (0x10, 0x80)      # embedded lifecs LifeHealth elements (a third one at +0x48 is all zero)
EL_CUR = (0x1c, 0x20, 0x24)  # in an element: three copies of the current health, the same as for the AI
EL_MAX = 0x30                # in an element: the maximum health (also at +0x2c and +0x34)


def find_module(p, vt):
    """The PlayerHealthModule, or None. One scan of all memory, about 75 s."""
    found, _ = scan(p, [(vt, vt)])
    return found[0][0] if len(found) == 1 else None


def player_health(p, hm):
    """[((3 current copies), maximum)] for each element, or None."""
    try:
        b = p.read(hm, 0xc0)
    except OSError:
        return None
    return [(tuple(struct.unpack_from("<f", b, e + o)[0] for o in EL_CUR), struct.unpack_from("<f", b, e + EL_MAX)[0])
            for e in ELEMENTS]


def heal(pw, hm, hp):
    """Write the maximum into each element whose health is below it (pw: a write handle, hp: player_health()).
    Skips 0: the player is already dead, and a revive by write is untested."""
    for e, (cur, mx) in zip(ELEMENTS, hp):
        if 0 < cur[0] < mx < 1e5:
            for off in EL_CUR:
                pw.write_f32(hm + e + off, mx)


if __name__ == "__main__":
    write = sys.argv[1:] == ["--write"]
    p = mem.Process(EXE, write=write)
    vt = parse_addr(modules(p), PLAYER_HEALTH_VT)
    hm, shown = None, 0
    while not key_down():
        if not alive(p, hm, vt):  # the start, or a death, a sleep or a load made a new player
            print("scanning for the player's health module (about 75 s)...", flush=True)
            hm = find_module(p, vt)
            if hm is None:
                sys.exit("expected 1 PlayerHealthModule. Load a save first.")
            print(f"PlayerHealthModule at {hm:#x}. {'GOD MODE ON' if write else 'Dry run'}. Hold F1 to end.", flush=True)
        hp = player_health(p, hm)
        if write and hp:
            heal(p, hm, hp)
        if hp and time.time() >= shown:
            print("  " + "   ".join(f"element +{e:#x}: {'/'.join(f'{c:.1f}' for c in cur)} of {mx:.0f}"
                                     for e, (cur, mx) in zip(ELEMENTS, hp)), flush=True)
            shown = time.time() + 0.5
        time.sleep(0.05)
