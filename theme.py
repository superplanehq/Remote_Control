# Factory Remote look and feel: SuperPlane's light board, Mona Sans text,
# and small vector glyphs. Everything is drawn with shapes; no pixel art.
import math
import time

# ---------------------------------------------------------------- colours
PAGE = color.rgb(243, 244, 246)
CARD = color.rgb(255, 255, 255)
CARD_HI = color.rgb(249, 250, 251)
BORDER = color.rgb(229, 231, 235)
BORDER_STRONG = color.rgb(209, 213, 219)
INK = color.rgb(17, 24, 39)
TEXT = color.rgb(55, 65, 81)
MUTED = color.rgb(107, 114, 128)
FAINT = color.rgb(156, 163, 175)
WHITE = color.rgb(255, 255, 255)
BLACK = color.rgb(0, 0, 0)
FOCUS = color.rgb(37, 99, 235)
PURPLE = color.rgb(124, 58, 237)
PURPLE_BG = color.rgb(237, 233, 254)
GREEN = color.rgb(22, 163, 74)
GREEN_BG = color.rgb(220, 252, 231)
RED = color.rgb(220, 38, 38)
RED_BG = color.rgb(254, 226, 226)
ORANGE = color.rgb(234, 88, 12)
AMBER = color.rgb(217, 119, 6)
AMBER_BG = color.rgb(254, 243, 199)
BLUE = color.rgb(37, 99, 235)
BLUE_BG = color.rgb(219, 234, 254)

# Confidence meter, as on the SuperPlane board.
METER_ON_HIGH = color.rgb(34, 197, 94)
METER_ON_MID = color.rgb(249, 115, 22)
METER_ON_LOW = color.rgb(239, 68, 68)
METER_OFF = color.rgb(209, 213, 219)

# Lane colours. Keys match SuperPlane's column colour ids.
LANES = {
    "plain": (236, 237, 240),
    "slate": (152, 162, 178),
    "yellow": (226, 164, 110),
    "lime": (128, 196, 160),
    "teal": (110, 200, 190),
    "sky": (125, 185, 228),
    "purple": (190, 172, 245),
}
DEFAULT_LANE = {"backlog": "plain", "phase": "slate", "verify": "yellow", "done": "lime"}


def lane_rgb(name):
    return LANES.get(name) or LANES["plain"]


def rgb(t, alpha=255):
    return color.rgb(t[0], t[1], t[2], alpha)


def shade(t, k):
    """Darken (k < 1) or lighten (k > 1) an (r, g, b) tuple."""
    if k <= 1:
        return (int(t[0] * k), int(t[1] * k), int(t[2] * k))
    k -= 1
    return (int(t[0] + (255 - t[0]) * k), int(t[1] + (255 - t[1]) * k), int(t[2] + (255 - t[2]) * k))


# ---------------------------------------------------------------- fonts
try:
    SANS = font.load("/system/assets/fonts/MonaSans-Medium.af")
    VECTOR = True
except (OSError, ValueError, AttributeError):
    SANS = font.sins
    VECTOR = False

XS = 9
SM = 10
MD = 11
LG = 13
XL = 16

_width_cache = {}


def measure(value, size):
    key = (value, size)
    found = _width_cache.get(key)
    if found is not None:
        return found
    screen.font = SANS
    if VECTOR:
        w = screen.measure_text(value, size)[0]
    else:
        w = screen.measure_text(value)[0]
    if len(_width_cache) > 400:
        _width_cache.clear()
    _width_cache[key] = w
    return w


def text(value, x, y, size, pen):
    screen.font = SANS
    screen.pen = pen
    if VECTOR:
        screen.text(value, vec2(int(x), int(y)), size)
    else:
        screen.text(value, int(x), int(y))


def right(value, x, y, size, pen):
    text(value, x - measure(value, size), y, size, pen)


def center(value, cx, y, size, pen):
    text(value, cx - measure(value, size) / 2, y, size, pen)


_fit_cache = {}


