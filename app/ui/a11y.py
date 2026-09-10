# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Screen reader helpers.

wxPython draws with native Windows controls, so NVDA reads the buttons,
fields and tables on its own with no help from us. This module adds the
one thing that does need help: announcing events that have no visible
control behind them — "saved", "35 results" — which would otherwise pass
silently.

Announcements go out two ways:

1. If ``nvdaControllerClient64.dll`` sits next to the program, NVDA is
   told directly and speaks the message straight away. This is best.
2. Otherwise the message goes to the status bar and the action log,
   which the user can replay at any time with Ctrl+J.

The program is usable either way; the DLL is purely an improvement.
"""

from __future__ import annotations

import ctypes
from pathlib import Path

import wx

from ..i18n import t

_dll = None
_load_attempted = False

# File names differ by Windows build.
_DLL_NAMES = ("nvdaControllerClient64.dll", "nvdaControllerClient.dll")


def _load_controller():
    """Load NVDA's client library once, staying quiet if it is absent."""
    global _dll, _load_attempted
    if _load_attempted:
        return _dll
    _load_attempted = True

    search = [Path(__file__).resolve().parent.parent.parent, Path.cwd()]
    for name in _DLL_NAMES:
        for folder in search:
            candidate = folder / name
            if candidate.exists():
                try:
                    _dll = ctypes.windll.LoadLibrary(str(candidate))
                    return _dll
                except OSError:
                    pass
        # It may also be installed somewhere on the system path.
        try:
            _dll = ctypes.windll.LoadLibrary(name)
            return _dll
        except OSError:
            continue
    return None


def is_screen_reader_connected() -> bool:
    """Whether NVDA is running and reachable right now."""
    dll = _load_controller()
    if dll is None:
        return False
    try:
        return dll.nvdaController_testIfRunning() == 0
    except OSError:
        return False


def speak(message: str, interrupt: bool = False) -> bool:
    """Ask NVDA to speak a message. Returns False if that was not possible."""
    if not message:
        return False
    dll = _load_controller()
    if dll is None:
        return False
    try:
        if dll.nvdaController_testIfRunning() != 0:
            return False
        if interrupt:
            dll.nvdaController_cancelSpeech()
        dll.nvdaController_speakText(str(message))
        return True
    except (OSError, ValueError):
        return False


class Announcer:
    """Delivers messages to the user by every route available at once."""

    def __init__(self, frame: wx.Frame) -> None:
        self.frame = frame
        self.log: list[str] = []

    def say(self, message: str, interrupt: bool = False) -> None:
        """Announce a message: status bar, action log, and direct speech."""
        message = (message or "").strip()
        if not message:
            return

        self.log.append(message)
        del self.log[:-50]  # keep only the last 50 messages

        status_bar = self.frame.GetStatusBar()
        if status_bar:
            status_bar.SetStatusText(message, 0)

        speak(message, interrupt=interrupt)

    def last(self) -> str:
        return self.log[-1] if self.log else t("Nothing has happened yet.")

    def history_text(self) -> str:
        return "\n".join(reversed(self.log)) or t("Nothing has happened yet.")
