# One task: what it is, where it is on the line, and the button that moves
# it forward. Backlog -> Start on the line. Verify -> Merge the pull request.
# Verify and Done also list the files the agent changed; SELECT opens a diff.
import theme as t
from core import Job

HOLD_MS = 1000
TOP = 28
BOTTOM_PAD = 18
ROW_H = 20


def stage_label(app, card):
    column = card["column"]
    if column == "backlog":
        return "Backlog"
    if column == "verify":
        return "Verify"
    if column == "done":
        return "Done"
    for stage in app.backend.line["stages"]:
        if "phase-%d" % stage["index"] == column:
            return stage["name"]
    return "In progress"


class Detail:
    def __init__(self):
        self.card = None
        self.info = None
        self.files = None
        self.files_error = ""
        self.merge = None
        self.focus = 0
        self.scroll = 0
        self.hold_start = None
        self.next_refresh = 0
        self.next_merge_check = 0
        self.content_h = 0
        self.focus_y = []
        self.retry_at = 0

    def open(self, app, card):
        self.card = card
        self.info = None
        self.files = None
        self.files_error = ""
        self.merge = None
        self.focus = 0
        self.scroll = 0
        self.hold_start = None
        self.next_refresh = 0
        self.next_merge_check = 0
        self.retry_at = 0

    # ------------------------------------------------------------ data
    @property
    def view(self):
        return self.info or self.card

    def pr(self):
        return (self.view or {}).get("pr")

    def wants_files(self):
        return self.view["column"] in ("verify", "done") and self.pr() is not None

    def load(self, app, force=False):
        """Queue whatever this screen still needs. One request per frame."""
        if app.job is not None:
            return
        now = badge.ticks
        if now < self.retry_at and not force:
            return
        backend = app.backend
        card = self.card
        steps = []
        live = self.view["column"].startswith("phase") or self.view["column"] == "verify"
        if self.info is None or force or (live and now >= self.next_refresh):
            def refresh():
                info = backend.detail(card["id"])
                moved = self.info is not None and info["column"] != self.info["column"]
                self.info = info
                if moved:
                    app.board_stale = True
                self.next_refresh = badge.ticks + app.detail_refresh_ms
            steps.append(("Loading %s" % card["key"], refresh))
        if self.wants_files() and self.files is None and not self.files_error:
            def files():
                try:
                    self.files = backend.files(self.pr())
                except Exception as error:  # noqa: BLE001
                    self.files_error = getattr(error, "message", None) or str(error)
            steps.append(("Loading changes", files))
        if self.view["column"] == "verify" and self.pr() and now >= self.next_merge_check:
            def merge_check():
                self.next_merge_check = badge.ticks + 4000
                self.merge = backend.mergeability(self.pr())
                self.next_merge_check = badge.ticks + (4000 if not self.merge["can_merge"] else 15000)
            steps.append(("Checking the pull request", merge_check))
        if steps:
            def failed(message):
                # back off instead of retrying every frame
                self.retry_at = badge.ticks + 5000
                app.toast(message, "error")
            app.run(Job(steps), quiet=True, on_fail=failed)

    # ------------------------------------------------------------ action
    def action(self, app):
        """(label, enabled, colour, glyph) for the primary button."""
        view = self.view
        column = view["column"]
        if column == "backlog":
            stages = app.backend.line["stages"]
            name = stages[0]["name"] if stages else "the line"
            return ("Hold to start on %s" % name, True, t.PURPLE, None)
        if column == "verify":
            pr = self.pr()
            if not pr:
                return ("No pull request yet", False, t.FAINT, None)
            if self.merge is None:
                return ("Checking pull request #%d..." % pr["number"], False, t.FAINT, t.g_spinner)
            if self.merge["can_merge"]:
                return ("Hold to merge PR #%d" % pr["number"], True, t.GREEN, t.g_merged)
            reason = self.merge["message"] or self.merge["reason"].replace("BLOCKED_REASON_", "").replace(
                "_", " ").lower() or "blocked"
            return ("Can't merge yet: " + reason, False, t.AMBER, t.g_clock)
        if column == "done":
            pr = self.pr()
            if pr and pr["state"] == "STATE_MERGED":
                return ("Merged as PR #%d" % pr["number"], False, t.PURPLE, t.g_merged)
            return ("Closed: %s" % view["status"], False, t.MUTED, None)
        status = view["status"]
        if status == "running":
            return ("Agent is working on it", False, t.BLUE, t.g_spinner)
        if status == "queued":
            return ("Queued for the agent", False, t.MUTED, t.g_clock)
        if status == "failed":
            return ("The step failed. Retry it in SuperPlane.", False, t.RED, t.g_cross_circle)
        return ("Waiting on the agent", False, t.AMBER, t.g_clock)

    def do_action(self, app):
        backend = app.backend
        card = self.view
        column = card["column"]
        if column == "backlog":
            def start():
                backend.start(card)
            app.act(Job([("Starting %s" % card["key"], start)]), card, "Started %s" % card["key"])
        elif column == "verify":
            pr = self.pr()

            def merge():
                fresh = backend.mergeability(pr)
                if not fresh["can_merge"]:
                    self.merge = fresh
                    raise ValueError(fresh["message"] or "the pull request can't be merged right now")
                backend.merge(pr, fresh)
            app.act(Job([("Merging PR #%d" % pr["number"], merge)]), card, "Merged PR #%d" % pr["number"])

    # ------------------------------------------------------------ input
    def update(self, app):
        self.load(app)
        enabled = self.action(app)[1]
        focusables = len(self.focus_y) or 1
        if badge.pressed(BUTTON_BACK):
            return ("back", None)
        if badge.pressed(BUTTON_DOWN):
            if self.focus < focusables - 1:
                self.focus += 1
            else:
                self.scroll = min(self.scroll + 30, max(0, self.content_h - self.view_h()))
            app.dirty()
        elif badge.pressed(BUTTON_UP):
            if self.focus > 0:
                self.focus -= 1
            else:
                self.scroll = max(0, self.scroll - 30)
            app.dirty()
        elif badge.pressed(BUTTON_MENU):
            self.files = None
            self.files_error = ""
            self.next_merge_check = 0
            self.load(app, force=True)

        # hold SELECT on the action button; SELECT on a file opens its diff
        if self.focus == 0 and enabled and app.job is None:
            if badge.held(BUTTON_SELECT):
                if self.hold_start is None:
                    self.hold_start = badge.ticks
                app.animating = True
                if badge.ticks - self.hold_start >= HOLD_MS:
                    self.hold_start = None
                    self.do_action(app)
            elif self.hold_start is not None:
                self.hold_start = None
                app.dirty()
        elif self.focus > 0 and badge.pressed(BUTTON_SELECT) and self.files:
            return ("diff", self.focus - 1)
        return None

    def view_h(self):
        return screen.height - BOTTOM_PAD - TOP - 4

    # ------------------------------------------------------------ drawing
    def draw(self, app):
        t.fill(0, 0, screen.width, screen.height, t.CARD)
        view = self.view
        x = 12
        w = screen.width - 24
        self.focus_y = []
        y0 = TOP + 6 - self.scroll
        y = y0

        # title and meta
        for row in t.wrap(view["title"], w, t.LG, 3):
            t.text(row, x, y, t.LG, t.INK)
            y += 17
        y += 2
        mx = x
        if view.get("origin", "").find("github.com") >= 0:
            t.g_github(mx + 5, y + 6, t.INK)
            mx += 14
        meta = []
        if view.get("origin_label"):
            meta.append(view["origin_label"])
        if view.get("created"):
            meta.append("opened " + t.ago(view["created"]))
        if view.get("assignee"):
            meta.append(view["assignee"])
        t.text(t.fit("  -  ".join(meta), w - (mx - x), t.XS), mx, y + 1, t.XS, t.MUTED)
        y += 18

        # primary button
        label, enabled, tone, glyph = self.action(app)
        self.focus_y.append(y)
        focused = self.focus == 0
        if enabled:
            t.box(x, y, w, 28, tone, 7)
            if self.hold_start is not None:
                progress = min(1.0, (badge.ticks - self.hold_start) / HOLD_MS)
                t.box(x, y, max(14, int(w * progress)), 28, t.rgb((255, 255, 255), 70), 7)
            if focused:
                t.frame(x - 2, y - 2, w + 4, 32, t.FOCUS, 9, 2)
            t.center(label, x + w / 2, y + 7, t.MD, t.WHITE)
        else:
            t.box(x, y, w, 28, t.PAGE, 7)
            t.frame(x, y, w, 28, t.BORDER, 7)
            tx = x + 10
            if glyph:
                glyph(x + 14, y + 14, tone)
                tx = x + 26
                if glyph is t.g_spinner:
                    app.animating = True
            t.text(t.fit(label, w - (tx - x) - 8, t.SM), tx, y + 8, t.SM, tone)
        y += 38

        # progress through the line
        if view.get("steps"):
            y = self.section(x, y, w, "Progress")
            for step in view["steps"]:
                mark = step["mark"]
                if mark == "running":
                    t.g_spinner(x + 6, y + 6, t.BLUE)
                    app.animating = True
                elif mark == "passed":
                    t.g_check_circle(x + 6, y + 6, t.GREEN)
                elif mark in ("failed", "cancelled"):
                    t.g_cross_circle(x + 6, y + 6, t.RED)
                else:
                    t.g_dashed_circle(x + 6, y + 6, t.FAINT)
                t.text(step["name"], x + 18, y, t.SM, t.INK)
                seconds = step.get("seconds")
                if mark == "running" and step.get("started") and t.Clock.now():
                    seconds = t.Clock.now() - step["started"]
                if seconds:
                    t.right(t.duration(seconds), x + w, y, t.SM, t.MUTED)
                y += 16
            y += 4
        for note in view.get("notes") or []:
            t.text(t.fit(note, w, t.XS), x, y, t.XS, t.AMBER)
            y += 13
        if view.get("notes"):
            y += 4

        # pull request and changes
        pr = view.get("pr")
        if pr:
            y = self.section(x, y, w, "Pull request")
            t.g_pr(x + 6, y + 6, t.GREEN if pr["state"] == "STATE_OPEN" else t.PURPLE)
            state = {"STATE_OPEN": "Open", "STATE_MERGED": "Merged", "STATE_DRAFT": "Draft",
                     "STATE_CLOSED": "Closed"}.get(pr["state"], "")
            sw = t.measure(state, t.XS) + 10 if state else 0
            t.text(t.fit("#%d %s" % (pr["number"], pr["title"]), w - 24 - sw, t.SM), x + 18, y, t.SM, t.INK)
            if state:
                fg, bg = (t.GREEN, t.GREEN_BG) if state == "Open" else (t.PURPLE, t.PURPLE_BG)
                t.pill(state, x + w - sw, y - 1, fg, bg, t.XS, 5)
            y += 16
            if pr.get("repo"):
                t.text(pr["repo"], x + 18, y, t.XS, t.MUTED)
                y += 14
            y += 4
        if self.wants_files():
            y = self.draw_files(app, x, y, w)

        # what the agent did
        if view.get("activity"):
            y = self.section(x, y, w, "What the agent did")
            for item in view["activity"][:3]:
                if item["title"]:
                    t.text(t.fit(item["title"], w, t.SM), x, y, t.SM, t.INK)
                    y += 14
                for row in t.wrap(item["body"], w, t.XS, 3):
                    t.text(row, x, y, t.XS, t.TEXT)
                    y += 12
                y += 4

        # scores
        checks = [c for c in view.get("checks") or [] if c["score"] is not None]
        if checks:
            y = self.section(x, y, w, "Scores")
            for check in checks[:4]:
                t.text(t.fit(check["name"], w - 60, t.SM), x, y, t.SM, t.INK)
                if check["max"] == 5 or check["name"] in ("Confidence score", "Clarity score"):
                    t.meter(x + w - 29, y + 3, int(check["score"] + 0.5))
                elif check["format"] == "FORMAT_PERCENT":
                    t.right("%d%%" % check["score"], x + w, y, t.SM, t.MUTED)
                else:
                    t.right("%g / %g" % (check["score"], check["max"] or 1), x + w, y, t.SM, t.MUTED)
                y += 14
                for row in t.wrap(check["summary"], w, t.XS, 2):
                    t.text(row, x, y, t.XS, t.MUTED)
                    y += 12
                y += 4

        if view.get("description"):
            y = self.section(x, y, w, "Description")
            for row in t.wrap(view["description"], w, t.XS, 8):
                t.text(row, x, y, t.XS, t.TEXT)
                y += 12
            y += 4

        if self.info is None:
            t.text("Loading details...", x, y, t.XS, t.MUTED)
            y += 14
        if view.get("cost_cents") or view.get("seconds"):
            parts = []
            if view.get("seconds"):
                parts.append("agent time " + t.duration(view["seconds"]))
            if view.get("cost_cents"):
                parts.append("cost $%d.%02d" % (view["cost_cents"] // 100, view["cost_cents"] % 100))
            t.text("  -  ".join(parts), x, y, t.XS, t.FAINT)
            y += 14

        self.content_h = y - y0 + 10
        self.keep_focus_visible(app)
        self.draw_header(app, view)
        self.draw_footer(app)

    def keep_focus_visible(self, app):
        if not self.focus_y:
            return
        self.focus = min(self.focus, len(self.focus_y) - 1)
        fy = self.focus_y[self.focus]
        top = TOP + 4
        bottom = screen.height - BOTTOM_PAD - 24
        if fy < top:
            self.scroll = max(0, self.scroll - (top - fy))
            app.dirty()
        elif fy > bottom:
            self.scroll += fy - bottom
            app.dirty()

    def section(self, x, y, w, title):
        t.line(x, y, x + w, y, t.BORDER, 1)
        t.text(title.upper(), x, y + 6, t.XS, t.MUTED)
        return y + 22

    def draw_files(self, app, x, y, w):
        if self.files is None:
            y = self.section(x, y, w, "Changes")
            if self.files_error:
                for row in t.wrap("Couldn't load the changes: " + self.files_error, w, t.XS, 3):
                    t.text(row, x, y, t.XS, t.RED)
                    y += 12
            else:
                t.g_spinner(x + 6, y + 6, t.MUTED)
                app.animating = True
                t.text("Loading the files the agent changed...", x + 18, y, t.XS, t.MUTED)
                y += 14
            return y + 6
        add = 0
        delete = 0
        for f in self.files:
            add += f["add"]
            delete += f["del"]
        t.line(x, y, x + w, y, t.BORDER, 1)
        title = "CHANGES  %d FILE%s" % (len(self.files), "" if len(self.files) == 1 else "S")
        t.text(title, x, y + 6, t.XS, t.MUTED)
        tail = "-%d" % delete
        t.right(tail, x + w, y + 6, t.XS, t.RED)
        t.right("+%d" % add, x + w - t.measure(tail, t.XS) - 6, y + 6, t.XS, t.GREEN)
        y += 22
        for i, f in enumerate(self.files):
            self.focus_y.append(y)
            focused = self.focus == i + 1
            if focused:
                t.box(x - 4, y - 3, w + 8, ROW_H - 2, t.BLUE_BG, 5)
            t.g_file(x + 5, y + 6, t.MUTED)
            counts = "+%d -%d" % (f["add"], f["del"])
            cw = t.measure(counts, t.XS)
            name = f["name"]
            short = name if t.measure(name, t.SM) <= w - cw - 34 else ".../" + name.rsplit("/", 1)[-1]
            t.text(t.fit(short, w - cw - 34, t.SM), x + 16, y, t.SM, t.INK)
            minus = "-%d" % f["del"]
            t.right(minus, x + w - 10, y + 1, t.XS, t.RED)
            t.right("+%d" % f["add"], x + w - 14 - t.measure(minus, t.XS), y + 1, t.XS, t.GREEN)
            t.g_chevron(x + w - 2, y + 6, t.FAINT)
            y += ROW_H
        return y + 6

    def draw_header(self, app, view):
        t.fill(0, 0, screen.width, TOP - 2, t.CARD)
        t.line(0, TOP - 2, screen.width, TOP - 2, t.BORDER, 1)
        t.text(view["key"], 10, 7, t.SM, t.MUTED)
        kx = 16 + t.measure(view["key"], t.SM)
        from board import lane_name

        column = view["column"]
        kind = "phase" if column.startswith("phase") else column
        base = t.lane_rgb(lane_name(app, {"key": column, "kind": kind}))
        t.pill(stage_label(app, view), kx, 6, t.rgb(t.shade(base, 0.35)), t.rgb(base), t.XS, 6)
        if app.job is not None:
            t.g_spinner(screen.width - 14, 13, t.MUTED)
            app.animating = True
        elif app.backend.demo:
            t.pill("DEMO", screen.width - 46, 6, t.AMBER, t.AMBER_BG, t.XS, 5)

    def draw_footer(self, app):
        label, enabled, _, _ = self.action(app)
        items = [("U/D", "move")]
        if self.focus == 0 and enabled:
            items.append(("SELECT", "hold"))
        elif self.focus > 0 and self.files:
            items.append(("SELECT", "view diff"))
        items.append(("BACK", "board"))
        items.append(("MENU", "refresh"))
        t.hints(items)
