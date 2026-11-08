"""Humans vs zombies: the AI type name inside each HumanAI. Read-only.

Run: python aikind.py    (elevated terminal, a save loaded). One 75 s scan, then it lists the AI within 60 m once,
with the type name, the zombie/human verdict and the health.

HumanAI +0x27c0 holds the type as a short inline string (session 3): 8 bytes, the name, zero bytes, and the last byte
= 7 - length ('Biter' -> 'Biter\\0\\0\\x02', 'Spitter' -> 'Spitter\\0'). A copy at +0x2808. (+0x23b8 is another
field: 'ChaseInfected' on Volatiles, session 5.)
A longer name is a pointer to the text with a tag in its top byte (session 5: 4 of 4 Volatiles, tag 0x22): mask it to
the low 48 bits.
The game's type table (gamedll strings, one list): Finisher, Elite, BigZombie, Human, Human2H, HumanRifle, HumanShotgun,
Biter, Viral, Screamer, Spitter, Bolter, Suicider, Goon, Demolisher, Volatile, Corruptor, Skullface, Freak_*.
Seen in session 3: Biter in all 47 live AI; Viral and Spitter in freed AI slots. No human AI was loaded, so the human
side of the rule and the form of names longer than 7 characters (HumanRifle) are not checked yet.
"""
import sys

from head import cstr

KIND = 0x27c0
EMPTY = b"\0" * 7 + b"\x07"  # an inline name of length 0
MODULES = 0x2278  # -> the AI's module set name: 'modules_npc' (friendly NPCs), 'modules_biter_anger' (Biters)
# shortcut: human types by name prefix; seen: Human_1h, Baron_Rifleman (session 6). A bandit type with another prefix
# gets a magenta box. Upgrade when a bandit is loaded: test +0x2268 ('infected' on zombies, nothing on NPCs).
HUMANS = ("Human", "Baron")
NPC = "NPC"       # kind() of a friendly NPC. Session 6, safe zone: 20 of 20 spawned AI had an empty type name, the
                  # 'modules_npc' set, no health module, and a character at +0x2308 ('dlc_ft_mq_Lydia').


def decode(b):
    """8 bytes -> the inline name, or None when it is not an inline name (a pointer, or garbage)."""
    if 1 <= b[7] <= 7:
        n = 7 - b[7]
        name, pad = b[:n], b[n:7]
    elif b[7] == 0 and b[6]:
        name, pad = b[:7], b""
    else:
        return None
    return name.decode() if name and name.isascii() and name.decode().isprintable() and not any(pad) else None


def kind(p, human):
    """The AI type name ('Biter', 'Viral', 'Human', ...), NPC for a friendly NPC, or None if it cannot be read."""
    try:
        b = p.read(human + KIND, 8)
        if b == EMPTY:
            return NPC if cstr(p, p.u64(human + MODULES) & ((1 << 48) - 1)) == "modules_npc" else None
    except OSError:
        return None
    if (name := decode(b)) is not None:
        return name
    ptr = int.from_bytes(b, "little") & ((1 << 48) - 1)  # a long name: a tagged pointer to the text
    if not 0x10000 < ptr < 1 << 47:
        return None
    try:
        s = p.read(ptr, 32).split(b"\0")[0]
    except OSError:
        return None
    return s.decode() if 3 <= len(s) and s.isascii() and s.decode().isidentifier() else None


def is_zombie(name):
    """True for a zombie type, False for a human type ('Human', 'Human2H', 'HumanRifle', ...) or a friendly NPC, None
    when unknown. Callers that write (the nuke) should skip None."""
    return None if name is None else not (name.startswith(HUMANS) or name == NPC)


assert decode(b"Biter\0\0\x02") == "Biter" and decode(b"Spitter\0") == "Spitter" and decode(b"Human2H\0") == "Human2H"
assert decode(bytes.fromhex("10f03fbf39020000")) is None  # a heap pointer is not a name
assert is_zombie("Biter") and is_zombie("Volatile") and is_zombie("Human2H") is False and is_zombie(None) is None
assert is_zombie(NPC) is False and decode(EMPTY) is None
assert is_zombie("Baron_Rifleman") is False and is_zombie("Human_1h") is False and is_zombie("Biter_Bag")

if __name__ == "__main__":
    from collections import Counter

    import mem
    from findptr import modules
    from radar import AI_POS, HEALTH_VT, HUMAN_VT, PLAYER_VT, find_objects, health, health_element, health_module, heap_of, \
        humans_in, player_pos, read
    from rtti import parse_addr
    from track import flat, sane
    from watch import EXE

    p = mem.Process(EXE)
    mods = modules(p)
    pvt, hvt, hmvt = (parse_addr(mods, t) for t in (PLAYER_VT, HUMAN_VT, HEALTH_VT))
    print("scanning for the player and the AI (about 75 s)...", flush=True)
    player, humans = find_objects(p, pvt, hvt)
    if player is None or not humans:
        sys.exit("load a save first")
    me = player_pos(p, player)
    near = sorted((flat(me, v), h) for h in humans_in(p, heap_of(p, humans[0]), hvt)
                  if sane(v := read(p, h + AI_POS)) and flat(me, v) < 60)
    for d, h in near:
        name = kind(p, h)
        hp = health(p, el) if (hm := health_module(p, h, hmvt)) and (el := health_element(p, hm)) else None
        verdict = {True: "zombie", False: "HUMAN", None: "unknown"}[is_zombie(name)]
        print(f"  {d:5.1f} m  {h:#x}  {str(name):12} {verdict:7}  health {f'{hp[0]:.0f}/{hp[1]:.0f}' if hp else '-'}")
    print("by type:", Counter(kind(p, h) for d, h in near).most_common())
