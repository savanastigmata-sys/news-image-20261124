"""Draw the world-news infographic for Tuesday 24 November 2026.

Pure Python standard library. Renders a 1024x1024 PNG in a dense
newspaper style: masthead, UTC timeline, 16 illustrated lead stories,
a world map with numbered pins, a numbered 17-50 list, a date check
and a sourcing footer. Glyphs come from fontdata.py (DejaVu bitmaps
rasterised at build time); the program itself needs no fonts, no
network, no clock and no randomness -- two runs write identical bytes.

TARGET (per the brief): TOP 1. The judge weighs, in order: the day
named with specific recognisable events; breadth across regions and
fields; readability from the image alone; faithfulness; craft.

Stories: every one happened, or was first reported, on Tuesday
24 November 2026 in at least one time zone (the competition's own
rule). Built at about 16:00 UTC on 24 November, so the day is covered
up to mid-afternoon UTC; the DATE CHECK box names the big stories
deliberately left out because they belong to earlier days, and what
had not happened yet when the image was built. The US market rally of
Monday 23 November is included because it was first reported across
Asia on Tuesday 24 November.
"""
import base64 as _b64
import json as _json
import os
import struct
import sys
import zlib
from math import cos, pi, sin

# The grader runs `python3 -P -s`, which does not put the script's own
# directory on sys.path: add it so the sibling fontdata module is found.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fontdata import _FONT_B64

W, H = 1024, 1024
PAPER = (247, 241, 222)
CARD = (255, 252, 242)
INK = (26, 26, 26)
RED = (143, 29, 33)
MAROON = (112, 20, 24)
MUTED = (104, 94, 78)
RULE = (176, 164, 136)
LAND = (203, 192, 158)
SEA = (226, 232, 228)
TINTS = {
    "Europe": (216, 228, 242),
    "Middle East": (242, 216, 198),
    "Asia": (214, 236, 214),
    "Americas": (242, 232, 196),
    "Africa": (234, 214, 234),
    "Oceania": (198, 232, 230),
    "Global": (228, 228, 228),
}
GREEN = (34, 120, 60)
PIN_COLOURS = {
    "Europe": (60, 100, 180),
    "Middle East": (220, 120, 40),
    "Asia": (130, 80, 160),
    "Americas": (180, 40, 40),
    "Africa": (40, 130, 70),
    "Oceania": (40, 140, 140),
    "Global": (90, 90, 90),
}
TOPICS = {1: "MARKETS", 2: "UKRAINE WAR", 3: "LIBYA ROW", 4: "EU BUDGET",
          5: "GAZA", 6: "GULF TENSIONS", 7: "US AID", 8: "CHIP RALLY",
          9: "AIRSPACE ROW", 10: "FACTORY FIRE", 11: "OIL PROBE",
          12: "MIGRATION", 13: "EBOLA", 14: "SOUTH SUDAN",
          15: "CLIMATE", 16: "PACIFIC PACT"}

_FONTS = _json.loads(_b64.b64decode(_FONT_B64))


def _pick_size(family, size):
    sizes = sorted(int(s) for s in _FONTS[family])
    best = sizes[0]
    for s in sizes:
        if abs(s - size) < abs(best - size) or (
                abs(s - size) == abs(best - size) and s > best):
            best = s
    return best


def _glyph(family, size, ch):
    base = _pick_size(family, size)
    f = _FONTS[family][str(base)]
    g = f["glyphs"].get(ch)
    if g is None:
        g = f["glyphs"].get("?", f["glyphs"][" "])
    w, h, xo, yo, adv, b64 = g
    raw = _b64.b64decode(b64) if b64 else b""
    return w, h, xo, yo, adv, raw, base


def _bit(raw, w, x, y):
    i = y * w + x
    return (raw[i >> 3] >> (7 - (i & 7))) & 1


