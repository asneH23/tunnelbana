"""The mode button: a push button on the Pi that switches between mode 1 and 2.

On the Mac (emulator) there is no button, so pressing Enter in the terminal
does the same thing. If anything goes wrong setting up the button, the board
simply runs without it.
"""

import logging
import sys
import threading

import config
from display import use_emulator

log = logging.getLogger("sl-skylt")


class ModeButton:
    def __init__(self):
        # The button is handled in a background thread, which sets this flag.
        # The main loop checks it with was_pressed().
        self._pressed = threading.Event()
        self._button = None  # keep a reference, or gpiozero forgets the button

        if use_emulator():
            self._listen_to_keyboard()
        elif config.BUTTON_GPIO is not None:
            self._listen_to_gpio(config.BUTTON_GPIO)

    def was_pressed(self):
        """True once for every press (since the last time we asked)."""
        if self._pressed.is_set():
            self._pressed.clear()
            return True
        return False

    def _listen_to_gpio(self, pin):
        try:
            from gpiozero import Button
            # pull_up=True: the pin is normally high and goes low when the
            # button connects it to ground. bounce_time ignores the tiny
            # flickers a mechanical button makes when it is pressed.
            self._button = Button(pin, pull_up=True, bounce_time=0.05)
            self._button.when_pressed = self._pressed.set
            log.info("Mode button ready on GPIO %s", pin)
        except Exception as error:  # gpiozero missing, pin busy, ...
            log.warning("Mode button disabled: %s", error)

    def _listen_to_keyboard(self):
        if not sys.stdin.isatty():
            return

        def read_lines():
            for _ in sys.stdin:  # every Enter gives one line
                self._pressed.set()

        threading.Thread(target=read_lines, daemon=True).start()
        log.info("Press Enter in this terminal to switch mode")
