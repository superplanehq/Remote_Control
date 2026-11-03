# Factory Remote - run your SuperPlane AI software factory from your badge.
#
# Board  -> the factory dashboard: Backlog, the line's steps, Verify, Done.
# Task   -> details, progress, and the button that moves it forward:
#           Backlog: hold SELECT to start it on the line (agent implements it)
#           Verify:  hold SELECT to merge its pull request (task moves to Done)
# Diff   -> the files the agent changed, line by line.
import gc
import os
import sys

APP_DIR = os.getcwd()
APP_FILE = globals().get("__file__", "")
if "/" in APP_FILE:
    APP_DIR = APP_FILE.rsplit("/", 1)[0] or "/"
    if not APP_DIR.startswith("/"):
        APP_DIR = os.getcwd().rstrip("/") + "/" + APP_DIR

APP_DIRS = (
    APP_DIR,
    "/remote/apps/factory-remote",
    "/system/apps/factory-remote",
    "/apps/factory-remote",
    "/factory-remote",
    "/",
)
for app_dir in APP_DIRS:
    try:
        os.stat(app_dir.rstrip("/") + "/superplane.py")
        APP_DIR = app_dir
        break
    except OSError:
        pass

os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

import compat  # noqa: E402,F401  (maps buttons in the web simulator)

badge.mode(HIRES | VSYNC)
# Only redraw when something changed; the board is mostly still.
badge.default_clear = None
screen.antialias = image.X2

import config  # noqa: E402
import theme as t  # noqa: E402
from board import Board  # noqa: E402
from core import Job, make_backend  # noqa: E402
from detail import Detail  # noqa: E402
from diff import Diff  # noqa: E402

TOAST_MS = 3500
ALERT_MS = 6000


