"""Record the world position of every CModelObject until F1, save raw samples, then list walkers. Read-only.

Run: python -m research.movers            record (scan about 75 s), then analyze
     python -m research.movers analyze    analyze the saved file again
"""
import struct
import sys
import time

import numpy as np

OUT = __file__.replace("movers.py", "movers.npz")
MATRIX = 0xf0  # 3x4 row-major world matrix; translation at +0xfc, +0x10c, +0x11c


def record():
    import mem
    from findptr import modules, scan
    from rtti import parse_addr
    from radar import PLAYER_VT, PLAYER_POS, read, alive
    from watch import EXE, key_down

    p = mem.Process(EXE)
    mods = modules(p)
    pvt, mvt = parse_addr(mods, PLAYER_VT), parse_addr(mods, "engine_x64_rwdi.dll+0x18059e8")  # CModelObject
    print("scanning (about 75 s)...", flush=True)
    found, _ = scan(p, [(pvt, pvt), (mvt, mvt)])
    player = next(h for h, v in found if v == pvt)
    models = [h for h, v in found if v == mvt]
    print(f"{len(models)} models. Recording. Fight zombies, then hold F1.", flush=True)
    ts, mes, rows, t0 = [], [], [], time.time()
    while not key_down():
        if not alive(p, player, pvt):
            print("  the player object is gone (death?). Stopping.", flush=True)
            break
        row = np.full((len(models), 3), np.nan, dtype=np.float32)
        for k, m in enumerate(models):
            try:
                b = p.read(m, MATRIX + 0x30)
            except OSError:
                continue
            if struct.unpack_from("<Q", b)[0] == mvt:  # else freed or reused
                r = struct.unpack_from("<12f", b, MATRIX)
                row[k] = r[3], r[7], r[11]
        ts.append(time.time() - t0)
        mes.append(read(p, player + PLAYER_POS))
        rows.append(row)
        if len(ts) % 50 == 1:
            print(f"  {ts[-1]:6.1f} s  me=({mes[-1][0]:.0f},{mes[-1][1]:.0f},{mes[-1][2]:.0f})", flush=True)
        time.sleep(0.1)
    np.savez(OUT, t=np.array(ts), me=np.array(mes, dtype=np.float32), pos=np.stack(rows), models=np.array(models, dtype=np.uint64))
    print(f"saved {len(ts)} samples to {OUT}")


def analyze():
    d = np.load(OUT)
    t, me, pos, models = d["t"], d["me"], d["pos"], d["models"]
    dt = np.diff(t)[:, None]
    step = np.hypot(*(np.diff(pos[:, :, [0, 2]], axis=0)).transpose(2, 0, 1))  # ground distance per sample, per model
    walk = np.where((step / dt < 15) & (dt < 0.5), step, 0)  # below 15 m/s between two close samples: a real move
    jumps = np.nansum(step / dt >= 15, axis=0)
    walked = np.nansum(walk, axis=0)
    near = np.nanmin(np.hypot(pos[:, :, 0] - me[:, None, 0], pos[:, :, 2] - me[:, None, 2]), axis=0)
    print(f"{len(t)} samples over {t[-1]:.0f} s, {len(models)} models")
    order = np.argsort(-walked)
    print("model             walked  jumps  nearest to me  first -> last valid position")
    for k in order[:30]:
        if walked[k] < 1:
            break
        ok = np.flatnonzero(~np.isnan(pos[:, k, 0]))
        a, b = pos[ok[0], k], pos[ok[-1], k]
        print(f"  {int(models[k]):#x}  {walked[k]:6.1f}  {jumps[k]:5}  {near[k]:9.1f} m    "
              f"{tuple(round(float(c), 1) for c in a)} -> {tuple(round(float(c), 1) for c in b)}")


if __name__ == "__main__":
    if sys.argv[1:] != ["analyze"]:
        record()
    analyze()
