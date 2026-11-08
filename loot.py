"""Loot ESP data: searchable containers, bodies and collectables, found by their class (vtable). Read-only.

Each loot object holds its own 3x4 row-major world matrix at +0x140, the same layout as a CModelObject at +0xf0.
Session 3: 72 of 93 Container and 109 of 136 ComplexContainer objects were within 150 m, each at its own place.
A screenshot put the ComplexContainer markers next to the game's own white loot dots.
The objects sit in many small heap regions (not one block like the AI), so new ones need a full scan (about 75 s).
"""
import struct

from rtti import parse_addr

# class vtable -> (label, color). Labels from the user's check in the game (session 3).
# Not included: ContainerItem (parts of a ComplexContainer, same positions), LootedObject (707, no position field).
LOOT = {
    "gamedll_ph_x64_rwdi.dll+0x29c1910": ("search", "#ffff00"),       # Container: loot you search (hold the key)
    "gamedll_ph_x64_rwdi.dll+0x29c7e98": ("pickup", "#00ffff"),       # ComplexContainer: loot you take at once
    "gamedll_ph_x64_rwdi.dll+0x29c2e00": ("body", "#ff4040"),         # BodyContainer: dead zombies and NPCs
    "gamedll_ph_x64_rwdi.dll+0x29d5508": ("collectable", "#00ff00"),  # CollectableObject: rare quest items (a treasure map)
}
MATRIX = 0x140


def loot_vtables(mods):
    """{vtable address: (label, color)} for this run of the game."""
    return {parse_addr(mods, k): v for k, v in LOOT.items()}


def spawned(p, obj):
    """False when the game never put this loot into the world: no model (+0x8), or a model with no scene pointer.
    Session 8 (the user: markers on bare ground and shelves): of 270 search, pickup and collectable objects, 16 had a
    model with +0x3a0 = 0 (257 others: one shared pointer), +0x390 = -1 and +0x40 bit 3 clear. 3 of the 16 were the
    user's 3 false markers, 1.6 to 3.1 m away; the other 13 were 93 m or more away. 3 more objects had no model."""
    try:
        return bool((m := p.u64(obj + 0x8)) and p.u64(m + 0x3a0))
    except OSError:
        return False


def loot_pos(p, obj):
    """(x, height, z) of a loot object: the translation column of its world matrix, or None."""
    try:
        r = struct.unpack("<12f", p.read(obj + MATRIX, 0x30))
    except OSError:
        return None
    return r[3], r[7], r[11]


def model_pos(p, obj):
    """(x, height, z) of the loot's model (obj +0x8 -> its matrix at +0xf0), or None. Use it for BodyContainer: the game
    reuses body objects, and their own matrix keeps an old place. Session 5: 2 of 2 fresh corpses had their model 0.1 m
    from the dead zombie and their own matrix 93 and 107 m away; 14 of 16 bodies' models sat where the user fought."""
    try:
        r = struct.unpack("<12f", p.read(p.u64(obj + 0x8) + 0xf0, 0x30))
    except OSError:
        return None
    return r[3], r[7], r[11]
