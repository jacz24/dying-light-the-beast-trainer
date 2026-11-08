"""Read-only (session 9): find the player's velocity field, for flying and NoClip.

Run: python -m research.velfind [seconds]   (default 30). Then walk, jump and fall while it records.
It reads the CBulletPhysicsCharacter (0x1400 bytes) and its btRigidBody (+0x158, 0x400 bytes) at each new game frame
(when the teleport source +0xfd0 changes, and at least every 50 ms), saves velfind.npz, and lists the floats that follow
the source's speed (its change per second between frames): per axis, the correlation and the slope (1.0 = m/s).
python -m research.velfind analyze: the same list from the saved file.
"""
import sys
import time

import numpy as np

CHAR_BYTES, BODY_BYTES, BODY_PTR = 0x1400, 0x400, 0x158
OUT = "velfind.npz"


def record(seconds):
    import mem
    from findptr import modules
    from godmode import find_module
    from radar import PLAYER_VT
    from rtti import parse_addr
    from teleport import BPC_VT, SOURCE, character
    from watch import EXE

    p = mem.Process(EXE)
    mods = modules(p)
    player = find_module(p, parse_addr(mods, PLAYER_VT))
    c = character(p, player, parse_addr(mods, BPC_VT)) if player else None
    if c is None:
        sys.exit("player not found")
    body = p.u64(c + BODY_PTR)
    cn, bn = min(CHAR_BYTES, p.region_size(c)), min(BODY_BYTES, p.region_size(body))  # session 9: the body sat 0x400
    ts, cs, bs, last, last_t = [], [], [], None, 0  # bytes before the end of its region; the next page is not readable
    print(f"{time.strftime('%H:%M:%S')} ready: recording {seconds} s ({cn:#x} + {bn:#x} bytes a frame). Walk, jump, "
          f"fall.", flush=True)
    end = time.time() + seconds
    while (now := time.time()) < end:
        src = p.read(c + SOURCE, 12)
        if src != last or now - last_t > 0.05:
            ts.append(now)
            cs.append(p.read(c, cn))
            bs.append(p.read(body, bn))
            last, last_t = src, now
        time.sleep(0.001)
    np.savez(OUT, t=np.array(ts), char=np.frombuffer(b"".join(cs), np.uint8).reshape(len(cs), -1),
             body=np.frombuffer(b"".join(bs), np.uint8).reshape(len(bs), -1))
    print(f"{time.strftime('%H:%M:%S')} done: {len(ts)} frames saved in {OUT}", flush=True)


def speed(t, pos):
    """Change per second of pos between rows (the first row repeats the second)."""
    v = np.diff(pos, axis=0) / np.diff(t)[:, None]
    return np.vstack([v[:1], v])


def candidates(floats, target, top=8):
    """[(corr, slope, offset index)] of the float columns that best follow target (one axis of the speed)."""
    ok = np.isfinite(floats).all(axis=0) & (np.abs(floats) < 1e4).all(axis=0) & (floats.std(axis=0) > 1e-3)
    f = floats[:, ok]
    fc, tc = f - f.mean(axis=0), target - target.mean()
    corr = (fc * tc[:, None]).sum(axis=0) / (np.sqrt((fc ** 2).sum(axis=0) * (tc ** 2).sum()) + 1e-12)
    slope = (fc * tc[:, None]).sum(axis=0) / ((tc ** 2).sum() + 1e-12)
    idx = np.flatnonzero(ok)
    best = np.argsort(-np.abs(corr))[:top]
    return [(corr[i], slope[i], idx[i]) for i in best]


def analyze():
    from teleport import SOURCE

    d = np.load(OUT)
    t, char, body = d["t"], d["char"].view(np.float32), d["body"].view(np.float32)
    pos = char[:, SOURCE // 4:SOURCE // 4 + 3].astype(np.float64)
    moved = np.r_[True, np.any(np.diff(pos, axis=0) != 0, axis=1)]  # one row per game frame: drop the 50 ms repeats
    t, pos, char, body = t[moved], pos[moved], char[moved], body[moved]
    v = speed(t, pos)
    print(f"{len(t)} frames over {t[-1] - t[0]:.1f} s; speed of the source: up {v[:, 1].min():.1f} to "
          f"{v[:, 1].max():.1f} m/s, horizontal up to {np.hypot(v[:, 0], v[:, 2]).max():.1f} m/s")
    for axis, name in enumerate(("x", "up", "z")):
        print(f"\n{name}: the floats that follow the source speed (corr, slope; slope 1.0 = the same m/s)")
        for where, arr in (("char", char), ("body", body)):
            for corr, slope, i in candidates(arr, v[:, axis]):
                print(f"   {where} +{i * 4:#06x}  corr {corr:+.3f}  slope {slope:+.3f}  "
                      f"range {arr[:, i].min():8.2f} to {arr[:, i].max():8.2f}")


if __name__ == "__main__":
    if sys.argv[1:] == ["analyze"]:
        analyze()
    else:
        record(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
        analyze()
