"""Watch the 64 MB AI/component heap for float triples that walk near the player. Read-only.

Run: python -m research.heapwatch <player CModelObject address>    record until F1, then analyze
     python -m research.heapwatch <same address> analyze            analyze the saved file again
"""
import struct
import sys
import time

import numpy as np

import mem
from findptr import modules
from rtti import parse_addr, classes_near
from watch import EXE, key_down

OUT = __file__.replace(".py", ".npz")
BASE, SIZE = 0xcb500000000, 64 << 20  # shortcut: the AI heap of session 2. After a restart, copy the "AI heap" line that radar.py prints.
RADIUS = 40


def me_pos(p, model):
    r = struct.unpack("<12f", p.read(model + 0xf0, 0x30))
    return np.array([r[3], r[7], r[11]], dtype=np.float32)


def record(p, model, mvt):
    f = np.frombuffer(p.read(BASE, SIZE), "<f4")
    me = me_pos(p, model)
    cand = []
    for st in (1, 4):  # 3 floats in a row, or a matrix column
        x, y, z = f[:len(f) - 2 * st], f[st:len(f) - st], f[2 * st:]
        with np.errstate(invalid="ignore"):
            ok = (np.abs(x - me[0]) < RADIUS) & (np.abs(z - me[2]) < RADIUS) & (np.abs(y - me[1]) < 20)
        i = np.flatnonzero(ok)
        cand.append(np.stack([i, i + st, i + 2 * st], axis=1))
    cand = np.concatenate(cand)
    print(f"me {np.round(me, 1)}: {len(cand)} candidate triples. Recording. Let the zombies chase you, then hold F1.", flush=True)
    vs, mes, ts, t0 = [], [], [], time.time()
    while not key_down():
        if p.u64(model) != mvt:
            print("  the player model is gone (death?). Stopping.", flush=True)
            break
        vs.append(np.frombuffer(p.read(BASE, SIZE), "<f4")[cand])
        mes.append(me_pos(p, model))
        ts.append(time.time() - t0)
        if len(ts) % 25 == 1:
            print(f"  {ts[-1]:6.1f} s  me={np.round(mes[-1], 0)}", flush=True)
        time.sleep(0.1)
    np.savez(OUT, t=np.array(ts), me=np.stack(mes), v=np.stack(vs), cand=cand)
    print(f"saved {len(ts)} samples ({len(ts) / ts[-1]:.1f} per s)")


def owner(p, mods, addr):
    below = [c for c in classes_near(p, mods, addr, 0x1000) if c[0] <= addr]
    return f"{max(below)[2]}+{addr - max(below)[0]:#x}" if below else "?"


def analyze(p, mods):
    d = np.load(OUT)
    t, me, v, cand = d["t"], d["me"], d["v"], d["cand"]
    dt = np.diff(t)[:, None]
    step = np.hypot(np.diff(v[:, :, 0], axis=0), np.diff(v[:, :, 2], axis=0))
    with np.errstate(invalid="ignore"):
        smooth = step / dt < 15
    walked = np.where(smooth, step, 0).sum(axis=0)
    jumps = (~smooth).sum(axis=0)
    dme = np.hypot(v[:, :, 0] - me[:, None, 0], v[:, :, 2] - me[:, None, 2])
    follow = np.nanmax(dme, axis=0) - np.nanmin(dme, axis=0)  # small: moves rigidly with me (camera, my bones)
    keep = np.flatnonzero((walked > 3) & (follow > 2) & (jumps < 5))
    print(f"{len(t)} samples, {len(cand)} triples, {len(keep)} walked over 3 m on their own")
    for k in keep[np.argsort(-walked[keep])][:40]:
        a = BASE + int(cand[k, 0]) * 4
        st = int(cand[k, 1] - cand[k, 0]) * 4
        print(f"  {a:#x} stride {st:2}  walked {walked[k]:6.1f}  jumps {jumps[k]}  dist to me {np.nanmin(dme[:, k]):5.1f}..{np.nanmax(dme[:, k]):5.1f}"
              f"  first {np.round(v[0, k], 1)} last {np.round(v[-1, k], 1)}  in {owner(p, mods, a)}")


if __name__ == "__main__":
    p = mem.Process(EXE)
    mods = modules(p)
    mvt = parse_addr(mods, "engine_x64_rwdi.dll+0x18059e8")  # CModelObject
    model = int(sys.argv[1], 16)
    assert p.u64(model) == mvt, "not a CModelObject: the player died? Find the new model address."
    if sys.argv[2:] != ["analyze"]:
        record(p, model, mvt)
    analyze(p, mods)
