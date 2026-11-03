# The factory board: Backlog, the line's steps, Verify and Done, like the
# SuperPlane dashboard. One lane is open at a time; LEFT/RIGHT switches lanes.
import theme as t
from superplane import columns_for

TOP = 28
TAB_H = 24
LANE_Y = TOP + TAB_H
CARD_H = 40
CARD_GAP = 5
LIST_Y = LANE_Y + 20

SUBTITLES = {
    "backlog": ("Tasks waiting for an agent", t.g_github),
    "phase": ("Runs the %s agent", t.g_robot),
    "verify": ("Review the pull request, then merge", t.g_pr),
    "done": ("Closes tasks when pull requests merge", t.g_github),
}


def lane_name(app, col):
    colors = app.backend.line.get("colors") or {}
    if col["kind"] == "phase":
        return colors.get(col["key"]) or t.DEFAULT_LANE["phase"]
    return colors.get(col["key"]) or t.DEFAULT_LANE[col["kind"]]


def status_glyph(card, x, y):
    status = card["status"]
    column = card["column"]
    if column == "backlog":
        t.g_dashed_circle(x, y, t.FAINT)
    elif column == "done":
        if status == "completed":
            t.g_check_circle(x, y, t.GREEN)
        elif status in ("failed", "rejected"):
            t.g_cross_circle(x, y, t.RED)
        else:
            t.g_check_circle(x, y, t.FAINT)
    elif status == "running":
        t.g_spinner(x, y, t.BLUE)
        return True
    elif status == "queued":
        t.g_clock(x, y, t.MUTED)
    elif status == "failed":
        t.g_cross_circle(x, y, t.RED)
    elif column == "verify":
        t.g_pr(x, y, t.GREEN)
    else:
        t.g_clock(x, y, t.AMBER)
    return False


