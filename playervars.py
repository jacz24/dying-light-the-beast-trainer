"""The game's player variables: its own switches and numbers (3111 of them, e.g. InfiniteStamina), in one array.

Run: python playervars.py [regex]    lists the variables whose name matches, with the value and the default. Read-only.
Session 5, found from the cheat table's ammo lead (its offsets were for game 1.2.2C and had moved):
- The table's getter pattern (cmp byte [rcx+X],0 / mov rax,[rip+global] / jne / mov rax,[rcx+Y] / mov rax,[rax+0xbe8] /
  ret) sits at gamedll+0x126fd40 in this build. Its global holds the PlayerState; PlayerState +0xbe8 -> the array.
- Each variable is a 0x18-byte record at its offset: class pointer (BoolPlayerVariable, FloatPlayerVariable, ...),
  then the value, then the default (bool: +8 and +9; float: +8 and +0xc).
- The game registers each one by name: mov dword [rsp+X], offset / lea r9,[rsp+X] / lea r8,[name] / mov dl,type.
  names() reads them from the code, so the list follows a game update. Session 8: the app writes only at the offsets
  that resolve_offsets() found by name in the running build (in session 7: InfiniteStamina 0x3910, ImmortalityBuff 0x1588, ...).
"""
import re
import struct
import sys
from collections import Counter

from rtti import image, parse_addr, vtable_name

PLAYER_STATE = "gamedll_ph_x64_rwdi.dll+0x3921830"  # global -> PlayerState
VARS = 0xbe8                                        # PlayerState -> the variable array
# Session 8: the getter as a code signature (1 hit in this build, at +0x126fd40): cmp byte [rcx+X],0 / mov rax,[rip+global]
# / jne / mov rax,[rcx+Y] / mov rax,[rax+VARS] / ret. It gives the global and VARS in a later build too.
GETTER = re.compile(rb"\x80\xB9....\x00\x48\x8B\x05(....)\x75.\x48\x8B\x81....\x48\x8B\x80(....)\xC3", re.S)
PATH = {}  # 'state' (the global's address) and 'vars' from GETTER (resolve_offsets); empty: the constants above
ON = b"\x01"
# switch -> [(variable, value while on)]
CHEATS = {
    "ammo": [(n, ON) for n in ("FirearmsPistolInfiniteAmmo", "FirearmsRevolverInfiniteAmmo", "FirearmsRifleInfiniteAmmo",
                               "FirearmsShotgunInfiniteAmmo", "FirearmsSMGInfiniteAmmo",
                               "FirearmsFlameThrowerInfiniteAmmo", "InfiniteArrows")],
    "stamina": [("InfiniteStamina", ON)],
    "immortal": [("ImmortalityBuff", ON)],  # session 7: the game's own god mode switch (bool, default 0)
    # session 7: a fraction like OutfitHumanDamageResistanceFactor (0.15); 1.0 = guess: no fall damage. Untested.
    "fall": [("FallDamageResistance", struct.pack("<f", 1.0))],
    # No 'infinite durability' variable exists. EfficientFightingDurabilityLostMul (0x9d98) = 0 was tried in session 5:
    # a weapon still went 75 -> 67. Durability is kept in the item instead (items.py).
}
# slider -> [float variable]: the app writes base x factor (session 7, the user's choice: x1 to x4, x1 = off).
# MoveSprintSpeed read 6 with a game default of 5 (a skill), so the base is the value before the first write, not +0xc.
# Session 7: NormalJumpHeight alone at x4 (18.08, held by the game) did not change the jump (the user). Candidates: the
# held jump and the tap jump after the advanced parkour skill (their hold times read 0.242 and 0.212, defaults 0.1).
SCALED = {"jump": ["NormalJumpHeight", "HoldJumpHeight", "AdvancedParkourNormalJumpHeight"],
          "speed": ["MoveForwardMaxSpeed", "MoveSprintSpeed"]}
OFFSETS = {}  # name -> offset in the running game build, filled by resolve_offsets(); a name not in it is never written
# StringPlayerVariable (session 7): a 0x18-byte record whose value and default are short strings (the aikind.py form)
# that name a parameter elsewhere: MeleeDamageMul -> 'Player_MeleeDamageMul', FallDamageReduction ->
# 'Player_FallDamageReduction'. No number in the record.


def var_array(p, mods):
    """The address of the variable array, or None (no save loaded)."""
    try:
        return p.u64(p.u64(PATH.get("state") or parse_addr(mods, PLAYER_STATE)) + PATH.get("vars", VARS)) or None
    except OSError:
        return None


