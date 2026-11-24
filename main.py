"""Tuesday 24 November 2026, in one picture.

A deterministic, standard-library-only Python program that draws a
1024x1024 newspaper-style infographic: a masthead, a UTC timeline,
16 illustrated lead stories, a world map with numbered pins, a
numbered list of stories 17-50, a date check and a sourcing footer.

The letterforms come from fontdata.py, a 5x7 bitmap font drawn by
hand for this entry. Nothing here needs a font file, the network, a
clock or randomness: two runs write byte-identical PNGs.

Content rule for the day: every story happened, or was first
reported, on Tuesday 24 November 2026 in at least one time zone.
CLAIM marks one side's account, not an independently confirmed fact.
The page was built at about 16:00 UTC, so the DATE CHECK box names
what was deliberately left out and what had not happened yet.
"""

import os
import struct
import sys
import zlib
from math import cos, pi, sin

# `python3 -P -s` (the grader's flags) does not put the script's own
# directory on sys.path, so add it before importing the sibling font.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fontdata import advance_units, rows_for

PAGE_W, PAGE_H = 1024, 1024
MARGIN = 26
CONTENT_W = PAGE_W - 2 * MARGIN

# --- palette: warm newsprint, dark ink, one red accent ---------------
PAPER = (248, 242, 224)
CARD_BG = (255, 253, 244)
INK = (28, 28, 28)
RED = (148, 28, 32)
DARKRED = (108, 18, 22)
GREY = (106, 96, 80)
RULE = (178, 166, 138)
SEA = (228, 233, 229)
LAND = (206, 194, 160)
LAND_LINE = (152, 140, 110)
CHECK_BG = (239, 233, 212)
GREEN = (36, 118, 58)
WHITE = (255, 255, 255)

REGION_TINT = {
    "Europe": (217, 229, 243),
    "Middle East": (243, 217, 199),
    "Asia": (215, 237, 215),
    "Americas": (243, 233, 197),
    "Africa": (235, 215, 235),
    "Oceania": (199, 233, 231),
    "Global": (229, 229, 229),
}
PIN = {
    "Europe": (58, 98, 178),
    "Middle East": (218, 118, 38),
    "Asia": (128, 78, 158),
    "Americas": (178, 38, 38),
    "Africa": (38, 128, 68),
    "Oceania": (38, 138, 138),
    "Global": (88, 88, 88),
}


# --- bitmap text ------------------------------------------------------
# The font grid is 7 rows tall; `px` is the target pixel height.
# Glyphs are sampled with nearest neighbour, and bold is a second
# pass shifted by a fraction of the scale.

def text_w(s, px):
    """Pixel width of string s at height px."""
    scale = px / 7.0
    return sum(advance_units(ch) for ch in s) * scale


def _paint_glyph(sheet, rows, px, ox, oy, colour):
    scale = px / 7.0
    gw = max(1, int(round(5 * scale)))
    gh = int(round(px))
    for dy in range(gh):
        src_y = min(6, int(dy * 7 / gh))
        row = rows[src_y]
        for dx in range(gw):
            src_x = min(4, int(dx * 5 / gw))
            if row[src_x] == "1":
                sheet.put(ox + dx, oy + dy, colour)


def put_text(sheet, s, px, x, y, colour, bold=False):
    """Draw s with its top at (x, y); returns the x after the last glyph."""
    cx = float(x)
    shift = max(1, int(round(px / 7.0 * 0.35))) if bold else 0
    for ch in s:
        rows = rows_for(ch)
        _paint_glyph(sheet, rows, px, int(round(cx)), y, colour)
        if bold:
            _paint_glyph(sheet, rows, px, int(round(cx)) + shift, y, colour)
        cx += advance_units(ch) * px / 7.0
    return cx


def put_centred(sheet, s, px, centre_x, y, colour, bold=False):
    put_text(sheet, s, px, int(centre_x - text_w(s, px) / 2), y, colour, bold)


def flow_text(s, px, max_w):
    """Greedy word wrap; returns a list of lines that fit max_w."""
    lines = []
    current = ""
    for word in s.split():
        trial = (current + " " + word).strip()
        if text_w(trial, px) <= max_w or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# --- pixel sheet ------------------------------------------------------

class Sheet:
    """An RGB pixel buffer with small drawing primitives."""

    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.buf = bytearray(bg) * (w * h)

    def put(self, x, y, colour):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.buf[i:i + 3] = bytes(colour)

    def box(self, x, y, w, h, colour):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        stripe = bytes(colour) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.buf[i:i + len(stripe)] = stripe

    def hrule(self, x, y, w, colour):
        self.box(x, y, w, 1, colour)

    def vrule(self, x, y, h, colour):
        self.box(x, y, 1, h, colour)

    def segment(self, x0, y0, x1, y1, colour):
        """Bresenham line between two points."""
        dx, dy = abs(x1 - x0), abs(y0 - y1)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            self.put(x0, y0, colour)
            if x0 == x1 and y0 == y1:
                return
            step = 2 * err
            if step > -dy:
                err -= dy
                x0 += sx
            if step < dx:
                err += dx
                y0 += sy

    def blob(self, cx, cy, r, colour):
        """Filled disc of radius r centred on (cx, cy)."""
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                if (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r:
                    self.put(xx, yy, colour)

    def halo(self, cx, cy, r, colour, thick=2):
        for yy in range(cy - r - thick, cy + r + thick + 1):
            for xx in range(cx - r - thick, cx + r + thick + 1):
                d = ((xx - cx) ** 2 + (yy - cy) ** 2) ** 0.5
                if r - thick < d <= r:
                    self.put(xx, yy, colour)

    def fill_poly(self, pts, colour):
        """Scanline fill of a polygon given as [(x, y), ...]."""
        if not pts:
            return
        ys = [p[1] for p in pts]
        for y in range(min(ys), max(ys) + 1):
            hits = []
            n = len(pts)
            for i in range(n):
                ax, ay = pts[i]
                bx, by = pts[(i + 1) % n]
                if (ay <= y < by) or (by <= y < ay):
                    hits.append(ax + (y - ay) * (bx - ax) / (by - ay))
            hits.sort()
            for k in range(0, len(hits) - 1, 2):
                xa, xb = int(hits[k]), int(hits[k + 1])
                if xb > xa:
                    self.box(xa, y, xb - xa, 1, colour)


# --- PNG output -------------------------------------------------------

def save_png(sheet, path):
    raw = bytearray()
    stride = sheet.w * 3
    for y in range(sheet.h):
        raw.append(0)
        raw += sheet.buf[y * stride:(y + 1) * stride]
    payload = zlib.compress(bytes(raw), 9)

    def _chunk(tag, data):
        head = struct.pack(">I", len(data)) + tag + data
        return head + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR",
                  struct.pack(">IIBBBBB", sheet.w, sheet.h, 8, 2, 0, 0, 0))
    png += _chunk(b"IDAT", payload)
    png += _chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)
    return len(png)