def fit(value, max_w, size):
    key = (value, max_w, size)
    found = _fit_cache.get(key)
    if found is not None:
        return found
    result = value
    if measure(value, size) > max_w:
        lo, hi = 0, len(value)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if measure(value[:mid] + "...", size) <= max_w:
                lo = mid
            else:
                hi = mid - 1
        result = value[:lo].rstrip() + "..."
    if len(_fit_cache) > 400:
        _fit_cache.clear()
    _fit_cache[key] = result
    return result


def wrap(value, max_w, size, max_lines=3):
    words = value.split(" ")
    lines = []
    line = ""
    for word in words:
        trial = word if not line else line + " " + word
        if measure(trial, size) <= max_w:
            line = trial
            continue
        if line:
            lines.append(line)
        line = word
        if len(lines) == max_lines:
            break
    if line and len(lines) < max_lines:
        lines.append(line)
    if len(lines) == max_lines and len(" ".join(lines)) < len(value):
        lines[-1] = fit(lines[-1] + " ...", max_w, size)
    return lines


def cap(value):
    """str.capitalize() is missing from MicroPython."""
    return value[:1].upper() + value[1:] if value else value


def clean(value):
    """The fonts cover ASCII; swap common punctuation and drop the rest."""
    if not value:
        return ""
    out = []
    for ch in str(value):
        o = ord(ch)
        if ch in "\n\r\t":
            out.append(" ")
        elif 32 <= o < 127:
            out.append(ch)
        elif o in (0x2018, 0x2019):
            out.append("'")
        elif o in (0x201C, 0x201D):
            out.append('"')
        elif o in (0x2013, 0x2014, 0x2212):
            out.append("-")
        elif o == 0x2026:
            out.append("...")
    return "".join(out)


# ---------------------------------------------------------------- shapes
def box(x, y, w, h, pen, r=4):
    screen.pen = pen
    if r <= 0:
        screen.rectangle(int(x), int(y), int(w), int(h))
    else:
        screen.shape(shape.rounded_rectangle(int(x), int(y), int(w), int(h), r))


def frame(x, y, w, h, pen, r=4, width=1):
    screen.pen = pen
    screen.shape(shape.rounded_rectangle(int(x), int(y), int(w), int(h), r).stroke(width))


def fill(x, y, w, h, pen):
    screen.pen = pen
    screen.rectangle(int(x), int(y), int(w), int(h))


def line(x0, y0, x1, y1, pen, width=1):
    screen.pen = pen
    screen.shape(shape.line(x0, y0, x1, y1, width))


def disc(x, y, r, pen):
    screen.pen = pen
    screen.shape(shape.circle(x, y, r))


def ring(x, y, r, pen, width=1):
    screen.pen = pen
    screen.shape(shape.circle(x, y, r).stroke(width))


def card(x, y, w, h, focused=False):
    box(x, y + 1, w, h, color.rgb(0, 0, 0, 18), 6)
    box(x, y, w, h, CARD, 6)
    if focused:
        frame(x - 1, y - 1, w + 2, h + 2, FOCUS, 7, 2)
    else:
        frame(x, y, w, h, BORDER, 6)