def resolve_offsets(p, mods):
    """Session 8: fill OFFSETS from the running build's registration code (names(), 0.6 s), so a game update that moves
    the variables cannot make a write land in another variable of the same class. A name found 0 or 2+ times stays out.
    Also PATH from the getter signature, when it matches exactly once. Returns names()."""
    g, size = next((b, s) for b, s, n in mods if n.lower() == "gamedll_ph_x64_rwdi.dll")
    img = image(p, g, size)
    found = names(img)
    count = Counter(n for n, o in found)
    OFFSETS.clear()
    OFFSETS.update((n, o) for n, o in found if count[n] == 1)
    PATH.clear()
    if len(hits := list(GETTER.finditer(img))) == 1:
        m = hits[0]
        PATH.update(state=g + m.start() + 14 + struct.unpack("<i", m[1])[0], vars=struct.unpack("<I", m[2])[0])
    return found


def check(pw, mods, arr, name, cls="PlayerVariable"):
    """The guard: the offset of this name in this build (resolve_offsets()), and a record of this class there, so a write never
    lands in another variable, or in game code or data. Returns the offset."""
    off = OFFSETS.get(name)
    if off is None:
        raise RuntimeError(f"{name}: not found by name in this game build; not written")
    if not (vtable_name(pw, mods, pw.u64(arr + off)) or "").endswith(cls):
        raise RuntimeError(f"{name}: no {cls} at {arr + off:#x}; not written")
    return off


def apply(pw, mods, arr, cheat, on):
    """Write the cheat's values (on), or each variable's own default back (off). pw: a write handle. Every variable of
    the cheat passes the guard before the first write, so a refused cheat writes nothing at all."""
    offs = [check(pw, mods, arr, name) for name, value in CHEATS[cheat]]
    for off, (name, value) in zip(offs, CHEATS[cheat]):
        n = len(value)
        pw.write(arr + off + 8, value if on else pw.read(arr + off + 8 + n, n))


def scale(pw, mods, arr, cheat, factor, base):
    """Write base x factor into each float variable of a slider; factor 1 writes the base back. base: {name: value
    before the app's first write}, kept and saved by the caller, so a killed app cannot make x2 compound into x4."""
    offs = [check(pw, mods, arr, name, "FloatPlayerVariable") for name in SCALED[cheat]]
    for off, name in zip(offs, SCALED[cheat]):
        pw.write_f32(arr + off + 8, base.setdefault(name, pw.f32(arr + off + 8)) * factor)


def names(img):
    """[(name, offset)] of every variable, read from the game's registration code. img: rtti.image() of gamedll."""
    out = []
    for m in re.finditer(rb"\xC7\x84\x24(....)(....)\x4C\x8D\x8C\x24(....)\x4C\x8D\x05(....)\xB2", img, re.S):
        if m[1] == m[3]:  # the offset is stored where r9 points
            at = m.start() + 26 + struct.unpack("<i", m[4])[0]  # rip after 'lea r8, [rip+disp]'
            out.append((img[at:at + 80].split(b"\0")[0].decode("ascii", "replace"), struct.unpack("<I", m[2])[0]))
    return out


if __name__ == "__main__":
    import mem
    from findptr import modules
    from watch import EXE

    p = mem.Process(EXE)
    mods = modules(p)
    arr = var_array(p, mods)
    if arr is None:
        sys.exit("no PlayerState: load a save first.")
    found = resolve_offsets(p, mods)
    missing = [n for rows in CHEATS.values() for n, v in rows if n not in OFFSETS] + [
        n for rows in SCALED.values() for n in rows if n not in OFFSETS]
    want = re.compile(sys.argv[1] if len(sys.argv) > 1 else ".", re.I)
    cls = {}
    for name, off in sorted(found, key=lambda r: r[1]):
        if want.search(name):
            vt = p.u64(arr + off)
            kind = cls.setdefault(vt, vtable_name(p, mods, vt)) or "?"
            raw = p.read(arr + off + 8, 8)
            value = (f"{raw[0]} (default {raw[1]})" if "Bool" in kind else
                     f"{struct.unpack('<f', raw[:4])[0]:g} (default {struct.unpack('<f', raw[4:])[0]:g})" if "Float" in kind
                     else raw.hex(" "))
            print(f"  {off:#7x}  {kind:22} {name:50} {value}")
    print(f"{len(found)} variables; " + (f"NOT FOUND by name (the app refuses them): {missing}" if missing
                                         else "every cheat variable found once by name."))
