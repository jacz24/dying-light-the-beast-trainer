"""Aimbot step 3: the head position of a HumanAI, from its skeleton. Read-only.

Run: python head.py    (elevated terminal, a save loaded). One 75 s scan, then it lists the AI within 40 m once:
the head height above the feet, the head offset to the side, and the skeleton file.

Path (session 3, static check in a pause, 47 of 47 AI):
  HumanAI +0x1d28 -> X, a member at +0x28 inside the AI's CoSkeleton.
  X +0x58   render world matrix, 3x4 row-major, WITH the zombie's size scale (0.93 to 1.10). It is the matrix of the
            CoWorldXform::Matrices object at X+0x48; its translation equals the AI position (HumanAI+0x1cc0).
            HumanAI+0x1c90 holds the same rotation rows without the scale.
  X +0x290  pose record {bone array, bone count, CCompactMesh}. The array holds one 3x4 row-major model-space matrix
            (0x30 bytes) per bone; the translation is the bone position, feet at height 0. A second record at +0x2c0
            is another frame buffer (equal while paused).
  CCompactMesh +0x10 bone count, +0x68 -> bone records of 0xe0 bytes, after a header (+0x0 -> the skeleton file name)
            of 0xd8 + 8 x (u32 at +0x5c) bytes: 1 on human and zombie meshes (header 0xe0), 3 on the Volatile mesh
            (0xf0). Session 7: 8 of 8 meshes; the fixed 0xe0 read no names on the Volatile, so it had no head dot.
            Bone record +0x28 -> the name. The head bone is called 'head'; its index differs per mesh (#62 Volatile,
            #106 to #173 others).
Evidence: standing AI had the head at 1.51 to 1.62 m (model space), two resting AI at 0.29 and 0.52 m, one lying at -0.09 m.
"""
import struct
import sys

SKEL = 0x1d28       # HumanAI -> X (inside the CoSkeleton)
WORLD = 0x58        # X: render world matrix, 3x4 row-major, scale included
POSE = 0x290        # X: {bone array, bone count, CCompactMesh}
MESH_COUNT, MESH_BONES, BONE_REC, BONE_NAME = 0x10, 0x68, 0xe0, 0x28
HEADER, HEADER_N = 0xd8, 0x5c  # bone records start after HEADER + 8 x (u32 at HEADER_N) bytes
_index = {}         # (mesh, bone count, name) -> bone index. shortcut: assumes a mesh address is not reused for another mesh; clear it after a load if heads look wrong.


def cstr(p, addr, n=48):
    try:
        return p.read(addr, n).split(b"\0")[0].decode("ascii", "replace")
    except OSError:
        return None


def bone_name(p, recs, i):
    """The name of bone i, from the mesh's bone records (CCompactMesh +0x68)."""
    return cstr(p, p.u64(recs + HEADER + 8 * p.u32(recs + HEADER_N) + i * BONE_REC + BONE_NAME))


def bone_index(p, mesh, count, name="head"):
    """Index of the named bone in this mesh, or None. Reads the names once per mesh."""
    key = (mesh, count, name)
    if key not in _index:
        try:
            recs = p.u64(mesh + MESH_BONES)
            _index[key] = next((i for i in range(count) if bone_name(p, recs, i) == name), None)
        except OSError:
            return None
    return _index[key]


def transform(m, v):
    """A 3x4 row-major matrix (12 floats) applied to a point."""
    return tuple(m[r * 4] * v[0] + m[r * 4 + 1] * v[1] + m[r * 4 + 2] * v[2] + m[r * 4 + 3] for r in range(3))


def head_pos(p, human, bone="head"):
    """World (x, height, z) of the AI's head bone, or None (no skeleton, unknown mesh, unreadable)."""
    try:
        x = p.u64(human + SKEL)
        world = struct.unpack("<12f", p.read(x + WORLD, 0x30))
        arr, count, mesh = struct.unpack("<3Q", p.read(x + POSE, 24))
        if not 0 < count < 1000:
            return None
        i = bone_index(p, mesh, count, bone)
        if i is None:
            return None
        m = struct.unpack("<12f", p.read(arr + i * 0x30, 0x30))
    except OSError:
        return None
    return transform(world, (m[3], m[7], m[11]))


assert transform((1, 0, 0, 10, 0, 1, 0, 20, 0, 0, 1, 30), (1, 2, 3)) == (11, 22, 33)
assert transform((0, 0, 1, 0, 0, 2, 0, 0, -1, 0, 0, 0), (1, 1, 0)) == (0, 2, -1)  # 90 degrees about y, height scale 2

if __name__ == "__main__":
    import mem
    from findptr import modules
    from radar import AI_POS, HUMAN_VT, PLAYER_VT, find_objects, heap_of, humans_in, player_pos, read
    from rtti import parse_addr
    from track import flat, sane

    from watch import EXE

    p = mem.Process(EXE)
    pvt, hvt = (parse_addr(modules(p), t) for t in (PLAYER_VT, HUMAN_VT))
    print("scanning for the player and the AI (about 12 s)...", flush=True)
    player, humans = find_objects(p, pvt, hvt)
    if player is None or not humans:
        sys.exit("load a save first")
    me = player_pos(p, player)
    near = sorted((flat(me, v), h, v) for h in humans_in(p, heap_of(p, humans[0]), hvt)
                  if sane(v := read(p, h + AI_POS)) and flat(me, v) < 60)
    if sys.argv[1:2] == ["bones"]:  # python head.py bones [type prefix]: every bone of the nearest AI of that type
        from aikind import kind
        want = sys.argv[2] if len(sys.argv) > 2 else "Volatile"
        a = next((h for d, h, feet in near if (kind(p, h) or "").startswith(want)), None)
        if a is None:
            sys.exit(f"no {want} within 60 m; types near: {sorted({kind(p, h) for d, h, f in near}, key=str)}")
        arr, count, mesh = struct.unpack("<3Q", p.read(p.u64(a + SKEL) + POSE, 24))
        recs = p.u64(mesh + MESH_BONES)
        print(f"{kind(p, a)} {a:#x}: {count} bones, skeleton {cstr(p, p.u64(recs))}; head_pos: {head_pos(p, a)}")
        for i in range(count):
            m = struct.unpack("<12f", p.read(arr + i * 0x30, 0x30))
            print(f"  #{i:3} {bone_name(p, recs, i)!s:32} height {m[7]:5.2f}")
        sys.exit()
    near = [n for n in near if n[0] < 40]
    for d, h, feet in near:
        hd = head_pos(p, h)
        try:  # the skeleton file name, for the reader: record 0 of the mesh's bone records
            skel = cstr(p, p.u64(p.u64(p.u64(p.u64(h + SKEL) + POSE + 16) + MESH_BONES)))
        except OSError:
            skel = "?"
        print(f"  {d:5.1f} m  {h:#x}  " + (f"head {hd[1] - feet[1]:5.2f} m above the feet, {flat(feet, hd):.2f} m to the side"
                                         if hd else "no head") + f"  {skel}")
