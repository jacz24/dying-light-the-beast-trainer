"""Small position helpers that the other modules share: sane(), flat(), fastest().

Session 9: the old live tracker of fixed session 1 addresses is gone (heap addresses change at each game start).
"""
import math


def sane(v):
    """A position: readable, finite, not huge, not all zero."""
    return v is not None and all(math.isfinite(c) and abs(c) < 1e5 for c in v) and any(v)


def flat(a, b):
    """Distance on the ground plane (x and z)."""
    return math.hypot(a[0] - b[0], a[2] - b[2])


def fastest(series, window=1.0):
    """Highest ground speed over any span of at least `window` seconds. series: [(t, vec)]."""
    best, j = 0.0, 0
    for i in range(len(series)):
        while j < len(series) and series[j][0] - series[i][0] < window:
            j += 1
        if j == len(series):
            break
        best = max(best, flat(series[i][1], series[j][1]) / (series[j][0] - series[i][0]))
    return best


assert flat((0, 5, 0), (3, 9, 4)) == 5.0
assert fastest([(0, (0, 0, 0)), (1, (3, 0, 4)), (2, (3, 0, 4))]) == 5.0
assert sane((1.0, 2.0, 3.0)) and not sane((0.0, 0.0, 0.0)) and not sane(None) and not sane((1e30, 1, 1))
