# Diff viewer: the lines the agent changed in one file, GitHub style.
import theme as t

TOP = 40
LINE_H = 12


class Repeat:
    """Auto-repeat while a button is held."""

    def __init__(self):
        self.since = {}
        self.last = {}

    def fire(self, button, delay=350, rate=60):
        now = badge.ticks
        if badge.pressed(button):
            self.since[button] = now
            self.last[button] = now
            return True
        if badge.held(button):
            since = self.since.get(button)
            if since is not None and now - since > delay and now - self.last[button] > rate:
                self.last[button] = now
                return True
        else:
            self.since.pop(button, None)
        return False


class Diff:
    def __init__(self):
        self.files = []
        self.index = 0
        self.top = 0
        self.repeat = Repeat()

    def open(self, files, index):
        self.files = files
        self.index = index
        self.top = 0

    def rows(self):
        return (screen.height - 18 - TOP) // LINE_H

    def update(self, app):
        lines = self.files[self.index]["lines"]
        page = self.rows()
        if self.repeat.fire(BUTTON_DOWN):
            self.top = min(self.top + 1, max(0, len(lines) - page))
            app.dirty()
        elif self.repeat.fire(BUTTON_UP):
            self.top = max(0, self.top - 1)
            app.dirty()
        elif badge.pressed(BUTTON_RIGHT) and self.index < len(self.files) - 1:
            self.index += 1
            self.top = 0
            app.dirty()
        elif badge.pressed(BUTTON_LEFT) and self.index > 0:
            self.index -= 1
            self.top = 0
            app.dirty()
        elif badge.pressed(BUTTON_SELECT):
            self.top = min(self.top + page, max(0, len(lines) - page))
            app.dirty()
        elif badge.pressed(BUTTON_BACK):
            return ("back", self.index)
        return None

    def draw(self, app):
        f = self.files[self.index]
        t.fill(0, 0, screen.width, screen.height, t.CARD)
        # header
        t.fill(0, 0, screen.width, TOP - 2, t.PAGE)
        t.line(0, TOP - 2, screen.width, TOP - 2, t.BORDER, 1)
        t.g_file(12, 11, t.MUTED)
        counts = "+%d -%d" % (f["add"], f["del"])
        cw = t.measure(counts, t.SM)
        name = f["name"]
        if t.measure(name, t.SM) > screen.width - cw - 40:
            name = ".../" + name.rsplit("/", 1)[-1]
        t.text(t.fit(name, screen.width - cw - 40, t.SM), 22, 5, t.SM, t.INK)
        minus = "-%d" % f["del"]
        t.right(minus, screen.width - 8, 5, t.SM, t.RED)
        t.right("+%d" % f["add"], screen.width - 12 - t.measure(minus, t.SM), 5, t.SM, t.GREEN)
        status = t.cap(f["status"])
        t.text("%s  -  file %d of %d" % (status, self.index + 1, len(self.files)), 22, 21, t.XS, t.MUTED)

        lines = f["lines"]
        if not lines:
            t.center("No text diff for this file (binary or too large).", screen.width / 2, 90,
                     t.XS, t.MUTED)
        y = TOP
        for i in range(self.top, min(len(lines), self.top + self.rows())):
            row = lines[i].replace("\t", "  ")
            if row.startswith("@@"):
                bg, fg = color.rgb(241, 245, 249), color.rgb(71, 85, 105)
            elif row.startswith("+"):
                bg, fg = color.rgb(230, 255, 236), color.rgb(22, 101, 52)
            elif row.startswith("-"):
                bg, fg = color.rgb(255, 235, 233), color.rgb(153, 27, 27)
            else:
                bg, fg = None, t.TEXT
            if bg is not None:
                t.fill(0, y, screen.width, LINE_H, bg)
            t.text(t.fit(t.clean(row) or " ", screen.width - 10, t.XS), 5, y + 1, t.XS, fg)
            y += LINE_H
        if len(lines) > self.rows():
            track = self.rows() * LINE_H
            bar = max(10, track * self.rows() // len(lines))
            pos = (track - bar) * self.top // max(1, len(lines) - self.rows())
            t.box(screen.width - 3, TOP + pos, 2, bar, t.BORDER_STRONG, 1)
        t.hints((("U/D", "scroll"), ("L/R", "file"), ("SELECT", "page"), ("BACK", "task")))
