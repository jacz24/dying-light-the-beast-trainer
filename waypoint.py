"""The map waypoint (session 7), for the app's F8 teleport. Read-only.

Path: LevelDI (1 object) +0x27c8 -> X; X +0x8 -> Locations::WaypointLocation; its +0xa0 = (x, height, z).
Found from the cheat table's lead (+0x27d0, written for game 1.2.2C): a full scan found the waypoint object (only while a
waypoint is set on the map), a pointer search back from it found X at offset 8 and LevelDI +0x27c8, and the path
was then checked from the LevelDI. The height read 47.8 where the player stood at 37.8 (guess: the ground at the marker).
"""
LEVEL_VT = "gamedll_ph_x64_rwdi.dll+0x2a762e8"     # LevelDI
WAYPOINT_VT = "gamedll_ph_x64_rwdi.dll+0x28aace8"  # Locations::WaypointLocation
LEVEL_WAYPOINT, WAYPOINT_POS = 0x27c8, 0xa0


def waypoint(p, level, wvt):
    """(x, height, z) of the map waypoint, or None (no waypoint set, or the path broke)."""
    try:
        w = p.u64(p.u64(level + LEVEL_WAYPOINT) + 0x8)
        return p.vec3(w + WAYPOINT_POS) if p.u64(w) == wvt else None
    except OSError:
        return None
