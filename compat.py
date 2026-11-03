# Runtime compatibility for the Pimoroni Badgeware Web Simulator.
#
# The Universe 2026 badge firmware provides eight logical actions
# (UP, DOWN, LEFT, RIGHT, SELECT, BACK, MENU, HOME). The web simulator runs the
# upstream Tufty 2350 runtime instead, which only has A, B, C, UP, DOWN and
# HOME, and it runs MicroPython in the browser (sys.platform "webassembly"),
# where the network is the browser's own.
#
# On the real badge this module changes nothing. In the simulator it maps:
#   LEFT   -> A      (left arrow key)
#   SELECT -> B      (space)
#   RIGHT  -> C      (right arrow key)
#   BACK   -> HOME   (Esc) - HOME is not wired to the launcher for editor runs
#   MENU   -> UP + DOWN pressed together
import builtins
import sys

WEB_SIMULATOR = sys.platform == "webassembly"

# Runtime globals are injected into builtins; MicroPython resolves them as bare
# names, but getattr(builtins, ...) does not see them, so probe by name.
try:
    BUTTON_SELECT  # noqa: B018
    NATIVE_ACTIONS = True
except NameError:
    NATIVE_ACTIONS = False


class _Virtual:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "<virtual %s>" % self.name


def _install_buttons():
    back = _Virtual("BACK")
    menu = _Virtual("MENU")
    up = BUTTON_UP
    down = BUTTON_DOWN
    home = BUTTON_HOME
    setattr(builtins, "BUTTON_LEFT", BUTTON_A)
    setattr(builtins, "BUTTON_SELECT", BUTTON_B)
    setattr(builtins, "BUTTON_RIGHT", BUTTON_C)
    setattr(builtins, "BUTTON_BACK", back)
    setattr(builtins, "BUTTON_MENU", menu)

    original_pressed = badge.pressed
    original_held = badge.held

    def menu_chord():
        return (original_pressed(up) and original_held(down)) or (
            original_pressed(down) and original_held(up)
        )

    def pressed(button=None):
        if button is None:
            return original_pressed()
        if button is back:
            return original_pressed(home)
        if button is menu:
            return menu_chord()
        if button is up or button is down:
            # don't also scroll when the MENU chord fires
            return original_pressed(button) and not menu_chord()
        return original_pressed(button)

    def held(button=None):
        if button is None:
            return original_held()
        if button is back:
            return original_held(home)
        if button is menu:
            return original_held(up) and original_held(down)
        return original_held(button)

    badge.pressed = pressed
    badge.held = held


if not NATIVE_ACTIONS:
    _install_buttons()

# Button labels for the on-screen key hints.
if NATIVE_ACTIONS:
    KEYS = {"U/D": "U/D", "L/R": "L/R", "SELECT": "SELECT", "BACK": "BACK", "MENU": "MENU"}
else:
    KEYS = {"U/D": "U/D", "L/R": "A/C", "SELECT": "B", "BACK": "ESC", "MENU": "U+D"}
