# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Colours, spacing and fonts — the look of the program in one place.

Everything here is derived from the system's own colours rather than
written down as fixed values. That is not laziness: a program that hard
codes light grey on white looks wrong the moment someone switches
Windows to its dark theme, and becomes unreadable the moment they switch
to a high contrast one — which the people this program is built for are
the most likely to do.

So the rules are:

* Colours are worked out from the current system palette.
* Differences are kept small enough that text contrast never suffers.
  The row shading below shifts the background by about five per cent,
  which the eye picks up as a stripe while leaving black-on-white
  black-on-white.
* Under a high contrast theme the shading is dropped altogether. High
  contrast themes are a promise that only the chosen colours appear, and
  decoration that ignores that promise does real harm.
* The light or dark choice is the user's, from the View menu, and
  defaults to whatever Windows is set to. A high contrast theme overrules
  the choice entirely: those colours are chosen by someone who needs
  exactly them.

Two honest limits. The menu bar and the drop-down part of a combo box
are drawn by Windows itself and take no colour from a program, so they
stay light whatever is chosen here. And the title bar is asked to go
dark through the window manager, which older builds of Windows 10 may
decline.
"""

from __future__ import annotations

import ctypes

import wx

# Spacing, in pixels, used throughout the windows. Named rather than
# sprinkled as numbers so the whole program breathes at one rate.
GAP_TIGHT = 4
GAP = 8
GAP_WIDE = 14
MARGIN = 12

# How tall a row in the contacts table should be. The default is cramped:
# a taller row is easier to track across the screen and easier to hit
# with a mouse.
ROW_HEIGHT = 26

# Icon sizes.
TOOLBAR_ICON = (24, 24)
FIELD_ICON = (16, 16)


# What the user picked in the View menu.
FOLLOW_SYSTEM = "system"
LIGHT = "light"
DARK = "dark"
MODES = (FOLLOW_SYSTEM, LIGHT, DARK)

# Dark out of the box: this program is used for long stretches of data
# entry, and a dark ground is easier on the eyes over an hour of it. The
# View menu offers the other two for anyone who prefers them.
_mode = DARK

# The dark palette. Not pure black: a near-black ground with off-white
# text sits at about thirteen to one, comfortably past the contrast the
# guidelines ask for, without the harsh edge of true black and true white.
_DARK_WINDOW = wx.Colour(31, 31, 31)
_DARK_TEXT = wx.Colour(232, 232, 232)
_DARK_PANEL = wx.Colour(43, 43, 43)


def set_mode(mode: str) -> str:
    """Choose light, dark, or whatever Windows is set to."""
    global _mode
    _mode = mode if mode in MODES else FOLLOW_SYSTEM
    return _mode


def get_mode() -> str:
    return _mode


def system_is_dark() -> bool:
    """Whether Windows itself is currently set to a dark theme."""
    try:
        appearance = wx.SystemSettings.GetAppearance()
        return bool(appearance.IsDark())
    except AttributeError:
        pass
    # Older wx: judge by how bright the window colour is.
    colour = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)
    brightness = (colour.Red() * 299 + colour.Green() * 587
                  + colour.Blue() * 114) / 1000
    return brightness < 128


def is_dark() -> bool:
    """Whether to paint dark, taking the user's choice into account.

    A high contrast theme wins over everything: its colours were chosen
    by someone who needs those exact colours, and a program that paints
    over them takes away the reason they turned it on.
    """
    if is_high_contrast():
        return False
    if _mode == DARK:
        return True
    if _mode == LIGHT:
        return False
    return system_is_dark()


# Asking the system costs a call into user32, and the answer is wanted
# once per widget while a window is being built. It is remembered here,
# and forgotten again if Windows reports the setting has changed.
_high_contrast: bool | None = None


def forget_theme() -> None:
    """Drop the remembered answer, after Windows changes its theme."""
    global _high_contrast
    _high_contrast = None


def is_high_contrast() -> bool:
    """Whether Windows is running one of its high contrast themes.

    Asked of the system directly, because wx has no equivalent. A failure
    to ask is treated as "no", which only means the gentle shading stays
    on — never that something becomes unreadable.
    """
    global _high_contrast
    if _high_contrast is not None:
        return _high_contrast

    class _HighContrast(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_uint),
            ("dwFlags", ctypes.c_uint),
            ("lpszDefaultScheme", ctypes.c_wchar_p),
        ]

    try:
        info = _HighContrast()
        info.cbSize = ctypes.sizeof(_HighContrast)
        spi_get_high_contrast = 0x0042
        ok = ctypes.windll.user32.SystemParametersInfoW(
            spi_get_high_contrast, info.cbSize, ctypes.byref(info), 0
        )
        if ok:
            _high_contrast = bool(info.dwFlags & 0x00000001)  # HCF_HIGHCONTRASTON
            return _high_contrast
    except (AttributeError, OSError, ValueError):
        pass
    _high_contrast = False
    return False


def blend(first: wx.Colour, second: wx.Colour, amount: float) -> wx.Colour:
    """Mix two colours, `amount` being how much of the second to take."""
    amount = max(0.0, min(1.0, amount))
    return wx.Colour(
        int(first.Red() + (second.Red() - first.Red()) * amount),
        int(first.Green() + (second.Green() - first.Green()) * amount),
        int(first.Blue() + (second.Blue() - first.Blue()) * amount),
    )


def window_colour() -> wx.Colour:
    """The background behind lists and text fields."""
    if is_dark():
        return _DARK_WINDOW
    return wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)


def text_colour() -> wx.Colour:
    """The colour of ordinary text."""
    if is_dark():
        return _DARK_TEXT
    return wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT)


def panel_colour() -> wx.Colour:
    """The background behind toolbars and forms.

    A shade away from the list background, so the bands of the window
    read as separate areas without a drawn line between them.
    """
    if is_high_contrast():
        return wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNFACE)
    if is_dark():
        return _DARK_PANEL
    return blend(window_colour(), text_colour(), 0.035)


def stripe_colour() -> wx.Colour | None:
    """The background for every other row, or None to leave rows alone."""
    if is_high_contrast():
        return None
    return blend(window_colour(), text_colour(), 0.05)


def accent_colour() -> wx.Colour:
    """The colour for the one button that matters most on a screen."""
    highlight = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
    return highlight if highlight.IsOk() else wx.Colour(0, 90, 158)


def heading_font(base: wx.Font | None = None) -> wx.Font:
    """A slightly heavier font for group captions and headings."""
    font = wx.Font(base) if base else wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
    font.SetWeight(wx.FONTWEIGHT_BOLD)
    return font


def enlarged_font(points: int = 1, base: wx.Font | None = None) -> wx.Font:
    """The system font, a touch larger — used for the search box."""
    font = wx.Font(base) if base else wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
    font.SetPointSize(font.GetPointSize() + points)
    return font


def icon_colour() -> str:
    """The colour to draw the icons in, as #RRGGBB.

    Light strokes on a dark ground and dark strokes on a light one. The
    drawings themselves carry no colour, so this is the only thing that
    decides it, and the icons follow the window without a second set of
    artwork.
    """
    colour = text_colour()
    if not is_dark() and not is_high_contrast():
        # In the ordinary case take the button text colour, which is what
        # the surrounding labels are drawn in.
        button_text = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNTEXT)
        if button_text.IsOk():
            colour = button_text
    return f"#{colour.Red():02x}{colour.Green():02x}{colour.Blue():02x}"


def _ask_for_dark_title_bar(window: wx.Window) -> None:
    """Ask Windows to draw this window's title bar dark.

    The attribute number changed between Windows 10 builds, so both are
    tried. A refusal costs nothing: the frame simply stays light while
    the inside of the window is dark, which is untidy but harmless.
    """
    try:
        handle = window.GetHandle()
        if not handle:
            return
        on = ctypes.c_int(1)
        for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(handle), ctypes.c_int(attribute),
                ctypes.byref(on), ctypes.sizeof(on))
    except (AttributeError, OSError, ValueError):
        pass


def _drop_windows_theme(window: wx.Window) -> None:
    """Stop Windows painting this control with its own theme.

    A themed drop-down ignores whatever colours a program asks for and
    stays bright white, which leaves a glaring box in the middle of a
    dark window. Removing the theme makes the control honour the colours
    again. It stays exactly the same kind of Windows control underneath —
    the same class, the same accessibility — so a screen reader notices
    no difference at all; only the painting changes.
    """
    try:
        handle = window.GetHandle()
        if handle:
            ctypes.windll.uxtheme.SetWindowTheme(
                ctypes.c_void_p(handle),
                ctypes.c_wchar_p(""), ctypes.c_wchar_p(""))
    except (AttributeError, OSError, ValueError):
        pass


def apply_window(window: wx.Window, skip: tuple = ()) -> None:
    """Paint a window and everything inside it in the chosen colours.

    Only does anything in dark mode: in light mode the system's own
    colours are already right, and leaving the controls alone keeps them
    native in every respect.
    """
    if not is_dark():
        return

    _ask_for_dark_title_bar(window)
    _paint(window, window_colour(), text_colour(), panel_colour(), set(skip))


def _paint(parent: wx.Window, window_bg: wx.Colour, fg: wx.Colour,
           panel_bg: wx.Colour, skip: set) -> None:
    """Walk the widget tree, giving each kind of control its colours."""
    for child in parent.GetChildren():
        if child in skip:
            continue

        try:
            if isinstance(child, (wx.TextCtrl, wx.ComboBox, wx.ListCtrl)):
                if isinstance(child, wx.ComboBox):
                    _drop_windows_theme(child)
                child.SetBackgroundColour(window_bg)
                child.SetForegroundColour(fg)
                if isinstance(child, wx.ListCtrl):
                    child.SetTextColour(fg)
            elif isinstance(child, wx.Choice):
                _drop_windows_theme(child)
                child.SetBackgroundColour(panel_bg)
                child.SetForegroundColour(fg)
            elif isinstance(child, (wx.Panel, wx.ScrolledWindow, wx.ToolBar,
                                    wx.StatusBar, wx.StaticBox, wx.Button,
                                    wx.CheckBox)):
                child.SetBackgroundColour(panel_bg)
                child.SetForegroundColour(fg)
            elif isinstance(child, (wx.StaticText, wx.StaticLine)):
                child.SetForegroundColour(fg)
        except (wx.wxAssertionError, AttributeError):
            pass

        _paint(child, window_bg, fg, panel_bg, skip)