def pill(label, x, y, fg, bg, size=XS, pad=5, glyph=None):
    """Rounded label. Returns its width."""
    w = measure(label, size) + pad * 2 + (10 if glyph else 0)
    h = size + 5
    box(x, y, w, h, bg, h // 2)
    tx = x + pad
    if glyph:
        glyph(tx + 3, y + h / 2, fg)
        tx += 10
    text(label, tx, y + 2, size, fg)
    return w


# ---------------------------------------------------------------- glyphs
# Each glyph is drawn centred on (cx, cy) and fits in about 9x9 pixels.
def g_github(cx, cy, pen):
    disc(cx, cy, 4.5, pen)
    disc(cx, cy + 0.6, 2.2, CARD)
    disc(cx - 2.6, cy - 3.2, 1.3, pen)
    disc(cx + 2.6, cy - 3.2, 1.3, pen)


def g_check_circle(cx, cy, pen):
    disc(cx, cy, 5, pen)
    line(cx - 2.4, cy + 0.2, cx - 0.6, cy + 2, WHITE, 1.4)
    line(cx - 0.6, cy + 2, cx + 2.6, cy - 1.8, WHITE, 1.4)


def g_cross_circle(cx, cy, pen):
    disc(cx, cy, 5, pen)
    line(cx - 2, cy - 2, cx + 2, cy + 2, WHITE, 1.4)
    line(cx - 2, cy + 2, cx + 2, cy - 2, WHITE, 1.4)


def g_dashed_circle(cx, cy, pen):
    for i in range(10):
        a = i * math.pi / 5
        disc(cx + math.cos(a) * 4.5, cy + math.sin(a) * 4.5, 0.75, pen)


def g_spinner(cx, cy, pen, t=None):
    if t is None:
        t = badge.ticks / 1000
    ring(cx, cy, 4.5, BORDER_STRONG, 1.5)
    a0 = t * 6
    for i in range(6):
        a = a0 + i * 0.32
        disc(cx + math.cos(a) * 4.5, cy + math.sin(a) * 4.5, 1, pen)


def g_clock(cx, cy, pen):
    ring(cx, cy, 4.5, pen, 1.2)
    line(cx, cy, cx, cy - 2.6, pen, 1.2)
    line(cx, cy, cx + 2, cy, pen, 1.2)


def g_pr(cx, cy, pen):
    ring(cx - 2.5, cy - 3, 1.4, pen, 1)
    ring(cx - 2.5, cy + 3.2, 1.4, pen, 1)
    line(cx - 2.5, cy - 1.6, cx - 2.5, cy + 1.8, pen, 1)
    ring(cx + 2.8, cy + 3.2, 1.4, pen, 1)
    line(cx + 2.8, cy + 1.8, cx + 2.8, cy - 1.2, pen, 1)
    line(cx + 2.8, cy - 1.2, cx + 0.6, cy - 3, pen, 1)


def g_merged(cx, cy, pen):
    ring(cx - 2.5, cy - 3, 1.4, pen, 1)
    ring(cx - 2.5, cy + 3.2, 1.4, pen, 1)
    ring(cx + 2.8, cy + 0.6, 1.4, pen, 1)
    line(cx - 2.5, cy - 1.6, cx - 2.5, cy + 1.8, pen, 1)
    line(cx - 2.5, cy - 1.6, cx + 1.4, cy + 0.6, pen, 1)


def g_person(cx, cy, pen):
    ring(cx, cy, 6, BORDER_STRONG, 1)
    ring(cx, cy - 1.6, 1.8, pen, 1)
    line(cx - 3, cy + 3.4, cx - 1.6, cy + 1.2, pen, 1)
    line(cx + 3, cy + 3.4, cx + 1.6, cy + 1.2, pen, 1)
    line(cx - 1.6, cy + 1.2, cx + 1.6, cy + 1.2, pen, 1)


def g_robot(cx, cy, pen):
    frame(cx - 4, cy - 2.5, 8, 6, pen, 1.5, 1)
    disc(cx - 1.6, cy + 0.5, 0.9, pen)
    disc(cx + 1.6, cy + 0.5, 0.9, pen)
    line(cx, cy - 2.5, cx, cy - 4.5, pen, 1)


def g_file(cx, cy, pen):
    frame(cx - 3, cy - 4, 6.5, 8.5, pen, 1, 1)
    line(cx - 1.4, cy - 1, cx + 2, cy - 1, pen, 1)
    line(cx - 1.4, cy + 1.4, cx + 2, cy + 1.4, pen, 1)


def g_chevron(cx, cy, pen):
    line(cx - 1.5, cy - 3, cx + 1.5, cy, pen, 1.4)
    line(cx + 1.5, cy, cx - 1.5, cy + 3, pen, 1.4)


def initials_avatar(cx, cy, name, r=6):
    palette = ((124, 58, 237), (37, 99, 235), (13, 148, 136), (217, 119, 6), (219, 39, 119))
    total = 0
    for ch in name:
        total += ord(ch)
    disc(cx, cy, r, rgb(palette[total % len(palette)]))
    letters = "".join(part[:1] for part in name.split()[:2]).upper() or "?"
    center(letters, cx, cy - 4.5, 8, WHITE)


def meter(x, y, score, size=5):
    """SuperPlane's five-step confidence meter. Returns its width."""
    if score is None:
        return 0
    if score >= 4:
        on = METER_ON_HIGH
    elif score >= 3:
        on = METER_ON_MID
    else:
        on = METER_ON_LOW
    w = 5
    for i in range(size):
        fill(x + i * (w + 1), y, w, 7, on if i < score else METER_OFF)
    return size * (w + 1) - 1


# ---------------------------------------------------------------- footer
def hints(items):
    """Key hints along the bottom edge: (key, action) pairs."""
    from compat import KEYS

    y = screen.height - 15
    fill(0, y - 1, screen.width, 16, CARD)
    line(0, y - 1, screen.width, y - 1, BORDER, 1)
    x = 6
    for key, action in items:
        key = KEYS.get(key, key)
        kw = measure(key, XS) + 8
        box(x, y + 1, kw, 12, PAGE, 3)
        frame(x, y + 1, kw, 12, BORDER_STRONG, 3)
        text(key, x + 4, y + 2, XS, TEXT)
        x += kw + 4
        text(action, x, y + 2, XS, MUTED)
        x += measure(action, XS) + 10


def toast(message, kind="info"):
    if kind == "error":
        fg, bg = RED, RED_BG
    elif kind == "ok":
        fg, bg = GREEN, GREEN_BG
    else:
        fg, bg = INK, CARD
    w = min(screen.width - 24, measure(message, SM) + 24)
    x = (screen.width - w) // 2
    y = screen.height - 44
    box(x, y + 2, w, 22, color.rgb(0, 0, 0, 40), 8)
    box(x, y, w, 22, bg, 8)
    frame(x, y, w, 22, BORDER_STRONG if kind == "info" else fg, 8)
    text(fit(message, w - 20, SM), x + 10, y + 5, SM, fg)


# ---------------------------------------------------------------- time
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


class Clock:
    """Wall clock from the API's Date header, else the system clock."""

    epoch = None
    at_ticks = 0

    @classmethod
    def sync(cls, header):
        try:
            parts = header.split()
            day = int(parts[1])
            month = MONTHS.index(parts[2]) + 1
            year = int(parts[3])
            hh, mm, ss = [int(v) for v in parts[4].split(":")]
            cls.epoch = time.mktime((year, month, day, hh, mm, ss, 0, 0))
            cls.at_ticks = badge.ticks
        except (ValueError, IndexError, AttributeError):
            pass

    @classmethod
    def now(cls):
        if cls.epoch is None:
            if time.localtime()[0] >= 2025:
                return int(time.time())
            return None
        return cls.epoch + (badge.ticks - cls.at_ticks) // 1000


def parse_iso(value):
    if not value or not isinstance(value, str) or len(value) < 19:
        return None
    try:
        return time.mktime((
            int(value[0:4]), int(value[5:7]), int(value[8:10]),
            int(value[11:13]), int(value[14:16]), int(value[17:19]), 0, 0,
        ))
    except (ValueError, OverflowError):
        return None


def ago(stamp):
    if stamp is None:
        return ""
    now = Clock.now()
    if now is None:
        tm = time.localtime(stamp)
        return "%s %d" % (MONTHS[tm[1] - 1], tm[2])
    d = now - stamp
    if d < 45:
        return "just now"
    if d < 3600:
        n = max(1, d // 60)
        return "%d minute%s ago" % (n, "" if n == 1 else "s")
    if d < 86400:
        n = d // 3600
        return "%d hour%s ago" % (n, "" if n == 1 else "s")
    if d < 86400 * 7:
        n = d // 86400
        return "%d day%s ago" % (n, "" if n == 1 else "s")
    if d < 86400 * 30:
        n = d // (86400 * 7)
        return "%d week%s ago" % (n, "" if n == 1 else "s")
    if d < 86400 * 365:
        n = d // (86400 * 30)
        return "%d month%s ago" % (n, "" if n == 1 else "s")
    n = d // (86400 * 365)
    return "%d year%s ago" % (n, "" if n == 1 else "s")


def duration(seconds):
    if seconds is None or seconds < 0:
        return ""
    seconds = int(seconds)
    if seconds < 60:
        return "%ds" % seconds
    if seconds < 3600:
        return "%dm %02ds" % (seconds // 60, seconds % 60)
    return "%dh %02dm" % (seconds // 3600, (seconds % 3600) // 60)
