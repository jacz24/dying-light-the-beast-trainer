"""The overlay windows: two painters with the same drawing calls, so overlay.py draws its layers once for both.

RlPaint: a raylib (OpenGL) window with per-pixel alpha and vsync; the GPU draws. The default since session 4.
TkPaint: the tkinter canvas of session 2 (a color key: black = see-through). The fallback (overlay.py --tk).
Both are undecorated, topmost and click-through, never take the focus (WS_EX_NOACTIVATE) and have no taskbar button.
A rect is (x, y, width, height) on the screen in physical pixels: call SetProcessDpiAwareness(2) first.
Colors are '#rrggbb'. Text anchors as in tk: 'n' = x is the middle, y the top; 'w' = x is the left edge, y the middle.
"""
import ctypes
import tkinter as tk
from functools import cache

import raylib as rl

GWL_EXSTYLE, APPWINDOW = -20, 0x40000
LAYERED, CLICK, TOOL, NOACTIVATE = 0x80000, 0x20, 0x80, 0x08000000  # WS_EX_*: TRANSPARENT = clicks go through
FONT = b"C:/Windows/Fonts/segoeuib.ttf"  # Segoe UI Bold, the tk font
u = ctypes.windll.user32


def no_focus(hwnd, extra=0):
    """No taskbar button and never the active window, plus the extra WS_EX_ styles."""
    u.SetWindowLongW(hwnd, GWL_EXSTYLE, u.GetWindowLongW(hwnd, GWL_EXSTYLE) & ~APPWINDOW | TOOL | NOACTIVATE | extra)


@cache
def rgba(color):
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16), 255


class RlPaint:
    def __init__(self, rect):
        rl.SetTraceLogLevel(rl.LOG_WARNING)
        rl.SetConfigFlags(rl.FLAG_WINDOW_TRANSPARENT | rl.FLAG_WINDOW_UNDECORATED | rl.FLAG_WINDOW_TOPMOST
                          | rl.FLAG_WINDOW_MOUSE_PASSTHROUGH | rl.FLAG_WINDOW_UNFOCUSED | rl.FLAG_WINDOW_HIDDEN
                          | rl.FLAG_VSYNC_HINT)
        rl.InitWindow(rect[2], rect[3], b"ESP overlay")
        rl.SetExitKey(rl.KEY_NULL)  # Esc in the game must not close the overlay
        self.hwnd = int(rl.ffi.cast("intptr_t", rl.GetWindowHandle()))
        no_focus(self.hwnd)  # while hidden, so the taskbar never shows a button
        self.place(rect)
        u.ShowWindow(self.hwnd, 4)  # SW_SHOWNOACTIVATE
        px = u.GetDpiForSystem() / 72 * 1.33  # tk sizes a font by its em, raylib by its line (1.33 em in Segoe UI)
        self.fonts = {pt: rl.LoadFontEx(FONT, round(pt * px), rl.ffi.NULL, 0) for pt in (9, 10)}

    def place(self, rect):
        rl.SetWindowPosition(rect[0], rect[1])
        rl.SetWindowSize(rect[2], rect[3])

    def begin(self):
        rl.BeginDrawing()
        rl.ClearBackground((0, 0, 0, 0))  # fully transparent: the game shows through

    def end(self):
        rl.EndDrawing()  # waits in the driver's present: vsync, and on this PC a driver cap of 100 a second

    def rect(self, left, top, right, bottom, color):
        rl.DrawRectangleLinesEx((left, top, right - left, bottom - top), 2, rgba(color))

    def fill(self, left, top, right, bottom, color):
        rl.DrawRectangleRec((left, top, right - left, bottom - top), rgba(color))

    def circle(self, x, y, r, color):
        rl.DrawRing((x, y), r - 1, r + 1, 0, 360, 16, rgba(color))

    def text(self, x, y, s, color, anchor, pt):
        f, b = self.fonts[pt], s.encode()
        size = f.baseSize
        if anchor == "n":
            x -= rl.MeasureTextEx(f, b, size, 0).x / 2
        else:
            y -= size / 2
        rl.DrawTextEx(f, b, (round(x), round(y)), size, 0, rgba(color))  # whole pixels: the glyphs stay sharp


class TkPaint:
    def __init__(self, root, rect):
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-transparentcolor", "black")  # black pixels show the game
        self.root, self.c = root, tk.Canvas(root, bg="black", highlightthickness=0)
        self.c.pack(fill="both", expand=True)
        self.place(rect)
        root.update()
        no_focus(u.GetParent(root.winfo_id()), LAYERED | CLICK)  # the Tk frame sits inside the real top-level window

    def place(self, rect):
        self.root.geometry(f"{rect[2]}x{rect[3]}+{rect[0]}+{rect[1]}")

    def begin(self):
        self.c.delete("all")

    def end(self):
        pass  # Tk redraws in root.update()

    def rect(self, left, top, right, bottom, color):
        self.c.create_rectangle(left, top, right, bottom, outline=color, width=2)

    def fill(self, left, top, right, bottom, color):
        self.c.create_rectangle(left, top, right, bottom, fill=color, width=0)

    def circle(self, x, y, r, color):
        self.c.create_oval(x - r, y - r, x + r, y + r, outline=color, width=2)

    def text(self, x, y, s, color, anchor, pt):
        self.c.create_text(x, y, text=s, fill=color, anchor=anchor, font=("Segoe UI", pt, "bold"))
