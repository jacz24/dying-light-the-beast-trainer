"""Inventory items: the durability of melee weapons.

Session 5. The game's 'durability lost' multiplier (playervars EfficientFightingDurabilityLostMul = 0) did not stop the
loss, so the value itself was found with an exact-value search (21 -> 17 -> 15 on screen: 12 places left, most of them
display copies). A write of 50 to ItemDescWithContext +0xb0 held; every display copy followed it within 55 s, and the
next hits counted down from 50 (to 24). The cheat table wrote +0xa8 for game 1.2.2C; this build is 8 bytes later.
ItemDescWithContext: one per item (860 seen). +0x8 -> the item type: ItemDescMelee, ItemDescFirearm, ItemDescInventory,
... Only melee items hold a durability at +0xb0 (22 to 150 seen); firearms hold other data there, so check the type.
"""
ITEM_VT = "gamedll_ph_x64_rwdi.dll+0x2876010"   # ItemDescWithContext
MELEE_VT = "gamedll_ph_x64_rwdi.dll+0x286ff38"  # ItemDescMelee
DURABILITY = 0xb0                               # float, in ItemDescWithContext

# Gun magazine (session 5): an exact-value search (24 -> 22 shots: 13 int32 places left). A write of 25 to
# InventoryItem +0x18 held, and within 0.01 s the weapon selector (GuiWeaponSelectorItem +0x88/+0x90) and the
# WeaponFireRightController (+0x14, +0x150) followed. InventoryItem embeds an ItemDescWithContext at +0x50, so +0x58 is
# the item type. Of 14 gun items, one was held by PlayerDI_PH +0x2b58 ([count, item]: probably the item in hand,
# candidate); the others by inventory screen entries or a world pickup. Only the gun in hand is touched, so a human
# enemy can never get an endless magazine.
INVENTORY_VT = "gamedll_ph_x64_rwdi.dll+0x293bee0"  # InventoryItem
FIREARM_VT = "gamedll_ph_x64_rwdi.dll+0x296bda8"    # ItemDescFirearm
HELD = 0x2b58     # PlayerDI_PH: [count, InventoryItem in hand]
LOADED = 0x18     # int32, in InventoryItem: the rounds in the magazine
TYPE = 0x58       # InventoryItem -> the item type


def held_gun(p, pdi, inventory_vt, firearm_vt):
    """The InventoryItem of the gun in the player's hand, or None (a melee weapon, nothing, or not readable)."""
    try:
        item = p.u64(pdi + HELD + 0x8)
        return item if p.u64(item) == inventory_vt and p.u64(p.u64(item + TYPE)) == firearm_vt else None
    except OSError:
        return None


def melee_durability(p, item, item_vt, melee_vt):
    """The durability of a melee item, or None (freed, not melee, or no durability)."""
    try:
        if p.u64(item) != item_vt or p.u64(p.u64(item + 0x8)) != melee_vt:
            return None
        d = p.f32(item + DURABILITY)
    except OSError:
        return None
    return d if 0 < d < 1e4 else None
