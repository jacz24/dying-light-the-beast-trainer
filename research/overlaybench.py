"""How fast can the overlay window redraw? The painters of overlay.py (paint.py) in one click-through window, 3440x1440.

Run: python -m research.overlaybench [boxes] [--tk]    (no game needed; a test window shows for 4 s, then the result)
Default: the raylib window (vsync). --tk: the tkinter canvas. Each frame also calls root.update(), as overlay.py does.
"work" = the time outside paint.end(): the draw calls and root.update() (where tk redraws). "end" = the time in
paint.end(): raylib's GPU flush and present, which waits for vsync and for the driver's frame cap.
Session 3 (tk): 10 boxes 357 redraws/s (1.4 ms a frame), 50 boxes 72/s (12.7 ms), 150 boxes 47/s (19.8 ms).
The tk cost follows the screen area that changes, not the box count: spread boxes make Tk redraw most of the window.
"""
import ctypes
import sys
import time
import tkinter as tk

ctypes.windll.shcore.SetProcessDpiAwareness(2)

from paint import RlPaint, TkPaint

N = next((int(a) for a in sys.argv[1:] if a.isdigit()), 50)
RECT = (347, 43, 3440, 1440)  # the game's client area in session 3
use_tk = "--tk" in sys.argv

root = tk.Tk()
if use_tk:
    paint, name = TkPaint(root, RECT), "tk"
else:
    root.withdraw()
    paint, name = RlPaint(RECT), "raylib"
ticks, work, end, t0 = [], [], [], time.perf_counter()
while (now := time.perf_counter()) - t0 < 4:
    ticks.append(now)
    k = len(ticks)
    paint.begin()
    for i in range(N):
        x, y = 200 + (i * 61 + k * 3) % 3000, 200 + (i * 37) % 1000
        paint.rect(x, y, x + 40, y + 100, "#ff00ff")
        paint.text(x + 20, y + 103, f"{i} m", "#ff00ff", "n", 10)
    a = time.perf_counter()
    paint.end()
    end.append(time.perf_counter() - a)
    root.update()  # tk: the real redraw happens here
    work.append(time.perf_counter() - now - end[-1])
    if use_tk:
        time.sleep(0.001)  # as root.after(1) in session 3
root.destroy()
med = lambda xs: sorted(xs)[len(xs) // 2] * 1e3  # noqa: E731
gaps = sorted(b - a for a, b in zip(ticks[1:], ticks[2:]))
print(f"{name}, {N} boxes: {len(ticks) / (ticks[-1] - ticks[0]):.0f} redraws/s, work median {med(work):.2f} ms, "
      f"end median {med(end):.2f} ms, gap median {med(gaps):.1f} ms, p95 {gaps[int(len(gaps) * .95)] * 1e3:.1f} ms, "
      f"worst {gaps[-1] * 1e3:.1f} ms")