class Board:
    def __init__(self):
        self.col = 0
        self.sel = {}
        self.scroll = {}

    def columns(self, app):
        return columns_for(app.backend.line)

    def cards(self, app, key):
        return (app.cards or {}).get(key) or []

    def focus(self, app, column_key, card_id=None):
        cols = self.columns(app)
        for i, col in enumerate(cols):
            if col["key"] == column_key:
                self.col = i
                if card_id:
                    for j, card in enumerate(self.cards(app, column_key)):
                        if card["id"] == card_id:
                            self.sel[column_key] = j
                return

    def selected(self, app):
        cols = self.columns(app)
        if not cols:
            return None
        self.col = min(self.col, len(cols) - 1)
        key = cols[self.col]["key"]
        cards = self.cards(app, key)
        if not cards:
            return None
        index = min(self.sel.get(key, 0), len(cards) - 1)
        self.sel[key] = index
        return cards[index]

    # ------------------------------------------------------------ input
    def update(self, app):
        cols = self.columns(app)
        if not cols:
            return None
        key = cols[min(self.col, len(cols) - 1)]["key"]
        count = len(self.cards(app, key))
        if badge.pressed(BUTTON_RIGHT) and self.col < len(cols) - 1:
            self.col += 1
            app.dirty()
        elif badge.pressed(BUTTON_LEFT) and self.col > 0:
            self.col -= 1
            app.dirty()
        elif badge.pressed(BUTTON_DOWN) and count:
            self.sel[key] = min(count - 1, self.sel.get(key, 0) + 1)
            app.dirty()
        elif badge.pressed(BUTTON_UP) and count:
            self.sel[key] = max(0, self.sel.get(key, 0) - 1)
            app.dirty()
        elif badge.pressed(BUTTON_SELECT):
            card = self.selected(app)
            if card:
                return ("open", card)
        elif badge.pressed(BUTTON_MENU):
            app.refresh(force=True)
        return None

    # ------------------------------------------------------------ drawing
    def draw_header(self, app):
        t.fill(0, 0, screen.width, TOP - 2, t.CARD)
        t.line(0, TOP - 2, screen.width, TOP - 2, t.BORDER, 1)
        factory = app.backend.factory or {}
        key = factory.get("key") or "SP"
        t.box(6, 4, 19, 18, t.PAGE, 4)
        t.frame(6, 4, 19, 18, t.BORDER_STRONG, 4)
        t.center(key[:2], 15.5, 8, t.XS, t.INK)
        t.text(t.fit(factory.get("name") or "Factory", 150, t.LG), 32, 6, t.LG, t.INK)
        x = screen.width - 8
        if app.job is not None:
            t.g_spinner(x - 4, 13, t.MUTED)
            app.animating = True
            label = "Syncing"
            t.right(label, x - 12, 8, t.XS, t.MUTED)
            x -= 16 + t.measure(label, t.XS)
        elif app.synced_at is not None:
            age = (badge.ticks - app.synced_at) // 1000
            label = "Synced just now" if age < 10 else "Synced %ds ago" % age if age < 60 else \
                "Synced %dm ago" % (age // 60)
            t.disc(x - 3, 13, 2.5, t.GREEN if not app.sync_error else t.RED)
            t.right(label, x - 9, 8, t.XS, t.MUTED)
            x -= 16 + t.measure(label, t.XS)
        if app.backend.demo:
            t.pill("DEMO", x - 38, 6, t.AMBER, t.AMBER_BG, t.XS, 5)

    def draw_tabs(self, app, cols):
        n = len(cols)
        gap = 3
        w = (screen.width - 8 - gap * (n - 1)) / n
        for i, col in enumerate(cols):
            x = 4 + i * (w + gap)
            base = t.lane_rgb(lane_name(app, col))
            count = len(self.cards(app, col["key"]))
            active = i == self.col
            if active:
                t.box(x, TOP + 2, w, TAB_H + 6, t.rgb(base), 6)
            else:
                t.box(x, TOP + 4, w, TAB_H - 4, t.rgb(t.shade(base, 1.45)), 6)
            ink = t.INK if active else t.MUTED
            label = t.fit(col["title"], w - 22, t.SM)
            t.text(label, x + 7, TOP + (7 if active else 8), t.SM, ink)
            t.right(str(count), x + w - 7, TOP + (7 if active else 8), t.SM, ink)

    def draw_card(self, app, card, x, y, w, focused):
        t.card(x, y, w, CARD_H, focused)
        if status_glyph(card, x + 12, y + 11):
            app.animating = True
        right_pad = 22
        t.text(t.fit(card["title"], w - 26 - right_pad, t.MD), x + 23, y + 4, t.MD, t.INK)
        if card.get("assignee"):
            t.initials_avatar(x + w - 13, y + 11, card["assignee"])
        else:
            t.g_person(x + w - 13, y + 11, t.FAINT)

        my = y + 24
        mx = x + 23
        if card.get("origin", "").find("github.com") >= 0:
            t.g_github(x + 12, my + 6, t.INK)
        column = card["column"]
        if column == "backlog":
            t.text(t.ago(card["created"]), mx, my + 1, t.XS, t.MUTED)
            if card.get("confidence") is not None:
                mw = 5 * 6 - 1
                t.meter(x + w - 10 - mw, my + 2, card["confidence"])
                t.right("Confidence", x + w - 15 - mw, my + 1, t.XS, t.MUTED)
        elif column == "done":
            pr = card.get("pr")
            if pr and pr["state"] == "STATE_MERGED":
                mx += t.pill("Merged #%d" % pr["number"], mx, my, t.PURPLE, t.PURPLE_BG, t.XS, 5,
                             t.g_merged) + 6
            elif card["status"] != "completed":
                mx += t.pill(t.cap(card["status"]), mx, my, t.RED, t.RED_BG) + 6
            t.text(t.ago(card["updated"]), mx, my + 1, t.XS, t.MUTED)
        elif column == "verify":
            pr = card.get("pr")
            if pr:
                mx += t.pill("PR #%d" % pr["number"], mx, my, t.GREEN, t.GREEN_BG, t.XS, 5, t.g_pr) + 6
            t.text("Ready for review", mx, my + 1, t.XS, t.MUTED)
            t.right(t.ago(card["updated"]), x + w - 10, my + 1, t.XS, t.MUTED)
        else:
            status = card["status"]
            if status == "running":
                since = card.get("started")
                now = t.Clock.now()
                spent = t.duration(now - since) if since and now else ""
                label = "Agent working" + (" - " + spent if spent else "")
                color = t.BLUE
            elif status == "queued":
                label, color = "Queued", t.MUTED
            elif status == "failed":
                label, color = "Step failed - open to see why", t.RED
            else:
                label, color = "Waiting", t.AMBER
            t.text(label, mx, my + 1, t.XS, color)

    def draw(self, app):
        t.fill(0, 0, screen.width, screen.height, t.PAGE)
        cols = self.columns(app)
        self.draw_header(app)
        if not cols:
            return
        self.col = min(self.col, len(cols) - 1)
        self.draw_tabs(app, cols)
        col = cols[self.col]
        base = t.lane_rgb(lane_name(app, col))
        lane_h = screen.height - 18 - LANE_Y
        t.box(4, LANE_Y, screen.width - 8, lane_h, t.rgb(base), 6)
        subtitle, glyph = SUBTITLES[col["kind"]]
        if "%s" in subtitle:
            subtitle = subtitle % col["title"]
        dark = t.rgb(t.shade(base, 0.38))
        glyph(16, LANE_Y + 10, dark)
        t.text(t.fit(subtitle, screen.width - 50, t.SM), 26, LANE_Y + 4, t.SM, dark)

        cards = self.cards(app, col["key"])
        if not cards:
            empty = "Nothing here." if col["kind"] == "phase" else "No tasks in %s." % col["title"]
            t.center(empty, screen.width / 2, LANE_Y + 64, t.MD, dark)
            if col["kind"] == "backlog":
                t.center("New GitHub issues land here.", screen.width / 2, LANE_Y + 82, t.XS, dark)
            self.draw_footer(app, None)
            return

        key = col["key"]
        index = min(self.sel.get(key, 0), len(cards) - 1)
        self.sel[key] = index
        step = CARD_H + CARD_GAP
        visible = (screen.height - 20 - LIST_Y) // step
        first = self.scroll.get(key, 0)
        if index < first:
            first = index
        if index >= first + visible:
            first = index - visible + 1
        self.scroll[key] = first
        y = LIST_Y
        bottom = screen.height - 20
        for i in range(first, len(cards)):
            if y + CARD_H > bottom + 12:
                break
            self.draw_card(app, cards[i], 10, y, screen.width - 20, i == index)
            y += step
        if len(cards) > visible:
            track = bottom - LIST_Y
            bar = max(14, track * visible // len(cards))
            pos = (track - bar) * first // max(1, len(cards) - visible)
            t.box(screen.width - 7, LIST_Y + pos, 2, bar, t.rgb(t.shade(base, 0.6)), 1)
        # fade the lane edge under the footer
        t.fill(4, bottom + 1, screen.width - 8, 2, t.rgb(base))
        self.draw_footer(app, cards[index])

    def draw_footer(self, app, card):
        items = [("L/R", "lanes"), ("U/D", "tasks")]
        if card:
            items.append(("SELECT", "open"))
        items.append(("MENU", "refresh"))
        t.hints(items)
