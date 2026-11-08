"""Time of day (session 6). DayNightCycle, 1 object (class name found in gamedll; nothing in the cheat table):
  +0x10   the time of day as a fraction of a day (0.375 = 09:00); copies at +0x20 and +0x5c.
          It grew 0.00018 a second, so a day lasts 5536 s (92 min of real time); +0x7c = 5538 (the day length, s).
  +0x24   real seconds (+1.0 a second), copy at +0x60.  +0x28 = -1.0 (guess: a target time; -1 = none).
Run: python daynight.py [address]                dry run: the game clock every 2 s. Hold F1 to end.
     python daynight.py --write HH:MM [address]  writes the time once into the three copies (WRITES GAME MEMORY),
                                                 then prints them 4 times a second for 5 s: do they hold and count on?
Without an address it scans for the object first (about 75 s).
"""
import sys
import time

DAYNIGHT_VT = "gamedll_ph_x64_rwdi.dll+0x2a78608"
TIME = (0x10, 0x20, 0x5c)  # float, fraction of a day


def hhmm(frac):
    m = round(frac % 1 * 1440) % 1440  # minutes, rounded once, so 23:59.99 carries into 00:00
    return f"{m // 60:02d}:{m % 60:02d}"


def fraction(text):
    """'21:30' -> 0.8958."""
    h, m = text.split(":")
    assert 0 <= int(h) < 24 and 0 <= int(m) < 60, text
    return (int(h) + int(m) / 60) / 24


def set_time(pw, dnc, frac):
    for off in TIME:
        pw.write_f32(dnc + off, frac)


assert hhmm(0.375) == "09:00" and hhmm(fraction("21:30")) == "21:30" and fraction("00:00") == 0 and hhmm(0.99999) == "00:00"

if __name__ == "__main__":
    import mem
    from findptr import modules, scan
    from rtti import parse_addr
    from watch import EXE, key_down

    args = sys.argv[1:]
    write = fraction(args[1]) if args[:1] == ["--write"] else None
    rest = args[2:] if write is not None else args
    p = mem.Process(EXE, write=write is not None)
    vt = parse_addr(modules(p), DAYNIGHT_VT)
    if rest:
        dnc = int(rest[0], 16)
    else:
        print("scanning for the DayNightCycle (about 75 s)...", flush=True)
        dnc = next((h for h, v in scan(p, [(vt, vt)])[0]), None)
    if dnc is None or p.u64(dnc) != vt:
        sys.exit("no DayNightCycle found (load a save first)")

    def show():
        vals = [p.f32(dnc + off) for off in TIME]
        print(f"  {time.strftime('%H:%M:%S')}  game clock {hhmm(vals[0])}  copies " + " ".join(f"{v:.5f}" for v in vals)
              + f"  +0x28 {p.f32(dnc + 0x28):g}", flush=True)

    if write is None:
        print(f"dry run on {dnc:#x}. Hold F1 to end.", flush=True)
        while not key_down():
            show()
            time.sleep(2)
        sys.exit()
    show()
    set_time(p, dnc, write)
    print(f"  wrote {write:.5f} ({hhmm(write)}) into +0x10, +0x20, +0x5c", flush=True)
    for _ in range(20):
        time.sleep(0.25)
        show()
