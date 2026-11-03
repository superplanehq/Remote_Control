# Settings, Wi-Fi and step-by-step network jobs for Factory Remote.
import gc

import config
from compat import WEB_SIMULATOR
from superplane import ApiError

try:
    import secrets
except ImportError:
    secrets = None


def setting(name, default=""):
    value = getattr(secrets, name, "") if secrets else ""
    if not value:
        value = getattr(config, name, "") or default
    return value.strip() if isinstance(value, str) else value


def make_backend():
    token = setting("SUPERPLANE_TOKEN")
    if not token:
        from demo import Demo

        return Demo()
    from superplane import SuperPlane

    return SuperPlane(
        setting("SUPERPLANE_URL", "https://app.superplane.com"),
        token,
        setting("SUPERPLANE_WORKSPACE"),
        setting("SUPERPLANE_LINE"),
        setting("GITHUB_TOKEN"),
    )


def wifi_status():
    """("ok" | "connecting" | "missing", message)."""
    if WEB_SIMULATOR:
        return ("ok", "")
    ssid = setting("WIFI_SSID")
    if not ssid:
        return ("missing", "Wi-Fi isn't set up. Double-tap RESET for disk mode and add "
                           "WIFI_SSID and WIFI_PASSWORD to secrets.py.")
    import wifi

    if wifi.connect():
        return ("ok", "")
    return ("connecting", "Connecting to %s..." % ssid)


class Job:
    """Runs (label, fn) steps one per frame, after a frame that shows the label."""

    RUNNING = 1
    DONE = 2
    FAILED = 3

    def __init__(self, steps, network=True):
        self.steps = steps
        self.index = 0
        self.network = network
        self.state = Job.RUNNING
        self.error = ""
        self.armed = False
        self.waiting = ""
        self.started = badge.ticks

    @property
    def label(self):
        if self.waiting:
            return self.waiting
        if self.index < len(self.steps):
            return self.steps[self.index][0]
        return ""

    def tick(self):
        if self.state != Job.RUNNING:
            return self.state
        if not self.armed:
            self.armed = True
            return self.state
        if self.network:
            status, message = wifi_status()
            if status == "missing":
                return self.fail(message)
            if status == "connecting":
                self.waiting = message
                return self.state
            self.waiting = ""
        label, step = self.steps[self.index]
        try:
            step()
        except ApiError as error:
            return self.fail(error.message)
        except Exception as error:  # noqa: BLE001 - shown on screen, never crash
            return self.fail("%s failed: %s" % (label, error))
        self.index += 1
        self.armed = False
        if self.index >= len(self.steps):
            self.state = Job.DONE
        return self.state

    def fail(self, message):
        self.state = Job.FAILED
        self.error = message or "Something went wrong"
        gc.collect()
        return self.state