class App:
    def __init__(self):
        self.backend = make_backend()
        self.cards = None
        self.job = None
        self.job_quiet = False
        self.on_done = None
        self.on_fail = None
        self.connected = False
        self.error = ""
        self.sync_error = False
        self.synced_at = None
        self.board_stale = False
        demo = self.backend.demo
        self.refresh_ms = 3000 if demo else max(5, config.REFRESH_SECONDS) * 1000
        self.detail_refresh_ms = 2000 if demo else max(3, config.DETAIL_REFRESH_SECONDS) * 1000
        self.next_refresh = 0
        self.scene = "board"
        self.board = Board()
        self.detail = Detail()
        self.diff = Diff()
        self.toast_text = ""
        self.toast_kind = "info"
        self.toast_until = 0
        self.alert_until = 0
        self.lights_at = 0
        self.lights_on = None
        self._dirty = True
        self.animating = False
        self.drawn_at = 0
        self.connect()

    # ------------------------------------------------------------ plumbing
    def dirty(self):
        self._dirty = True

    def toast(self, message, kind="info"):
        self.toast_text = message
        self.toast_kind = kind
        self.toast_until = badge.ticks + TOAST_MS
        self.dirty()

    def run(self, job, quiet=False, on_done=None, on_fail=None):
        self.job = job
        self.job_quiet = quiet
        self.on_done = on_done
        self.on_fail = on_fail
        self.dirty()

    def tick_job(self):
        if self.job is None:
            return
        before = (self.job.index, self.job.state, self.job.waiting)
        state = self.job.tick()
        if (self.job.index, state, self.job.waiting) != before:
            self.dirty()
        if state == Job.RUNNING:
            return
        job = self.job
        done, fail = self.on_done, self.on_fail
        self.job = None
        self.on_done = self.on_fail = None
        gc.collect()
        if state == Job.DONE and done:
            done()
        elif state == Job.FAILED:
            if fail:
                fail(job.error)
            else:
                self.toast(job.error, "error")
        self.dirty()

    # ------------------------------------------------------------ data
    def connect(self):
        self.error = ""

        def ok():
            self.connected = True

        def fail(message):
            self.error = message

        self.run(Job([("Connecting to SuperPlane", self.backend.connect),
                      ("Loading the factory board", self.load_board)]), on_done=ok, on_fail=fail)

    def load_board(self):
        old = self.cards or {}
        cards = self.backend.board()
        if self.cards is not None:
            before = set(c["id"] for c in old.get("verify") or [])
            for card in cards.get("verify") or []:
                if card["id"] not in before:
                    self.toast("%s is ready to review" % card["key"], "ok")
                    self.alert_until = badge.ticks + ALERT_MS
                    break
        self.cards = cards
        self.synced_at = badge.ticks
        self.sync_error = False
        self.next_refresh = badge.ticks + self.refresh_ms
        self.board_stale = False

    def refresh(self, force=False):
        if self.job is not None or not self.connected:
            return
        if force or badge.ticks >= self.next_refresh or self.board_stale:
            def fail(message):
                self.sync_error = True
                self.next_refresh = badge.ticks + self.refresh_ms
                if force:
                    self.toast(message, "error")
            self.run(Job([("Refreshing the board", self.load_board)]), quiet=True, on_fail=fail)

    def act(self, job, card, message):
        """Run an action, refresh the board, then show where the task went."""
        job.steps.append(("Updating the board", self.load_board))

        def done():
            new_column = None
            for key, cards in (self.cards or {}).items():
                for c in cards:
                    if c["id"] == card["id"]:
                        new_column = key
            title = "Done"
            for col in self.board.columns(self):
                if col["key"] == new_column:
                    title = col["title"]
            self.scene = "board"
            if new_column:
                self.board.focus(self, new_column, card["id"])
            if new_column and new_column != card["column"]:
                self.toast("%s - %s moved to %s" % (message, card["key"], title), "ok")
            else:
                self.toast("%s - the board will update shortly" % message, "ok")
                self.next_refresh = badge.ticks + 4000

        self.run(job, on_done=done)

    # ------------------------------------------------------------ lights
    def lights(self):
        if badge.ticks - self.lights_at < 60:
            return
        self.lights_at = badge.ticks
        cards = self.cards or {}
        now = badge.ticks
        if now < self.alert_until:
            on = 1.0 if (now // 150) % 2 == 0 else 0.0
            values = (on, on, on, on)
        elif cards.get("verify"):
            phase = (now % 2400) / 2400
            level = 0.15 + 0.6 * (1 - abs(phase * 2 - 1))
            values = (level, level, level, level)
        elif any(c["status"] == "running" for k, cs in cards.items() if k.startswith("phase") for c in cs):
            lit = (now // 250) % 4
            values = tuple(0.6 if i == lit else 0.05 for i in range(4))
        else:
            values = (0, 0, 0, 0)
        if values != self.lights_on:
            self.lights_on = values
            try:
                badge.caselights(*values)
            except (AttributeError, TypeError, ValueError, OSError):
                pass

    # ------------------------------------------------------------ screens
    def draw_splash(self):
        t.fill(0, 0, screen.width, screen.height, t.PAGE)
        cx = screen.width // 2
        lanes = ("plain", "slate", "yellow", "lime")
        for i, lane in enumerate(lanes):
            t.box(cx - 46 + i * 24, 58, 20, 34, t.rgb(t.lane_rgb(lane)), 4)
            t.box(cx - 43 + i * 24, 62 + (i % 2) * 8, 14, 9, t.CARD, 2)
        t.center("Factory Remote", cx, 104, t.XL, t.INK)
        t.center("Run your SuperPlane factory from your badge", cx, 126, t.SM, t.MUTED)
        if self.error:
            for i, row in enumerate(t.wrap(self.error, screen.width - 50, t.SM, 4)):
                t.center(row, cx, 152 + i * 15, t.SM, t.RED)
            t.hints((("SELECT", "try again"),))
        elif self.job is not None:
            t.g_spinner(cx - t.measure(self.job.label, t.SM) / 2 - 10, 160, t.BLUE)
            t.center(self.job.label, cx + 6, 154, t.SM, t.TEXT)
            self.animating = True

    def draw(self):
        self.animating = False
        self._dirty = False  # a screen may ask for another frame while drawing
        if not self.connected:
            self.draw_splash()
        elif self.scene == "board":
            self.board.draw(self)
        elif self.scene == "detail":
            self.detail.draw(self)
        else:
            self.diff.draw(self)
        if badge.ticks < self.toast_until:
            t.toast(self.toast_text, self.toast_kind)
        self.drawn_at = badge.ticks

    def update(self):
        self.tick_job()
        self.lights()

        if not self.connected:
            if self.error and self.job is None and badge.pressed(BUTTON_SELECT):
                self.connect()
        elif self.scene == "board":
            self.refresh()
            result = self.board.update(self)
            if result and result[0] == "open":
                self.detail.open(self, result[1])
                self.scene = "detail"
                self.dirty()
        elif self.scene == "detail":
            result = self.detail.update(self)
            if self.board_stale:
                self.refresh()
            if result and result[0] == "back":
                self.scene = "board"
                info = self.detail.info
                if info:
                    self.board.focus(self, info["column"], info["id"])
                self.refresh(force=self.board_stale)
                self.dirty()
            elif result and result[0] == "diff":
                self.diff.open(self.detail.files, result[1])
                self.scene = "diff"
                self.dirty()
        else:
            result = self.diff.update(self)
            if result and result[0] == "back":
                self.detail.focus = result[1] + 1
                self.scene = "detail"
                self.dirty()

        now = badge.ticks
        toast_live = self.toast_until and now < self.toast_until + 100
        if (self._dirty
                or (self.animating and now - self.drawn_at >= 66)
                or (toast_live and now - self.drawn_at >= 250)
                or now - self.drawn_at >= 1000):
            self.draw()


app = App()


def update():
    app.update()


run(update)