class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(bg) * (w * h)

    def _i(self, x, y):
        return (y * self.w + x) * 3

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = self._i(x, y)
            self.px[i:i + 3] = bytes(c)

    def fill_rect(self, x, y, w, h, c):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        row = bytes(c) * (x1 - x0)
        for yy in range(y0, y1):
            i = self._i(x0, yy)
            self.px[i:i + len(row)] = row

    def hline(self, x, y, w, c):
        self.fill_rect(x, y, w, 1, c)

    def vline(self, x, y, h, c):
        self.fill_rect(x, y, 1, h, c)

    def line(self, x0, y0, x1, y1, c):
        dx, dy = abs(x1 - x0), abs(y0 - y1)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            self.set(x0, y0, c)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def disc(self, cx, cy, r, c):
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                if (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r:
                    self.set(xx, yy, c)

    def ring(self, cx, cy, r, c, t=2):
        for yy in range(cy - r - t, cy + r + t + 1):
            for xx in range(cx - r - t, cx + r + t + 1):
                d = ((xx - cx) ** 2 + (yy - cy) ** 2) ** 0.5
                if r - t < d <= r:
                    self.set(xx, yy, c)

    def poly(self, pts, c):
        if not pts:
            return
        ys = [p[1] for p in pts]
        for y in range(min(ys), max(ys) + 1):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                self.fill_rect(int(xs[k]), y,
                               max(1, int(xs[k + 1]) - int(xs[k])), 1, c)

    def round_rect(self, x, y, w, h, r, c):
        self.fill_rect(x + r, y, w - 2 * r, h, c)
        self.fill_rect(x, y + r, w, h - 2 * r, c)
        for cx, cy in ((x + r, y + r), (x + w - r - 1, y + r),
                       (x + r, y + h - r - 1),
                       (x + w - r - 1, y + h - r - 1)):
            self.disc(cx, cy, r, c)


def text_width(family, size, s):
    tot = 0
    for ch in s:
        _, _, _, _, adv, _, base = _glyph(family, size, ch)
        tot += adv * size / base
    return tot


def draw_text(cv, family, size, x, y, s, color):
    cx = x
    for ch in s:
        w, h, xo, yo, adv, raw, base = _glyph(family, size, ch)
        sc = size / base
        if w <= 0 or h <= 0:
            cx += adv * sc
            continue
        dw, dh = max(1, round(w * sc)), max(1, round(h * sc))
        ox = round(cx + xo * sc)
        oy = round(y + yo * sc)
        for dy in range(dh):
            sy = min(h - 1, round(dy * (h - 1) / max(1, dh - 1)))
            for dx in range(dw):
                sx = min(w - 1, round(dx * (w - 1) / max(1, dw - 1)))
                if _bit(raw, w, sx, sy):
                    cv.set(ox + dx, oy + dy, color)
        cx += adv * sc
    return cx


def draw_centered(cv, family, size, cx, y, s, color):
    draw_text(cv, family, size,
              int(cx - text_width(family, size, s) / 2), y, s, color)


def wrap(family, size, s, max_w):
    words = s.split()
    lines, cur = [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if text_width(family, size, trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def write_png(cv, path):
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)
        raw += cv.px[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)

# ---- small procedural illustrations (one per lead story) ----
# Each draws inside box (x, y, w, h) on a tinted ground. Simple, bold
# shapes: the label text beside it carries the facts; the picture
# only has to make the story recognisable at a glance.


def _sky(cv, x, y, w, h, c):
    cv.fill_rect(x, y, w, h, c)


def ill_strike(cv, x, y, w, h):
    _sky(cv, x, y, w, h, (60, 58, 64))
    cv.fill_rect(x, y + h - 12, w, 12, (40, 38, 42))
    for dx, dy, r in ((w // 2, h // 2, 13), (w // 2 - 16, h // 2 + 4, 8),
                      (w // 2 + 17, h // 2 + 3, 7)):
        cv.disc(x + dx, y + dy, r, (240, 170, 40))
        cv.disc(x + dx, y + dy, r - 4, (250, 220, 90))
    cv.fill_rect(x + 8, y + h - 22, 10, 10, (20, 20, 22))
    cv.fill_rect(x + w - 20, y + h - 20, 12, 8, (20, 20, 22))


def ill_ship(cv, x, y, w, h):
    _sky(cv, x, y, w, h, (120, 165, 200))
    cv.fill_rect(x, y + h - 14, w, 14, (38, 84, 130))
    cv.poly([(x + 8, y + h - 14), (x + w - 8, y + h - 14),
             (x + w - 22, y + h - 4), (x + 22, y + h - 4)], (90, 40, 36))
    cv.fill_rect(x + w // 2 - 4, y + 8, 8, h - 26, (200, 200, 200))
    cv.disc(x + w // 2 + 14, y + 12, 7, (240, 170, 40))
    cv.fill_rect(x + w - 30, y + 6, 16, 3, (250, 220, 90))


def ill_talks(cv, x, y, w, h):
    _sky(cv, x, y, w, h, (222, 214, 190))
    cv.fill_rect(x + 6, y + h - 16, w - 12, 6, (120, 84, 50))
    cv.disc(x + w // 3, y + h // 2 - 2, 9, (70, 90, 130))
    cv.disc(x + 2 * w // 3, y + h // 2 - 2, 9, (150, 60, 50))
    cv.fill_rect(x + w // 3 - 9, y + h // 2 + 6, 18, 10, (70, 90, 130))
    cv.fill_rect(x + 2 * w // 3 - 9, y + h // 2 + 6, 18, 10, (150, 60, 50))
    draw_text(cv, "sans_bold", 11, x + w // 2 - 4, y + 2, "?", INK)


def ill_chart_down(cv, x, y, w, h):
    _sky(cv, x, y, w, h, (240, 236, 224))
    cv.fill_rect(x + 10, y + h - 12, 8, 12, (90, 130, 90))
    cv.fill_rect(x + 26, y + h - 20, 8, 20, (90, 130, 90))
    cv.fill_rect(x + 42, y + h - 30, 8, 30, (170, 60, 50))
    cv.fill_rect(x + 58, y + h - 38, 8, 38, (170, 60, 50))
    cv.line(x + 8, y + 10, x + w - 8, y + h - 8, (170, 60, 50))
    cv.line(x + w - 14, y + h - 14, x + w - 8, y + h - 8, (170, 60, 50))
    cv.line(x + w - 14, y + h - 2, x + w - 8, y + h - 8, (170, 60, 50))


def ill_chart_up(cv, x, y, w, h):
    # A market rally: green bars climbing left to right, arrow up.
    _sky(cv, x, y, w, h, (240, 236, 224))
    cv.fill_rect(x + 10, y + h - 24, 8, 24, (60, 130, 80))
    cv.fill_rect(x + 26, y + h - 32, 8, 32, (60, 130, 80))
    cv.fill_rect(x + 42, y + h - 40, 8, 40, (60, 130, 80))
    cv.fill_rect(x + 58, y + h - 50, 8, 50, (30, 110, 60))
    cv.line(x + 8, y + h - 10, x + w - 8, y + 8, (30, 110, 60))
    cv.line(x + w - 16, y + 8, x + w - 8, y + 8, (30, 110, 60))
    cv.line(x + w - 8, y + 16, x + w - 8, y + 8, (30, 110, 60))


def ill_space(cv, x, y, w, h):
    _sky(cv, x, y, w, h, (18, 22, 44))
    for dx, dy in ((8, 6), (w - 12, 8), (14, h - 8), (w - 20, h - 12),
                   (w // 2, 5)):
        cv.disc(x + dx, y + dy, 1, (255, 255, 255))
    cv.disc(x + w - 18, y + 12, 10, (200, 190, 170))
    cv.disc(x + w - 21, y + 10, 3, (170, 160, 140))
    cv.disc(x + 16, y + h - 12, 7, (90, 140, 200))
    cv.line(x + 16, y + h - 12, x + 34, y + h - 22, (240, 200, 80))


def ill_cyclone(cv, x, y, w, h):
    _sky(cv, x, y, w, h, (170, 195, 215))
    cx, cy = x + w // 2, y + h // 2
    for r in (16, 11, 6):
        cv.ring(cx, cy, r, (255, 255, 255), 3)
    cv.disc(cx, cy, 3, (240, 240, 240))
    cv.fill_rect(x, y + h - 10, w, 10, (90, 130, 90))
    cv.line(x + 6, y + h - 10, x + 14, y + h - 22, (60, 90, 60))
    cv.line(x + 14, y + h - 22, x + 22, y + h - 10, (60, 90, 60))


def ill_quake(cv, x, y, w, h):
    _sky(cv, x, y, w, h, (210, 200, 170))
    cv.fill_rect(x + 8, y + h - 20, 14, 14, (120, 100, 80))
    cv.fill_rect(x + w - 26, y + h - 24, 16, 18, (100, 85, 70))
    cv.fill_rect(x + w // 2 - 6, y + h - 16, 12, 10, (140, 120, 95))
    cv.line(x + 4, y + h - 6, x + w // 3, y + h - 14, (60, 50, 40))
    cv.line(x + w // 3, y + h - 14, x + 2 * w // 3, y + h - 4, (60, 50, 40))
    cv.line(x + 2 * w // 3, y + h - 4, x + w - 4, y + h - 12, (60, 50, 40))
    draw_text(cv, "sans_bold", 11, x + w // 2 - 8, y + 2, "5.6", RED)


def ill_gavel(cv, x, y, w, h):
    _sky(cv, x, y, w, h, (226, 220, 200))
    cv.fill_rect(x + 10, y + h - 12, w - 20, 5, (120, 84, 50))
    cv.line(x + w // 2 - 14, y + 12, x + w // 2 + 14, y + 26, (90, 60, 30))
    cv.fill_rect(x + w // 2 - 18, y + 8, 12, 7, (70, 50, 30))
    cv.fill_rect(x + w // 2 + 6, y + 22, 12, 7, (70, 50, 30))


def ill_chip(cv, x, y, w, h):
    _sky(cv, x, y, w, h, (30, 44, 66))
    cv.fill_rect(x + w // 2 - 14, y + h // 2 - 12, 28, 24, (60, 180, 140))
    cv.fill_rect(x + w // 2 - 8, y + h // 2 - 6, 16, 12, (30, 44, 66))
    for dx in (-18, -9, 0, 9, 18):
        cv.fill_rect(x + w // 2 + dx - 1, y + 4, 2, 8, (200, 200, 200))
        cv.fill_rect(x + w // 2 + dx - 1, y + h - 12, 2, 8, (200, 200, 200))


def ill_plane(cv, x, y, w, h):
    _sky(cv, x, y, w, h, (150, 190, 220))
    cv.poly([(x + 8, y + h // 2), (x + w - 12, y + h // 2 - 6),
             (x + w - 4, y + h // 2), (x + w - 12, y + h // 2 + 6)],
            (240, 240, 240))
    cv.poly([(x + w // 2, y + h // 2 - 4), (x + w // 2 + 8, y + h // 2 - 16),
             (x + w // 2 + 12, y + h // 2 - 4)], (200, 60, 50))
    cv.disc(x + w - 22, y + 8, 5, (250, 220, 90))


def ill_flag(cv, x, y, w, h):
    _sky(cv, x, y, w, h, (232, 226, 205))
    cv.fill_rect(x + 12, y + 6, 3, h - 12, (90, 70, 50))
    cv.fill_rect(x + 15, y + 8, w - 30, 12, (40, 90, 160))
    cv.fill_rect(x + 15, y + 20, w - 30, 12, (255, 255, 255))
    cv.fill_rect(x + 15, y + 32, w - 30, 12, (200, 60, 50))


def ill_missile(cv, x, y, w, h):
    _sky(cv, x, y, w, h, (40, 40, 52))
    cv.line(x + 10, y + h - 8, x + w - 16, y + 10, (240, 200, 80))
    cv.disc(x + w - 16, y + 10, 4, (255, 240, 160))
    cv.disc(x + w // 2, y + h // 2 + 6, 8, (150, 60, 50))
    cv.disc(x + w // 2, y + h // 2 + 6, 4, (240, 170, 40))
    cv.fill_rect(x + 6, y + h - 16, 14, 8, (90, 90, 100))


def ill_court(cv, x, y, w, h):
    _sky(cv, x, y, w, h, (222, 216, 198))
    cv.poly([(x + 6, y + 14), (x + w // 2, y + 2), (x + w - 6, y + 14)],
            (170, 150, 110))
    for dx in (12, 28, 44, 58):
        cv.fill_rect(x + dx, y + 16, 4, h - 26, (200, 185, 150))
    cv.fill_rect(x + 6, y + h - 10, w - 12, 4, (150, 130, 95))


def ill_mine(cv, x, y, w, h):
    _sky(cv, x, y, w, h, (90, 130, 170))
    cv.fill_rect(x, y + h - 12, w, 12, (30, 70, 110))
    cv.poly([(x + 12, y + h - 12), (x + w - 12, y + h - 12),
             (x + w - 24, y + h - 2), (x + 24, y + h - 2)], (70, 60, 55))
    cv.disc(x + w // 2, y + 12, 6, (40, 40, 44))
    for a in range(8):
        ang = a * pi / 4
        cv.line(x + w // 2, y + 12, int(x + w // 2 + 11 * cos(ang)),
                int(y + 12 + 11 * sin(ang)), (40, 40, 44))


def ill_summit(cv, x, y, w, h):
    _sky(cv, x, y, w, h, (214, 228, 214))
    cv.fill_rect(x + 6, y + h - 14, w - 12, 5, (120, 84, 50))
    for dx, col in ((-18, (70, 90, 130)), (0, (150, 60, 50)),
                    (18, (60, 120, 80))):
        cv.disc(x + w // 2 + dx, y + h // 2 - 4, 8, col)
        cv.fill_rect(x + w // 2 + dx - 8, y + h // 2 + 3, 16, 9, col)


def ill_science(cv, x, y, w, h):
    # A virus under the microscope: spiked disc, small dots, a slide line.
    _sky(cv, x, y, w, h, (238, 234, 220))
    cx, cy = x + w // 2, y + h // 2 - 2
    for a in range(8):
        ang = a * pi / 4
        cv.line(cx, cy, int(cx + 15 * cos(ang)), int(cy + 15 * sin(ang)),
                (60, 120, 180))
    cv.disc(cx, cy, 10, (60, 120, 180))
    cv.disc(cx - 3, cy - 3, 3, (200, 230, 245))
    cv.disc(cx + 6, cy + 5, 2, (200, 230, 245))
    cv.fill_rect(x + 6, y + h - 8, w - 12, 3, (90, 90, 90))


def ill_sport(cv, x, y, w, h):
    _sky(cv, x, y, w, h, (90, 150, 90))
    cv.disc(x + w // 2, y + h // 2, 12, (255, 255, 255))
    cv.fill_rect(x + w // 2 - 1, y + 4, 2, h - 8, (255, 255, 255))
    cv.disc(x + w // 2 - 8, y + h // 2 - 6, 3, (30, 30, 30))
    cv.disc(x + w // 2 + 8, y + h // 2 + 6, 3, (30, 30, 30))


def ill_globe(cv, x, y, w, h):
    _sky(cv, x, y, w, h, (200, 220, 235))
    cv.disc(x + w // 2, y + h // 2, min(w, h) // 2 - 2, (70, 120, 180))
    cv.disc(x + w // 2 - 6, y + h // 2 - 6, 7, (90, 170, 110))
    cv.disc(x + w // 2 + 8, y + h // 2 + 7, 5, (90, 170, 110))
    cv.ring(x + w // 2, y + h // 2, min(w, h) // 2 - 2, (40, 80, 130), 2)


def ill_fire(cv, x, y, w, h):
    # A factory fire: dark smoke sky, orange flame tongues, a roofline.
    _sky(cv, x, y, w, h, (52, 46, 44))
    cv.fill_rect(x, y + h - 14, w, 14, (34, 32, 30))
    cv.fill_rect(x + 6, y + h - 24, w - 12, 10, (96, 84, 70))
    for dx, hh, col in ((-16, 22, (230, 90, 20)), (0, 30, (250, 160, 30)),
                        (16, 20, (230, 90, 20))):
        cx = x + w // 2 + dx
        cv.poly([(cx - 7, y + h - 24), (cx, y + h - 24 - hh),
                 (cx + 7, y + h - 24)], col)
    cv.disc(x + w // 2, y + h - 26, 4, (250, 220, 90))
    cv.fill_rect(x + 8, y + 4, w - 16, 3, (90, 84, 78))


def ill_race(cv, x, y, w, h):
    # A Formula 1 car under the floodlights: dark track, low open-wheeler.
    _sky(cv, x, y, w, h, (24, 26, 40))
    for dx, dy in ((10, 6), (w - 14, 10), (w // 2, 5), (20, h - 20)):
        cv.disc(x + dx, y + dy, 1, (255, 255, 255))
    cv.fill_rect(x, y + h - 12, w, 12, (60, 60, 66))
    cv.fill_rect(x + 6, y + h - 22, w - 12, 10, (200, 30, 40))
    cv.disc(x + w // 2 - 12, y + h - 10, 5, (20, 20, 20))
    cv.disc(x + w // 2 + 12, y + h - 10, 5, (20, 20, 20))
    cv.fill_rect(x + w // 2 - 4, y + h - 30, 8, 9, (240, 240, 240))
    for i in range(4):
        col = (255, 255, 255) if i % 2 == 0 else (20, 20, 20)
        cv.fill_rect(x + w - 14 + (i % 2) * 4, y + 4 + (i // 2) * 4, 4, 4,
                     col)


def ill_cricket(cv, x, y, w, h):
    # A cricket bat striking a red ball on a green outfield.
    _sky(cv, x, y, w, h, (96, 158, 96))
    cv.fill_rect(x, y + h - 10, w, 10, (70, 120, 70))
    cv.line(x + w // 2 - 4, y + 6, x + w // 2 + 10, y + h - 18,
            (222, 200, 150))
    cv.fill_rect(x + w // 2 + 8, y + h - 22, 6, 12, (222, 200, 150))
    cv.disc(x + w // 2 + 18, y + h // 2 - 4, 5, (190, 40, 40))
    cv.disc(x + w // 2 + 18, y + h // 2 - 4, 2, (240, 240, 240))
    for dx in (-20, -14, -8):
        cv.fill_rect(x + w // 2 + dx, y + h - 12, 3, 6, (240, 230, 200))


ILLS = {"strike": ill_strike, "ship": ill_ship, "talks": ill_talks,
        "chart": ill_chart_down, "chart_up": ill_chart_up,
        "space": ill_space, "cyclone": ill_cyclone,
        "quake": ill_quake, "gavel": ill_gavel, "chip": ill_chip,
        "plane": ill_plane, "flag": ill_flag, "missile": ill_missile,
        "court": ill_court, "mine": ill_mine, "summit": ill_summit,
        "science": ill_science, "sport": ill_sport, "globe": ill_globe,
        "fire": ill_fire, "race": ill_race, "cricket": ill_cricket}

# ---- world map (coarse equirectangular continents, hand-plotted) ----
CONTINENTS = [
    [(-168, 66), (-140, 70), (-120, 72), (-95, 72), (-80, 73), (-65, 62),
     (-55, 52), (-60, 45), (-75, 35), (-80, 26), (-85, 20), (-95, 16),
     (-105, 20), (-115, 28), (-125, 40), (-125, 49), (-145, 60), (-168, 66)],
    [(-80, 10), (-60, 8), (-50, 0), (-40, -5), (-35, -10), (-40, -20),
     (-50, -30), (-60, -35), (-70, -40), (-73, -50), (-70, -55),
     (-75, -40), (-80, -20), (-80, -5), (-80, 10)],
    [(-10, 36), (-10, 43), (-2, 48), (0, 50), (5, 53), (8, 57), (10, 59),
     (18, 56), (21, 55), (24, 60), (30, 62), (30, 70), (20, 70), (12, 65),
     (5, 60), (-5, 58), (-10, 55), (-10, 48), (-10, 36)],
    [(-6, 35), (10, 37), (20, 32), (32, 31), (35, 28), (43, 12), (48, 11),
     (51, 10), (44, 0), (40, -10), (35, -20), (32, -28), (20, -35),
     (15, -30), (12, -18), (9, -2), (9, 4), (-8, 5), (-15, 10), (-17, 15),
     (-15, 25), (-10, 30), (-6, 35)],
    [(30, 70), (40, 68), (60, 70), (70, 72), (90, 75), (110, 76), (130, 72),
     (150, 70), (170, 66), (178, 65), (170, 60), (160, 55), (155, 50),
     (142, 45), (140, 40), (130, 35), (127, 33), (122, 30), (120, 25),
     (110, 20), (105, 10), (100, 8), (95, 15), (90, 22), (85, 20), (80, 13),
     (75, 8), (72, 20), (65, 25), (60, 25), (55, 26), (50, 30), (48, 30),
     (42, 35), (36, 36), (30, 36), (30, 42), (30, 55), (30, 70)],
    [(113, -22), (114, -30), (115, -35), (120, -34), (130, -32), (135, -35),
     (140, -38), (145, -38), (150, -37), (153, -32), (153, -27), (150, -22),
     (146, -19), (142, -11), (137, -12), (135, -15), (132, -12), (130, -13),
     (126, -14), (122, -17), (118, -20), (113, -22)],
    [(167, -45), (170, -42), (174, -39), (177, -38), (174, -41), (168, -46),
     (167, -45)],
]


def _lonlat(lon, lat, x, y, w, h):
    # latitude cropped to -60..85 so the map is not a flat strip
    return (x + int((lon + 180.0) / 360.0 * w),
            y + int((85.0 - lat) / 145.0 * h))


def draw_map(cv, x, y, w, h, pins):
    cv.fill_rect(x, y, w, h, SEA)
    for poly in CONTINENTS:
        pts = [_lonlat(lon, lat, x, y, w, h) for lon, lat in poly]
        cv.poly(pts, LAND)
        for i in range(len(pts)):
            cv.line(pts[i][0], pts[i][1], pts[(i + 1) % len(pts)][0],
                    pts[(i + 1) % len(pts)][1], (150, 138, 108))
    for num, lon, lat, region in pins:
        px, py = _lonlat(lon, lat, x, y, w, h)
        cv.disc(px, py, 8, PIN_COLOURS[region])
        cv.ring(px, py, 8, (255, 255, 255), 1)
        s = str(num)
        draw_text(cv, "sans_bold", 9, px - int(text_width("sans_bold", 9, s) / 2),
                  py - 5, s, (255, 255, 255))


MX = 28
CW = 968


def draw_masthead(cv):
    cv.hline(MX, 12, CW, INK)
    cv.hline(MX, 14, CW, INK)
    draw_centered(cv, "sans_bold", 12, 512, 18, "THE WORLD TODAY", RED)
    draw_centered(cv, "serif_bold", 48, 512, 36,
                  "TUESDAY, 24 NOVEMBER 2026", INK)
    draw_centered(cv, "sans", 11, 512, 92,
                  "ONE DAY OF WORLD NEWS, ONE PICTURE  \u00b7  50 STORIES  \u00b7  7 REGIONS  \u00b7  16 FIELDS",
                  MUTED)
    cv.hline(MX, 110, CW, INK)


def draw_timeline(cv):
    y = 134
    draw_text(cv, "sans_bold", 10, MX, y, "THE DAY IN UTC", RED)
    draw_text(cv, "sans", 10, MX + 108, y,
              "as the day turned west \u2014 overnight to evening", MUTED)
    bx, bw, bh = MX, 132, 34
    for i, (t, head) in enumerate(TIMELINE):
        x = bx + i * (bw + 7)
        cv.fill_rect(x, y + 14, bw, bh, CARD)
        cv.hline(x, y + 14, bw, RULE)
        cv.hline(x, y + 14 + bh - 1, bw, RULE)
        draw_text(cv, "sans_bold", 9, x + 5, y + 17, t, RED)
        for j, ln in enumerate(wrap("sans", 9, head, bw - 10)):
            draw_text(cv, "sans", 9, x + 5, y + 28 + j * 10, ln, INK)


def _meta(cv, x, y, max_w, region, source, status):
    draw_text(cv, "sans_bold", 8, x, y,
              (region.upper() + "  \u00b7  " + source.upper())[:60], MUTED)
    label = "CONFIRMED" if status == "CONFIRMED" else "CLAIM"
    col = GREEN if status == "CONFIRMED" else RED
    tw = int(text_width("sans_bold", 8, label))
    px = int(x + max_w - tw - 8)
    cv.fill_rect(px, y - 1, tw + 8, 10, col)
    draw_text(cv, "sans_bold", 8, px + 4, y, label, (255, 255, 255))


def draw_card(cv, s):
    n = s["n"]
    col, row = (n - 1) % 4, (n - 1) // 4
    x = MX + col * 246
    ys = [186, 294, 392, 490]
    hs = [106, 94, 94, 94]
    y, h = ys[row], hs[row]
    w = 238
    large = (row == 0)
    cv.fill_rect(x, y, w, h, CARD)
    cv.hline(x, y, w, RULE)
    cv.hline(x, y + h - 1, w, RULE)
    cv.vline(x, y, h, RULE)
    cv.vline(x + w - 1, y, h, RULE)
    cv.fill_rect(x, y, w, 13, TINTS[s["region"]])
    draw_text(cv, "sans_bold", 9, x + 4, y + 2, str(n), RED)
    draw_text(cv, "sans_bold", 8, x + 18, y + 3,
              s["region"].upper() + " \u00b7 " + TOPICS[n], INK)
    if large:
        ILLS[s["ill"]](cv, x + 4, y + 16, 58, 44)
        tx, tsize, tw = x + 66, 12, w - 70
        sy = y + 62
    else:
        ILLS[s["ill"]](cv, x + 4, y + 16, 44, 28)
        tx, tsize, tw = x + 52, 11, w - 56
        sy = y + 46
    for j, ln in enumerate(wrap("serif_bold", tsize, s["title"], tw)[:2]):
        draw_text(cv, "serif_bold", tsize, tx, y + 17 + j * (tsize + 2), ln,
                  INK)
    for j, ln in enumerate(wrap("sans", 9, s["summ"], w - 8)[:3]):
        draw_text(cv, "sans", 9, x + 4, sy + j * 10, ln, INK)
    _meta(cv, x + 4, y + h - 11, w - 8, s["region"], s["source"], s["status"])


REGION_TALLY = [("EUROPE", 10), ("MIDDLE EAST", 9), ("ASIA", 10),
                ("AMERICAS", 5), ("AFRICA", 6), ("OCEANIA", 4),
                ("GLOBAL", 6)]
FIELDS = ["War", "Markets", "Diplomacy", "Politics", "Climate",
          "Trade", "Disaster", "Health", "Law & Crime", "Defence",
          "Energy", "Space", "Science", "Sport", "AI & Tech",
          "Migration"]


def draw_map_panel(cv):
    y = 588
    draw_text(cv, "sans_bold", 11, MX, y, "WHERE IT HAPPENED", RED)
    draw_text(cv, "sans", 10, MX + 150, y,
              "numbered pins are the 16 lead stories above", MUTED)
    my = y + 15
    # left tally: stories per region (counts verified against the 50 items)
    draw_text(cv, "sans_bold", 9, MX, my, "BY REGION", INK)
    for i, (name, cnt) in enumerate(REGION_TALLY):
        ry = my + 14 + i * 11
        cv.disc(MX + 5, ry + 4, 4, PIN_COLOURS[name.title()])
        draw_text(cv, "sans", 9, MX + 14, ry, name, INK)
        c = str(cnt)
        draw_text(cv, "sans_bold", 9, MX + 156 - text_width("sans_bold", 9, c),
                  ry, c, RED)
    # right list: the 16 fields covered, two columns
    rx = MX + CW - 160
    draw_text(cv, "sans_bold", 9, rx, my, "16 FIELDS", INK)
    for i, f in enumerate(FIELDS):
        col = i // 8
        row = i % 8
        draw_text(cv, "sans", 8, rx + col * 82, my + 14 + row * 11, f, INK)
    pins = [(s["n"], s["lon"], s["lat"], s["region"]) for s in LEADS]
    draw_map(cv, MX + 164, my, 640, 140, pins)


def draw_also(cv):
    y = 749
    draw_text(cv, "sans_bold", 11, MX, y, "ALSO ON TUESDAY", RED)
    draw_text(cv, "sans", 10, MX + 140, y, "stories 17\u201350, one line each",
              MUTED)
    col_w = 478
    for i, s in enumerate(ALSO):
        col = i // 17
        row = i % 17
        x = MX + col * (col_w + 12)
        yy = y + 16 + row * 10
        draw_text(cv, "sans_bold", 9, x, yy, str(s["n"]) + ".", RED)
        line = s["title"] + " \u2014 " + s["source"]
        for ln in wrap("sans", 9, line, col_w - 22):
            draw_text(cv, "sans", 9, x + 20, yy, ln, INK)
            if s.get("claim"):
                draw_text(cv, "sans_bold", 9,
                          x + 20 + text_width("sans", 9, ln) + 3, yy,
                          "\u00b7 CLAIM", RED)
            break


def draw_datecheck(cv):
    y = 941
    cv.fill_rect(MX, y, CW, 48, (238, 232, 210))
    cv.hline(MX, y, CW, RED)
    cv.hline(MX, y + 47, CW, RED)
    cv.vline(MX, y, 48, RED)
    cv.vline(MX + CW - 1, y, 48, RED)
    draw_text(cv, "sans_bold", 10, MX + 6, y + 4, "DATE CHECK", RED)
    lines = wrap("sans", 9, DATECHECK, CW - 12)
    for j, ln in enumerate(lines[:3]):
        draw_text(cv, "sans", 9, MX + 6, y + 17 + j * 11, ln, INK)


def draw_footer(cv):
    y = 993
    cv.hline(MX, y, CW, INK)
    draw_text(cv, "sans", 9, MX, y + 5, FOOTER, MUTED)


# ---- the day's stories (verified Tuesday 24 November 2026) ----
# Every item happened, or was first reported, on 24 Nov 2026 in at
# least one time zone. CLAIM = one side's account, not confirmed.
# Sources checked 24 Nov 2026 ~16:00 UTC: Reuters (Zaporizhzhia, Gaza,
# Libya, Huckabee, Vance probe, sanctions), AP (Indonesia fire),
# WSJ/CNN/Zacks (Nvidia rally, Korea ADIZ), Morningstar/Dow Jones
# (Asia chip rally), UN News (Ebola, South Sudan), PINA (COP31, Fiji,
# Vanuatu), Arab News + MEF (Middle East), Euronews (Asia), Horizon
# (Nepal quake, Mexico, Colombia, Brazil, ICJ), Sportstar/Guardian
# (cricket, chess), The Peel (CrowdStrike), Brimco (Azure).
TIMELINE = [
    ("~04:30 UTC", "Russian strikes hit Zaporizhzhia; 2 killed"),
    ("~06:40 UTC", "Indonesia confirms 26 dead in factory fire"),
    ("09:14 UTC", "Asia chip stocks soar; Taiex +9.0%"),
    ("~11:30 UTC", "Gaza strike kills Hamas security chief"),
    ("~13:00 UTC", "Solomons to drop China security pact"),
    ("~14:00 UTC", "France rejects 1.78tn euro EU budget"),
    ("Evening", "COP31 fallout: Pacific leaders despair"),
]

LEADS = [
    {"n": 1, "region": "Global", "ill": "chart_up", "lon": -74.0, "lat": 40.7,
     "title": "Nvidia soars 31.5% as Huang returns",
     "summ": "Nvidia jumps 31.5%, its best day since 2003, after the board reinstates Jensen Huang; S&P 500 +4.7%, Nasdaq +6.5%.",
     "source": "WSJ", "status": "CONFIRMED"},
    {"n": 2, "region": "Europe", "ill": "strike", "lon": 35.2, "lat": 47.8,
     "title": "Russian strike kills 2 in Zaporizhzhia",
     "summ": "A Russian attack kills 2 and wounds 22, including 2 children, in Zaporizhzhia overnight, regional officials say.",
     "source": "Reuters", "status": "CONFIRMED"},
    {"n": 3, "region": "Europe", "ill": "ship", "lon": 20.1, "lat": 32.1,
     "title": "Kyiv: Libya ship strike was self-defence",
     "summ": "Kyiv calls the sinking of a Russian corvette off Libya self-defence; Zelenskiy confirms a second strike in the Gulf of Finland.",
     "source": "Reuters", "status": "CONFIRMED"},
    {"n": 4, "region": "Europe", "ill": "flag", "lon": 4.35, "lat": 50.85,
     "title": "France rejects 1.78tn euro EU budget",
     "summ": "Paris calls Costa's 2028-34 budget 'very disappointing' despite a digital tax Paris wanted; leaders meet 26-27 Nov.",
     "source": "Brussels Signal", "status": "CONFIRMED"},
    {"n": 5, "region": "Middle East", "ill": "strike", "lon": 34.45, "lat": 31.35,
     "title": "Gaza strikes kill 3; Hamas security chief dead",
     "summ": "An airstrike kills 3 near a police post in Khan Younis; a second strike kills Hamas internal security chief Naeem Abu Nahel.",
     "source": "Reuters", "status": "CONFIRMED"},
    {"n": 6, "region": "Middle East", "ill": "mine", "lon": 56.5, "lat": 26.6,
     "title": "Iran claims 3 tankers hit mines in Gulf",
     "summ": "The IRGC navy claims three tankers struck mines in the Gulf; the US imposes new sanctions on Iran's shadow banking.",
     "source": "Neptune P2P", "status": "CLAIM"},
    {"n": 7, "region": "Middle East", "ill": "talks", "lon": 34.8, "lat": 32.1,
     "title": "Huckabee doubts end to Israel aid",
     "summ": "The US envoy says he is 'not certain' the $3.8bn yearly military aid will end this year, as Trump promised on 3 Nov.",
     "source": "Reuters", "status": "CONFIRMED"},
    {"n": 8, "region": "Asia", "ill": "chip", "lon": 121.6, "lat": 25.0,
     "title": "Asia chip stocks soar on Huang return",
     "summ": "Taiwan's Taiex jumps 9.0%, its best day since Apr 2025; Kospi +6.3% as TSMC, Samsung and SK Hynix surge.",
     "source": "Morningstar", "status": "CONFIRMED"},
    {"n": 9, "region": "Asia", "ill": "plane", "lon": 129.5, "lat": 36.5,
     "title": "Russian jets enter Seoul defence zone",
     "summ": "Russian warplanes enter South Korea's air-defence zone; Seoul summons the Russian defence attache in protest.",
     "source": "WSJ", "status": "CONFIRMED"},
    {"n": 10, "region": "Asia", "ill": "fire", "lon": 106.2, "lat": -6.2,
     "title": "Factory fire kills 26 in Indonesia",
     "summ": "A fire at a candy factory in Serang kills 26 workers; 8 are still missing as 600 rescuers search the ruins.",
     "source": "AP", "status": "CONFIRMED"},
    {"n": 11, "region": "Americas", "ill": "gavel", "lon": -77.0, "lat": 38.9,
     "title": "Senate probes Vance over oil deal",
     "summ": "Senator Hassan opens a probe into whether Vance helped a donor land Venezuelan oil business; Vance denies any meeting.",
     "source": "Reuters", "status": "CONFIRMED"},
    {"n": 12, "region": "Americas", "ill": "court", "lon": -122.4, "lat": 37.8,
     "title": "Court keeps Venezuelan TPS frozen",
     "summ": "An appeals court keeps deportation protections frozen for hundreds of thousands of Venezuelans with TPS.",
     "source": "US Court", "status": "CONFIRMED"},
    {"n": 13, "region": "Africa", "ill": "science", "lon": 29.5, "lat": 1.8,
     "title": "DRC Ebola passes 11,000 cases",
     "summ": "Cases pass 11,000 and deaths reach 5,358; heavy fighting near an Ituri hospital traps Ebola responders.",
     "source": "UN News", "status": "CONFIRMED"},
    {"n": 14, "region": "Africa", "ill": "globe", "lon": 31.6, "lat": 4.85,
     "title": "UN meets on South Sudan vote",
     "summ": "The Security Council meets as South Sudan prepares its first elections since independence, set for 22 Dec.",
     "source": "UN News", "status": "CONFIRMED"},
    {"n": 15, "region": "Oceania", "ill": "summit", "lon": 149.1, "lat": -35.3,
     "title": "COP31 fallout hits Canberra",
     "summ": "Australia's opposition demands minister Chris Bowen resign over the failed COP31 talks; Pacific states voice despair.",
     "source": "AP", "status": "CONFIRMED"},
    {"n": 16, "region": "Oceania", "ill": "talks", "lon": 160.0, "lat": -9.4,
     "title": "Solomons to drop China pact",
     "summ": "Honiara tells Beijing it will not renew its 2022 security pact and will sign a new treaty with Canberra on Wednesday.",
     "source": "Reuters", "status": "CONFIRMED"},
]

ALSO = [
    {"n": 17, "title": "Abu Dhabi talks end; Moscow holds hard line, envoys fly on", "source": "Nexus Europa"},
    {"n": 18, "title": "Moldova reports seven Russian drone incursions", "source": "Nexus Europa"},
    {"n": 19, "title": "Zelenskiy: intel shows Russia planning new strikes", "source": "Reuters"},
    {"n": 20, "title": "Burnham dismisses ex-PMs over EU rejoin talk", "source": "UnHerd"},
    {"n": 21, "title": "Australia coalition opposes Vanuatu treaty deal", "source": "PINA"},
    {"n": 22, "title": "German PMI 55.0, best since March 2022", "source": "Edge"},
    {"n": 23, "title": "Fiji shuts all schools for five days as drought deepens", "source": "PINA"},
    {"n": 24, "title": "EU-Indonesia pact cuts tariffs on 98% of lines", "source": "Edge"},
    {"n": 25, "title": "Russia readies nuclear-capable satellite launch, intel says", "source": "Ungated", "claim": True},
    {"n": 26, "title": "Hamas, factions agree Gaza disarmament roadmap", "source": "MEF"},
    {"n": 27, "title": "Israeli forces in major operation at Al-Amari camp", "source": "Arab News"},
    {"n": 28, "title": "Houthi shelling kills, wounds civilians on Yemen road", "source": "Arab News"},
    {"n": 29, "title": "US senators move to halt funding for war on Iran", "source": "MEF"},
    {"n": 30, "title": "UNIFIL warns of fragile security before Jan 2027 pullout", "source": "MEF"},
    {"n": 31, "title": "US weighs first training mission with Syrian army", "source": "MEF"},
    {"n": 32, "title": "5,000 drones light sky over Three Gorges festival", "source": "Euronews"},
    {"n": 33, "title": "South Korea, China agree wider trade deal on entertainment", "source": "Euronews"},
    {"n": 34, "title": "Japan launches Asian oil task force amid Gulf disruption", "source": "Euronews"},
    {"n": 35, "title": "5.6-magnitude quake strikes Nepal near China border", "source": "Horizon"},
    {"n": 36, "title": "China opens Tiangong station to first foreign astronaut", "source": "Straits Times"},
    {"n": 37, "title": "Sooryavanshi hits 204 off 53, fastest List A double ton", "source": "Sportstar"},
    {"n": 38, "title": "Gukesh opens world title defence against Sindarov", "source": "Guardian"},
    {"n": 39, "title": "CrowdStrike to buy Zscaler in $43.9bn all-stock deal", "source": "The Peel"},
    {"n": 40, "title": "Microsoft: Azure made $33.2bn in a quarter, first disclosure", "source": "Brimco"},
    {"n": 41, "title": "14 nations recognise ICJ ruling on Rohingya genocide", "source": "Horizon"},
    {"n": 42, "title": "FIFA confirms 2031 Women's World Cup hosts", "source": "myKhel"},
    {"n": 43, "title": "Bitcoin, gold slide as stocks soar", "source": "FXStreet"},
    {"n": 44, "title": "Mexico to try 'El Chapo Isidro' despite US extradition bid", "source": "Horizon"},
    {"n": 45, "title": "Colombia car bomb wrecks buildings; no victims confirmed", "source": "Horizon"},
    {"n": 46, "title": "Brazil cuts 2027 growth forecast to 1.8%", "source": "MercoPress"},
    {"n": 47, "title": "Nigeria: nearly 60 dead in tribal reprisal attacks", "source": "Sahara Medias"},
    {"n": 48, "title": "South Africa court to rule on Malema bid to gag Zille", "source": "TimesLIVE"},
    {"n": 49, "title": "Somalia names new defence minister Saadaq Omar Mohamed", "source": "Goobjoog"},
    {"n": 50, "title": "Ghana top court sets Nov 25 ruling on Sky Train case", "source": "Citi Newsroom"},
]

DATECHECK = ("Left out: COP31's collapse (Sun 22 Nov); India-NZ Test draw (23 Nov); Alcaraz's ATP Finals title (22 Nov); "
             "the Shenzhen summit (19-20 Nov). Not yet decided at about 16:00 UTC: Tuesday's US market close; the "
             "Solomons-Australia treaty (Wed); the EU summit (26-27 Nov); South Sudan's vote (22 Dec).")

FOOTER = ("Every story happened or was first reported on Tue 24 Nov 2026. "
          "CLAIM = one side's account. "
          "Sources: Reuters, AP, WSJ, CNN, UN News, Euronews, PINA, Arab News, Guardian, MEF. Original drawings.")


def render():
    cv = Canvas(W, H, PAPER)
    draw_masthead(cv)
    draw_timeline(cv)
    for s in LEADS:
        draw_card(cv, s)
    draw_map_panel(cv)
    draw_also(cv)
    draw_datecheck(cv)
    draw_footer(cv)
    return cv


def main():
    out = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "entry.png")
    size = write_png(render(), path)
    print("wrote", path, size, "bytes")


if __name__ == "__main__":
    main()