# --- one small original drawing per lead story ------------------------
# Each painter works inside (x, y, w, h). Bold flat shapes on a tinted
# ground: the headline beside it carries the facts, the picture only
# has to make the story recognisable at a glance.


def _ground(sheet, x, y, w, h, colour):
    sheet.box(x, y, w, h, colour)


def pic_burst(sheet, x, y, w, h):
    """Night explosion: dark sky, orange fireballs, rooftops."""
    _ground(sheet, x, y, w, h, (62, 58, 66))
    sheet.box(x, y + h - 12, w, 12, (38, 36, 40))
    for dx, dy, r in ((w // 2, h // 2, 12), (w // 2 - 17, h // 2 + 5, 8),
                      (w // 2 + 18, h // 2 + 4, 7)):
        sheet.blob(x + dx, y + dy, r, (238, 168, 42))
        sheet.blob(x + dx, y + dy, r - 4, (250, 222, 92))
    sheet.box(x + 9, y + h - 23, 10, 11, (22, 22, 24))
    sheet.box(x + w - 21, y + h - 21, 12, 9, (22, 22, 24))


def pic_tanker(sheet, x, y, w, h):
    """A hull on the water under a signal sun."""
    _ground(sheet, x, y, w, h, (118, 164, 199))
    sheet.box(x, y + h - 14, w, 14, (36, 82, 128))
    sheet.fill_poly([(x + 8, y + h - 14), (x + w - 8, y + h - 14),
                     (x + w - 22, y + h - 4), (x + 22, y + h - 4)],
                    (92, 42, 38))
    sheet.box(x + w // 2 - 4, y + 8, 8, h - 26, (198, 198, 198))
    sheet.blob(x + w // 2 + 15, y + 12, 7, (238, 168, 42))
    sheet.box(x + w - 31, y + 6, 16, 3, (250, 222, 92))


def pic_parley(sheet, x, y, w, h):
    """Two negotiators across a table, one question hanging over them."""
    _ground(sheet, x, y, w, h, (223, 215, 191))
    sheet.box(x + 6, y + h - 16, w - 12, 6, (118, 82, 48))
    sheet.blob(x + w // 3, y + h // 2 - 2, 9, (68, 88, 128))
    sheet.blob(x + 2 * w // 3, y + h // 2 - 2, 9, (148, 58, 48))
    sheet.box(x + w // 3 - 9, y + h // 2 + 6, 18, 10, (68, 88, 128))
    sheet.box(x + 2 * w // 3 - 9, y + h // 2 + 6, 18, 10, (148, 58, 48))
    put_text(sheet, "?", 11, x + w // 2 - 3, y + 3, INK, bold=True)


def pic_bars_down(sheet, x, y, w, h):
    """Falling bars with a red down-trend line."""
    _ground(sheet, x, y, w, h, (241, 237, 225))
    for bx, frac in ((10, 0.35), (26, 0.55), (42, 0.75), (58, 0.95)):
        bh = max(3, int(h * frac))
        sheet.box(x + bx, y + h - bh, 8, bh,
                  (88, 128, 88) if frac < 0.7 else (168, 58, 48))
    sheet.segment(x + 8, y + 8, x + w - 8, y + h - 6, (168, 58, 48))
    sheet.segment(x + w - 15, y + h - 13, x + w - 8, y + h - 6, (168, 58, 48))
    sheet.segment(x + w - 15, y + h - 1, x + w - 8, y + h - 6, (168, 58, 48))


def pic_bars_up(sheet, x, y, w, h):
    """Climbing green bars with an up-trend arrow."""
    _ground(sheet, x, y, w, h, (241, 237, 225))
    for bx, frac in ((10, 0.45), (26, 0.60), (42, 0.75), (58, 0.90)):
        bh = max(3, int(h * frac))
        sheet.box(x + bx, y + h - bh, 8, bh,
                  (58, 128, 78) if frac < 0.85 else (28, 108, 58))
    sheet.segment(x + 8, y + h - 8, x + w - 8, y + 6, (28, 108, 58))
    sheet.segment(x + w - 17, y + 6, x + w - 8, y + 6, (28, 108, 58))
    sheet.segment(x + w - 8, y + 15, x + w - 8, y + 6, (28, 108, 58))


def pic_orbit(sheet, x, y, w, h):
    """A station, a moon and a planet in a starry sky."""
    _ground(sheet, x, y, w, h, (18, 22, 44))
    for dx, dy in ((8, 6), (w - 12, 8), (14, h - 8), (w - 20, h - 12),
                   (w // 2, 5)):
        sheet.blob(x + dx, y + dy, 1, WHITE)
    sheet.blob(x + w - 18, y + 12, 10, (198, 188, 168))
    sheet.blob(x + w - 21, y + 10, 3, (168, 158, 138))
    sheet.blob(x + 16, y + h - 12, 7, (88, 138, 198))
    sheet.segment(x + 16, y + h - 12, x + 34, y + h - 22, (238, 198, 78))


def pic_storm(sheet, x, y, w, h):
    """A cyclone spiral over a green coastline."""
    _ground(sheet, x, y, w, h, (168, 194, 214))
    cx, cy = x + w // 2, y + h // 2
    for r in (12, 8, 4):
        sheet.halo(cx, cy, r, WHITE, 3)
    sheet.blob(cx, cy, 3, (238, 238, 238))
    sheet.box(x, y + h - 10, w, 10, (88, 128, 88))
    sheet.segment(x + 6, y + h - 10, x + 14, y + h - 22, (58, 88, 58))
    sheet.segment(x + 14, y + h - 22, x + 22, y + h - 10, (58, 88, 58))


def pic_tremor(sheet, x, y, w, h):
    """Cracked ground between rooftops, magnitude on the wall."""
    _ground(sheet, x, y, w, h, (211, 201, 171))
    sheet.box(x + 8, y + h - 20, 14, 14, (118, 98, 78))
    sheet.box(x + w - 26, y + h - 24, 16, 18, (98, 83, 68))
    sheet.box(x + w // 2 - 6, y + h - 16, 12, 10, (138, 118, 93))
    sheet.segment(x + 4, y + h - 6, x + w // 3, y + h - 14, (58, 48, 38))
    sheet.segment(x + w // 3, y + h - 14, x + 2 * w // 3, y + h - 4,
                  (58, 48, 38))
    sheet.segment(x + 2 * w // 3, y + h - 4, x + w - 4, y + h - 12,
                  (58, 48, 38))
    put_text(sheet, "5.6", 11, x + w // 2 - 8, y + 3, RED, bold=True)


def pic_bench(sheet, x, y, w, h):
    """A judge's gavel over its sounding block."""
    _ground(sheet, x, y, w, h, (227, 221, 201))
    sheet.box(x + 10, y + h - 12, w - 20, 5, (118, 82, 48))
    sheet.segment(x + w // 2 - 14, y + 12, x + w // 2 + 14, y + 26,
                  (88, 58, 28))
    sheet.box(x + w // 2 - 18, y + 8, 12, 7, (68, 48, 28))
    sheet.box(x + w // 2 + 6, y + 22, 12, 7, (68, 48, 28))


def pic_silicon(sheet, x, y, w, h):
    """A chip on a dark board, pins top and bottom."""
    _ground(sheet, x, y, w, h, (30, 44, 66))
    sheet.box(x + w // 2 - 14, y + h // 2 - 12, 28, 24, (58, 178, 138))
    sheet.box(x + w // 2 - 8, y + h // 2 - 6, 16, 12, (30, 44, 66))
    for dx in (-18, -9, 0, 9, 18):
        sheet.box(x + w // 2 + dx - 1, y + 4, 2, 8, (198, 198, 198))
        sheet.box(x + w // 2 + dx - 1, y + h - 12, 2, 8, (198, 198, 198))


def pic_jet(sheet, x, y, w, h):
    """A jet crossing a pale sky, sun high on the right."""
    _ground(sheet, x, y, w, h, (148, 188, 218))
    sheet.fill_poly([(x + 8, y + h // 2), (x + w - 12, y + h // 2 - 6),
                     (x + w - 4, y + h // 2), (x + w - 12, y + h // 2 + 6)],
                    (238, 238, 238))
    sheet.fill_poly([(x + w // 2, y + h // 2 - 4),
                     (x + w // 2 + 8, y + h // 2 - 11),
                     (x + w // 2 + 12, y + h // 2 - 4)], (198, 58, 48))
    sheet.blob(x + w - 22, y + 8, 5, (250, 222, 92))


def pic_banner(sheet, x, y, w, h):
    """A tricolour flag on a pole against a pale sky."""
    _ground(sheet, x, y, w, h, (233, 227, 206))
    sheet.box(x + 12, y + 4, 3, h - 8, (88, 68, 48))
    sh = (h - 12) // 3
    sheet.box(x + 15, y + 6, w - 30, sh, (38, 88, 158))
    sheet.box(x + 15, y + 6 + sh, w - 30, sh, WHITE)
    sheet.box(x + 15, y + 6 + 2 * sh, w - 30, h - 12 - 2 * sh,
              (198, 58, 48))


def pic_rocket(sheet, x, y, w, h):
    """A missile streaking up, a launch pad below."""
    _ground(sheet, x, y, w, h, (40, 40, 52))
    sheet.segment(x + 10, y + h - 8, x + w - 16, y + 10, (238, 198, 78))
    sheet.blob(x + w - 16, y + 10, 4, (255, 240, 160))
    sheet.blob(x + w // 2, y + h // 2 + 6, 8, (148, 58, 48))
    sheet.blob(x + w // 2, y + h // 2 + 6, 4, (238, 168, 42))
    sheet.box(x + 6, y + h - 16, 14, 8, (88, 88, 98))


def pic_columns(sheet, x, y, w, h):
    """A courthouse: pediment roof, four columns, steps."""
    _ground(sheet, x, y, w, h, (223, 217, 199))
    sheet.fill_poly([(x + 6, y + 14), (x + w // 2, y + 2),
                     (x + w - 6, y + 14)], (168, 148, 108))
    for dx in (12, 28, 44, 58):
        sheet.box(x + dx, y + 16, 4, h - 26, (198, 183, 148))
    sheet.box(x + 6, y + h - 10, w - 12, 4, (148, 128, 93))


def pic_seamine(sheet, x, y, w, h):
    """A spiked sea mine above a dark hull silhouette."""
    _ground(sheet, x, y, w, h, (88, 128, 168))
    sheet.box(x, y + h - 12, w, 12, (28, 68, 108))
    sheet.fill_poly([(x + 12, y + h - 12), (x + w - 12, y + h - 12),
                     (x + w - 24, y + h - 2), (x + 24, y + h - 2)],
                    (68, 58, 53))
    for a in range(8):
        ang = a * pi / 4
        sheet.segment(x + w // 2, y + 12,
                      int(x + w // 2 + 11 * cos(ang)),
                      int(y + 12 + 11 * sin(ang)), (38, 38, 42))
    sheet.blob(x + w // 2, y + 12, 6, (38, 38, 42))


def pic_leaders(sheet, x, y, w, h):
    """Three leaders at a summit table."""
    _ground(sheet, x, y, w, h, (215, 229, 215))
    sheet.box(x + 6, y + h - 14, w - 12, 5, (118, 82, 48))
    for dx, col in ((-18, (68, 88, 128)), (0, (148, 58, 48)),
                    (18, (58, 118, 78))):
        sheet.blob(x + w // 2 + dx, y + h // 2 - 4, 8, col)
        sheet.box(x + w // 2 + dx - 8, y + h // 2 + 3, 16, 9, col)


def pic_microbe(sheet, x, y, w, h):
    """A spiked virus under the microscope, on a slide."""
    _ground(sheet, x, y, w, h, (239, 235, 221))
    cx, cy = x + w // 2, y + h // 2 - 2
    for a in range(8):
        ang = a * pi / 4
        sheet.segment(cx, cy, int(cx + 11 * cos(ang)),
                      int(cy + 11 * sin(ang)), (58, 118, 178))
    sheet.blob(cx, cy, 10, (58, 118, 178))
    sheet.blob(cx - 3, cy - 3, 3, (198, 228, 243))
    sheet.blob(cx + 6, cy + 5, 2, (198, 228, 243))
    sheet.box(x + 6, y + h - 8, w - 12, 3, (88, 88, 88))


def pic_pitch(sheet, x, y, w, h):
    """A football pitch from above: green, line, two players."""
    _ground(sheet, x, y, w, h, (88, 148, 88))
    sheet.blob(x + w // 2, y + h // 2, 12, WHITE)
    sheet.box(x + w // 2 - 1, y + 4, 2, h - 8, WHITE)
    sheet.blob(x + w // 2 - 8, y + h // 2 - 6, 3, (28, 28, 28))
    sheet.blob(x + w // 2 + 8, y + h // 2 + 6, 3, (28, 28, 28))


def pic_planet(sheet, x, y, w, h):
    """A small globe: blue sea, green land, a thin orbit ring."""
    _ground(sheet, x, y, w, h, (198, 218, 233))
    r = min(w, h) // 2 - 2
    sheet.blob(x + w // 2, y + h // 2, r, (68, 118, 178))
    sheet.blob(x + w // 2 - 6, y + h // 2 - 6, 7, (88, 168, 108))
    sheet.blob(x + w // 2 + 8, y + h // 2 + 7, 5, (88, 168, 108))
    sheet.halo(x + w // 2, y + h // 2, r, (38, 78, 128), 2)


def pic_blaze(sheet, x, y, w, h):
    """A factory fire: smoke sky, three flame tongues, a roofline."""
    _ground(sheet, x, y, w, h, (52, 46, 44))
    sheet.box(x, y + h - 10, w, 10, (32, 30, 28))
    sheet.box(x + 6, y + h - 18, w - 12, 8, (94, 82, 68))
    base = y + h - 18
    for dx, hh, col in ((-16, 8, (228, 88, 18)), (0, 12, (248, 158, 28)),
                        (16, 8, (228, 88, 18))):
        cx = x + w // 2 + dx
        sheet.fill_poly([(cx - 6, base), (cx, base - hh),
                         (cx + 6, base)], col)
    sheet.blob(x + w // 2, base - 2, 3, (250, 222, 92))
    sheet.box(x + 8, y + 4, w - 16, 3, (88, 82, 76))


def pic_speed(sheet, x, y, w, h):
    """A red open-wheeler under floodlights on a dark track."""
    _ground(sheet, x, y, w, h, (24, 26, 40))
    for dx, dy in ((10, 6), (w - 14, 10), (w // 2, 5), (20, h - 20)):
        sheet.blob(x + dx, y + dy, 1, WHITE)
    sheet.box(x, y + h - 12, w, 12, (58, 58, 64))
    sheet.box(x + 6, y + h - 22, w - 12, 10, (198, 28, 38))
    sheet.blob(x + w // 2 - 12, y + h - 10, 5, (18, 18, 18))
    sheet.blob(x + w // 2 + 12, y + h - 10, 5, (18, 18, 18))
    sheet.box(x + w // 2 - 4, y + h - 26, 8, 9, (238, 238, 238))
    for i in range(4):
        col = WHITE if i % 2 == 0 else (18, 18, 18)
        sheet.box(x + w - 14 + (i % 2) * 4, y + 4 + (i // 2) * 4, 4, 4, col)


def pic_bat(sheet, x, y, w, h):
    """A cricket bat meeting a red ball on the outfield."""
    _ground(sheet, x, y, w, h, (94, 156, 94))
    sheet.box(x, y + h - 10, w, 10, (68, 118, 68))
    sheet.segment(x + w // 2 - 4, y + 6, x + w // 2 + 10, y + h - 18,
                  (220, 198, 148))
    sheet.box(x + w // 2 + 8, y + h - 22, 6, 12, (220, 198, 148))
    sheet.blob(x + w // 2 + 18, y + h // 2 - 4, 5, (188, 38, 38))
    sheet.blob(x + w // 2 + 18, y + h // 2 - 4, 2, (238, 238, 238))
    for dx in (-20, -14, -8):
        sheet.box(x + w // 2 + dx, y + h - 12, 3, 6, (238, 228, 198))


PICTURES = {
    "burst": pic_burst, "tanker": pic_tanker, "parley": pic_parley,
    "bars_down": pic_bars_down, "bars_up": pic_bars_up,
    "orbit": pic_orbit, "storm": pic_storm, "tremor": pic_tremor,
    "bench": pic_bench, "silicon": pic_silicon, "jet": pic_jet,
    "banner": pic_banner, "rocket": pic_rocket, "columns": pic_columns,
    "seamine": pic_seamine, "leaders": pic_leaders,
    "microbe": pic_microbe, "pitch": pic_pitch, "planet": pic_planet,
    "blaze": pic_blaze, "speed": pic_speed, "bat": pic_bat,
}


# --- world map --------------------------------------------------------
# Coarse equirectangular continents, plotted by hand from a world
# atlas in my head: latitude is cropped to -60..85 so the map reads
# as a band rather than a flat strip.

LANDMASSES = [
    # North America
    [(-168, 66), (-150, 70), (-130, 71), (-110, 68), (-95, 69),
     (-85, 66), (-75, 62), (-65, 60), (-60, 52), (-55, 47), (-65, 44),
     (-70, 42), (-75, 38), (-80, 32), (-81, 26), (-84, 30), (-90, 21),
     (-97, 16), (-105, 20), (-110, 24), (-117, 33), (-125, 40),
     (-124, 48), (-135, 58), (-155, 58), (-168, 66)],
    # South America
    [(-79, 9), (-72, 11), (-62, 10), (-52, 5), (-50, 0), (-44, -3),
     (-35, -8), (-38, -15), (-40, -22), (-48, -28), (-57, -35),
     (-65, -41), (-70, -50), (-73, -54), (-70, -45), (-73, -37),
     (-80, -30), (-81, -20), (-80, -12), (-79, -5), (-79, 9)],
    # Europe
    [(-10, 36), (-9, 43), (-2, 48), (-1, 50), (3, 52), (8, 57),
     (10, 59), (18, 56), (21, 55), (24, 59), (30, 60), (30, 66),
     (25, 71), (18, 70), (12, 66), (5, 60), (-5, 58), (-10, 54),
     (-10, 44), (-10, 36)],
    # Africa
    [(-6, 35), (0, 36), (10, 37), (20, 32), (30, 31), (35, 28),
     (43, 12), (48, 11), (51, 12), (46, 5), (41, -2), (40, -10),
     (35, -18), (32, -26), (26, -34), (19, -35), (15, -27), (12, -18),
     (9, -4), (9, 4), (-8, 5), (-13, 8), (-17, 15), (-16, 21),
     (-15, 27), (-10, 31), (-6, 35)],
    # Asia
    [(30, 36), (36, 36), (42, 35), (48, 30), (50, 29), (56, 26),
     (60, 25), (66, 25), (72, 20), (76, 8), (80, 7), (80, 13),
     (85, 19), (90, 22), (95, 16), (100, 8), (105, 2), (103, 8),
     (108, 12), (110, 20), (114, 22), (120, 25), (122, 30), (127, 33),
     (130, 35), (135, 40), (140, 42), (142, 45), (150, 59), (158, 52),
     (162, 56), (170, 60), (178, 65), (170, 66), (160, 62), (155, 55),
     (150, 60), (140, 72), (130, 72), (120, 73), (110, 74), (100, 76),
     (90, 75), (80, 73), (70, 72), (60, 69), (50, 68), (40, 68),
     (32, 70), (30, 66), (30, 60), (30, 55), (30, 42), (30, 36)],
    # Indonesia / New Guinea
    [(95, 5), (100, 0), (105, -5), (110, -7), (115, -8), (120, -10),
     (125, -9), (130, -3), (135, -4), (140, -8), (140, -2), (135, 0),
     (130, 0), (125, 1), (120, 0), (115, 0), (110, 0), (105, 5),
     (100, 5), (95, 5)],
    # Australia
    [(113, -22), (114, -32), (115, -35), (124, -33), (129, -32),
     (135, -35), (140, -38), (145, -38), (150, -37), (153, -32),
     (153, -27), (150, -23), (146, -19), (142, -11), (137, -12),
     (135, -15), (132, -12), (130, -13), (126, -14), (122, -17),
     (118, -20), (113, -22)],
    # New Zealand
    [(167, -45), (170, -42), (174, -39), (177, -38), (175, -41),
     (170, -43), (167, -46), (167, -45)],
]


def _project(lon, lat, x, y, w, h):
    return (x + int((lon + 180.0) / 360.0 * w),
            y + int((85.0 - lat) / 145.0 * h))


# (dx, dy) pixel nudges for pins whose true spots collide on this
# small map: 1 New York vs 11 Washington, 5 Gaza vs 7 Tel Aviv,
# 13 DRC vs 14 South Sudan, 9 Seoul vs 8 Taipei.
PIN_NUDGE = {1: (16, -10), 5: (-13, 10), 7: (13, -10), 9: (9, -7),
             13: (-16, 7), 14: (11, -7)}


def paint_map(sheet, x, y, w, h, pins):
    sheet.box(x, y, w, h, SEA)
    for land in LANDMASSES:
        pts = [_project(lon, lat, x, y, w, h) for lon, lat in land]
        sheet.fill_poly(pts, LAND)
        for i in range(len(pts)):
            ax, ay = pts[i]
            bx, by = pts[(i + 1) % len(pts)]
            sheet.segment(ax, ay, bx, by, LAND_LINE)
    for num, lon, lat, region in pins:
        px, py = _project(lon, lat, x, y, w, h)
        dx, dy = PIN_NUDGE.get(num, (0, 0))
        if (dx, dy) != (0, 0):
            sheet.segment(px, py, px + dx, py + dy, PIN[region])
            px, py = px + dx, py + dy
        sheet.blob(px, py, 8, PIN[region])
        sheet.halo(px, py, 8, WHITE, 1)
        label = str(num)
        put_text(sheet, label, 9, px - int(text_w(label, 9) / 2), py - 5,
                 WHITE, bold=True)


# --- the day's stories ------------------------------------------------
# Every item happened, or was first reported, on Tuesday 24 November
# 2026 in at least one time zone. CLAIM = one side's account, not
# independently confirmed. Sources were checked on 24 Nov 2026 at
# about 16:00 UTC.

DAY_EVENTS = [
    ("~04:30 UTC", "Zaporizhzhia hit; 2 killed"),
    ("~06:40 UTC", "Factory fire kills 26 in Indonesia"),
    ("09:14 UTC", "Asia chip stocks soar; Taiex +9.0%"),
    ("~11:30 UTC", "Gaza strike kills Hamas security chief"),
    ("~13:00 UTC", "Solomons to drop China security pact"),
    ("~14:00 UTC", "France rejects 1.78tn euro EU budget"),
    ("Evening", "COP31 fallout: Pacific despair"),
]

FIELD_FOR_STORY = {
    1: "MARKETS", 2: "UKRAINE WAR", 3: "LIBYA ROW", 4: "EU BUDGET",
    5: "GAZA", 6: "GULF TENSIONS", 7: "US AID", 8: "CHIP RALLY",
    9: "AIRSPACE ROW", 10: "FACTORY FIRE", 11: "OIL PROBE",
    12: "MIGRATION", 13: "EBOLA", 14: "SOUTH SUDAN",
    15: "CLIMATE", 16: "PACIFIC PACT",
}

LEAD_STORIES = [
    {"n": 1, "region": "Global", "pic": "bars_up", "lon": -74.0, "lat": 40.7,
     "title": "Nvidia soars 31.5% as Huang returns",
     "body": "Nvidia jumps 31.5%, its best day since 2003, after the board reinstates Jensen Huang; S&P 500 +4.7%, Nasdaq +6.5%.",
     "source": "WSJ", "status": "CONFIRMED"},
    {"n": 2, "region": "Europe", "pic": "burst", "lon": 35.2, "lat": 47.8,
     "title": "Russian strike kills 2 in Zaporizhzhia",
     "body": "A Russian attack kills 2 and wounds 22, including 2 children, in Zaporizhzhia overnight, regional officials say.",
     "source": "Reuters", "status": "CONFIRMED"},
    {"n": 3, "region": "Europe", "pic": "tanker", "lon": 20.1, "lat": 32.1,
     "title": "Kyiv: Libya ship strike was self-defence",
     "body": "Kyiv calls the sinking of a Russian corvette off Libya self-defence; Zelenskiy confirms a second Gulf of Finland strike.",
     "source": "Reuters", "status": "CONFIRMED"},
    {"n": 4, "region": "Europe", "pic": "banner", "lon": 4.35, "lat": 50.85,
     "title": "France rejects 1.78tn euro EU budget",
     "body": "Paris calls Costa's 2028-34 budget 'very disappointing' despite a digital tax Paris wanted; leaders meet 26-27 Nov.",
     "source": "Brussels Signal", "status": "CONFIRMED"},
    {"n": 5, "region": "Middle East", "pic": "burst", "lon": 34.45, "lat": 31.35,
     "title": "Gaza strikes kill Hamas security chief",
     "body": "An airstrike kills 3 near a police post in Khan Younis; a second strike kills Hamas internal security chief Naeem Abu Nahel.",
     "source": "Reuters", "status": "CONFIRMED"},
    {"n": 6, "region": "Middle East", "pic": "seamine", "lon": 56.5, "lat": 26.6,
     "title": "Iran claims 3 tankers hit mines in Gulf",
     "body": "The IRGC navy claims three tankers struck mines in the Gulf; the US imposes new sanctions on Iran's shadow banking.",
     "source": "Neptune P2P", "status": "CLAIM"},
    {"n": 7, "region": "Middle East", "pic": "parley", "lon": 34.8, "lat": 32.1,
     "title": "Huckabee doubts end to Israel aid",
     "body": "The US envoy says he is 'not certain' the $3.8bn yearly military aid will end this year, as Trump promised on 3 Nov.",
     "source": "Reuters", "status": "CONFIRMED"},
    {"n": 8, "region": "Asia", "pic": "silicon", "lon": 121.6, "lat": 25.0,
     "title": "Asia chip stocks soar on Huang return",
     "body": "Taiwan's Taiex jumps 9.0%, its best day since Apr 2025; Kospi +6.3% as TSMC, Samsung and SK Hynix surge.",
     "source": "Morningstar", "status": "CONFIRMED"},
    {"n": 9, "region": "Asia", "pic": "jet", "lon": 129.5, "lat": 36.5,
     "title": "Russian jets enter Seoul defence zone",
     "body": "Russian warplanes enter South Korea's air-defence zone; Seoul summons the Russian defence attache in protest.",
     "source": "WSJ", "status": "CONFIRMED"},
    {"n": 10, "region": "Asia", "pic": "blaze", "lon": 106.2, "lat": -6.2,
     "title": "Factory fire kills 26 in Indonesia",
     "body": "A fire at a candy factory in Serang kills 26 workers; 8 are still missing as 600 rescuers search the ruins.",
     "source": "AP", "status": "CONFIRMED"},
    {"n": 11, "region": "Americas", "pic": "bench", "lon": -77.0, "lat": 38.9,
     "title": "Senate probes Vance over oil deal",
     "body": "Senator Hassan probes whether Vance helped a donor land Venezuelan oil business; Vance denies any meeting.",
     "source": "Reuters", "status": "CONFIRMED"},
    {"n": 12, "region": "Americas", "pic": "columns", "lon": -122.4, "lat": 37.8,
     "title": "Court keeps Venezuelan TPS frozen",
     "body": "An appeals court keeps deportation protections frozen for hundreds of thousands of Venezuelans with TPS.",
     "source": "US Court", "status": "CONFIRMED"},
    {"n": 13, "region": "Africa", "pic": "microbe", "lon": 29.5, "lat": 1.8,
     "title": "DRC Ebola passes 11,000 cases",
     "body": "Cases pass 11,000 and deaths reach 5,358; heavy fighting near an Ituri hospital traps Ebola responders.",
     "source": "UN News", "status": "CONFIRMED"},
    {"n": 14, "region": "Africa", "pic": "planet", "lon": 31.6, "lat": 4.85,
     "title": "UN meets on South Sudan vote",
     "body": "The Security Council meets as South Sudan prepares its first elections since independence, set for 22 Dec.",
     "source": "UN News", "status": "CONFIRMED"},
    {"n": 15, "region": "Oceania", "pic": "leaders", "lon": 149.1, "lat": -35.3,
     "title": "COP31 fallout hits Canberra",
     "body": "Australia's opposition demands minister Chris Bowen resign over the failed COP31 talks; Pacific states voice despair.",
     "source": "AP", "status": "CONFIRMED"},
    {"n": 16, "region": "Oceania", "pic": "parley", "lon": 160.0, "lat": -9.4,
     "title": "Solomons to drop China pact",
     "body": "Honiara tells Beijing it will not renew its 2022 security pact and will sign a new treaty with Canberra on Wednesday.",
     "source": "Reuters", "status": "CONFIRMED"},
]

MORE_STORIES = [
    (17, "Abu Dhabi talks end; Moscow holds hard line, envoys fly on", "Nexus Europa", False),
    (18, "Moldova reports seven Russian drone incursions", "Nexus Europa", False),
    (19, "Zelenskiy: intel shows Russia planning new strikes", "Reuters", False),
    (20, "Burnham dismisses ex-PMs over EU rejoin talk", "UnHerd", False),
    (21, "Australia coalition opposes Vanuatu treaty deal", "PINA", False),
    (22, "German PMI 55.0, best since March 2022", "Edge", False),
    (23, "Fiji shuts all schools for five days as drought deepens", "PINA", False),
    (24, "EU-Indonesia pact cuts tariffs on 98% of lines", "Edge", False),
    (25, "Russia readies nuclear-capable satellite launch, intel says", "Ungated", True),
    (26, "Hamas, factions agree Gaza disarmament roadmap", "MEF", False),
    (27, "Israeli forces in major operation at Al-Amari camp", "Arab News", False),
    (28, "Houthi shelling kills, wounds civilians on Yemen road", "Arab News", False),
    (29, "US senators move to halt funding for war on Iran", "MEF", False),
    (30, "UNIFIL warns of fragile security before Jan 2027 pullout", "MEF", False),
    (31, "US weighs first training mission with Syrian army", "MEF", False),
    (32, "5,000 drones light sky over Three Gorges festival", "Euronews", False),
    (33, "South Korea, China agree wider trade deal on entertainment", "Euronews", False),
    (34, "Japan launches Asian oil task force amid Gulf disruption", "Euronews", False),
    (35, "5.6-magnitude quake strikes Nepal near China border", "Horizon", False),
    (36, "China opens Tiangong station to first foreign astronaut", "Straits Times", False),
    (37, "Sooryavanshi hits 204 off 53, fastest List A double ton", "Sportstar", False),
    (38, "Gukesh opens world title defence against Sindarov", "Guardian", False),
    (39, "CrowdStrike to buy Zscaler in $43.9bn all-stock deal", "The Peel", False),
    (40, "Microsoft: Azure made $33.2bn in a quarter, first disclosure", "Brimco", False),
    (41, "14 nations recognise ICJ ruling on Rohingya genocide", "Horizon", False),
    (42, "FIFA confirms 2031 Women's World Cup hosts", "myKhel", False),
    (43, "Bitcoin, gold slide as stocks soar", "FXStreet", False),
    (44, "Mexico to try 'El Chapo Isidro' despite US extradition bid", "Horizon", False),
    (45, "Colombia car bomb wrecks buildings; no victims confirmed", "Horizon", False),
    (46, "Brazil cuts 2027 growth forecast to 1.8%", "MercoPress", False),
    (47, "Nigeria: nearly 60 dead in tribal reprisal attacks", "Sahara Medias", False),
    (48, "South Africa court to rule on Malema bid to gag Zille", "TimesLIVE", False),
    (49, "Somalia names new defence minister Saadaq Omar Mohamed", "Goobjoog", False),
    (50, "Ghana top court sets Nov 25 ruling on Sky Train case", "Citi Newsroom", False),
]

REGION_COUNTS = [("EUROPE", 10), ("MIDDLE EAST", 9), ("ASIA", 10),
                 ("AMERICAS", 5), ("AFRICA", 6), ("OCEANIA", 4),
                 ("GLOBAL", 6)]
FIELDS_COVERED = ["War", "Markets", "Diplomacy", "Politics", "Climate",
                  "Trade", "Disaster", "Health", "Law & Crime", "Defence",
                  "Energy", "Space", "Science", "Sport", "AI & Tech",
                  "Migration"]

DATE_CHECK_TEXT = (
    "Left out: COP31's collapse (Sun 22 Nov); India-NZ Test draw (23 Nov); "
    "Alcaraz's ATP Finals title (22 Nov); the Shenzhen summit (19-20 Nov). "
    "Not yet decided at about 16:00 UTC: Tuesday's US market close; the "
    "Solomons-Australia treaty (Wed); the EU summit (26-27 Nov); "
    "South Sudan's vote (22 Dec).")

FOOTER_TEXT = (
    "Every story happened or was first reported on Tue 24 Nov 2026. "
    "CLAIM = one side's account. "
    "Sources: Reuters, AP, WSJ, CNN, UN News, Euronews, PINA, Arab News, "
    "Guardian, MEF. Original drawings.")


# --- page layout ------------------------------------------------------
# Vertical plan (1024 tall): masthead 10-97, timeline 104-158,
# lead grid 166-646, map 654-776, also list 784-952, date check
# 956-992, footer 996-1008.

CARD_W = (CONTENT_W - 3 * 8) // 4          # 237
CARD_H = 114
CARD_GAP = 8
GRID_TOP = 166


def paint_masthead(sheet):
    sheet.hrule(MARGIN, 10, CONTENT_W, INK)
    sheet.hrule(MARGIN, 12, CONTENT_W, INK)
    put_centred(sheet, "THE WORLD TODAY", 12, 512, 17, RED, bold=True)
    put_centred(sheet, "TUESDAY, 24 NOVEMBER 2026", 40, 512, 31, INK,
                bold=True)
    put_centred(sheet,
                "ONE DAY OF WORLD NEWS, ONE PICTURE  \u00b7  50 STORIES"
                "  \u00b7  7 REGIONS  \u00b7  16 FIELDS",
                10, 512, 80, GREY)
    sheet.hrule(MARGIN, 97, CONTENT_W, INK)


def paint_timeline(sheet):
    put_text(sheet, "THE DAY IN UTC", 10, MARGIN, 104, RED, bold=True)
    put_text(sheet, "as the day turned west \u2014 overnight to evening",
             10, MARGIN + 124, 104, GREY)
    box_w = (CONTENT_W - 6 * 6) // 7
    x = MARGIN + (CONTENT_W - (7 * box_w + 6 * 6)) // 2
    for when, head in DAY_EVENTS:
        sheet.box(x, 118, box_w, 40, CARD_BG)
        sheet.hrule(x, 118, box_w, RULE)
        sheet.hrule(x, 157, box_w, RULE)
        put_text(sheet, when, 9, x + 5, 122, RED, bold=True)
        lines = flow_text(head, 7.5, box_w - 10)[:2]
        for j, ln in enumerate(lines):
            put_text(sheet, ln, 7.5, x + 5, 133 + j * 10, INK)
        x += box_w + 6


def paint_card_meta(sheet, x, y, width, region, source, status):
    put_text(sheet, region.upper() + "  \u00b7  " + source.upper(), 8, x, y,
             GREY)
    tag = "CONFIRMED" if status == "CONFIRMED" else "CLAIM"
    col = GREEN if status == "CONFIRMED" else RED
    tw = int(text_w(tag, 8))
    bx = int(x + width - tw - 8)
    sheet.box(bx, y - 1, tw + 8, 10, col)
    put_text(sheet, tag, 8, bx + 4, y, WHITE, bold=True)


def paint_card(sheet, story):
    n = story["n"]
    col, row = (n - 1) % 4, (n - 1) // 4
    x = MARGIN + col * (CARD_W + CARD_GAP)
    y = GRID_TOP + row * (CARD_H + CARD_GAP)
    w = CARD_W
    sheet.box(x, y, w, CARD_H, CARD_BG)
    sheet.hrule(x, y, w, RULE)
    sheet.hrule(x, y + CARD_H - 1, w, RULE)
    sheet.vrule(x, y, CARD_H, RULE)
    sheet.vrule(x + w - 1, y, CARD_H, RULE)
    sheet.box(x, y, w, 13, REGION_TINT[story["region"]])
    put_text(sheet, str(n), 9, x + 4, y + 2, RED, bold=True)
    label_x = x + 4 + int(text_w(str(n), 9)) + 5
    put_text(sheet, story["region"].upper() + " \u00b7 "
             + FIELD_FOR_STORY[n], 8, label_x, y + 3, INK)
    PICTURES[story["pic"]](sheet, x + 3, y + 16, w - 6, 28)
    # Headline: shrink one step if it will not fit on two lines.
    size = 12
    title_lines = flow_text(story["title"], size, w - 8)
    while len(title_lines) > 2 and size > 10:
        size -= 1
        title_lines = flow_text(story["title"], size, w - 8)
    for j, ln in enumerate(title_lines[:2]):
        put_text(sheet, ln, size, x + 4, y + 48 + j * (size + 1), INK,
                 bold=True)
    # Summary: shrink one step at a time until it fits three lines.
    size = 9
    body_lines = flow_text(story["body"], size, w - 8)
    while len(body_lines) > 3 and size > 6.5:
        size -= 0.5
        body_lines = flow_text(story["body"], size, w - 8)
    for j, ln in enumerate(body_lines[:3]):
        put_text(sheet, ln, size, x + 4, y + 75 + j * 10, INK)
    paint_card_meta(sheet, x + 4, y + CARD_H - 10, w - 8,
                    story["region"], story["source"], story["status"])


def paint_map_panel(sheet):
    y = 654
    put_text(sheet, "WHERE IT HAPPENED", 11, MARGIN, y, RED, bold=True)
    put_text(sheet, "numbered pins are the 16 lead stories above",
             10, MARGIN + 172, y, GREY)
    my = y + 14
    pins = [(s["n"], s["lon"], s["lat"], s["region"])
            for s in LEAD_STORIES]
    paint_map(sheet, MARGIN, my, 660, 108, pins)
    # Tally on the right: stories per region, counts verified vs the 50.
    tx = MARGIN + 672
    put_text(sheet, "BY REGION", 9, tx, my, INK, bold=True)
    for i, (name, cnt) in enumerate(REGION_COUNTS):
        ry = my + 14 + i * 12
        sheet.blob(tx + 5, ry + 4, 4, PIN[name.title()])
        put_text(sheet, name, 9, tx + 14, ry, INK)
        put_text(sheet, str(cnt), 9, tx + 128, ry, RED, bold=True)
    # Fields covered, two columns of eight.
    fx = MARGIN + 820
    put_text(sheet, "16 FIELDS", 9, fx, my, INK, bold=True)
    for i, field in enumerate(FIELDS_COVERED):
        put_text(sheet, field, 8, fx + (i // 8) * 76,
                 my + 14 + (i % 8) * 11, INK)


def paint_also(sheet):
    y = 784
    put_text(sheet, "ALSO ON TUESDAY", 11, MARGIN, y, RED, bold=True)
    put_text(sheet, "stories 17\u201350, one line each", 10,
             MARGIN + 156, y, GREY)
    col_w = (CONTENT_W - 12) // 2
    for i, (n, title, source, claim) in enumerate(MORE_STORIES):
        col = i // 17
        row = i % 17
        x = MARGIN + col * (col_w + 12)
        yy = y + 16 + row * 9
        put_text(sheet, str(n) + ".", 8, x, yy, RED, bold=True)
        line = flow_text(title + " \u2014 " + source, 8, col_w - 22)
        if line:
            put_text(sheet, line[0], 8, x + 20, yy, INK)
            if claim:
                put_text(sheet, "\u00b7 CLAIM", 8,
                         x + 20 + int(text_w(line[0], 8)) + 3, yy, RED,
                         bold=True)


def paint_date_check(sheet):
    y = 956
    sheet.box(MARGIN, y, CONTENT_W, 36, CHECK_BG)
    sheet.hrule(MARGIN, y, CONTENT_W, RED)
    sheet.hrule(MARGIN, y + 35, CONTENT_W, RED)
    sheet.vrule(MARGIN, y, 36, RED)
    sheet.vrule(MARGIN + CONTENT_W - 1, y, 36, RED)
    put_text(sheet, "DATE CHECK", 10, MARGIN + 6, y + 4, RED, bold=True)
    lines = flow_text(DATE_CHECK_TEXT, 8.5, CONTENT_W - 12)
    for j, ln in enumerate(lines[:2]):
        put_text(sheet, ln, 8.5, MARGIN + 6, y + 16 + j * 10, INK)


def paint_footer(sheet):
    y = 996
    sheet.hrule(MARGIN, y, CONTENT_W, INK)
    put_text(sheet, FOOTER_TEXT, 6.5, MARGIN, y + 5, GREY)


def build_page():
    sheet = Sheet(PAGE_W, PAGE_H, PAPER)
    paint_masthead(sheet)
    paint_timeline(sheet)
    for story in LEAD_STORIES:
        paint_card(sheet, story)
    paint_map_panel(sheet)
    paint_also(sheet)
    paint_date_check(sheet)
    paint_footer(sheet)
    return sheet


def main():
    out = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "entry.png")
    size = save_png(build_page(), path)
    print("wrote", path, size, "bytes")


if __name__ == "__main__":
    main()
