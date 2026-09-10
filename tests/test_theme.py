# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Theme tests.

The interesting ones here are the contrast checks. A dark theme that
looks stylish but puts grey text on a grey ground is worse than no dark
theme at all, so the colours are measured against the WCAG contrast
formula rather than eyeballed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _harness import check, finish, setup  # noqa: E402

setup()

import wx  # noqa: E402

from app.ui import icons, theme  # noqa: E402

app = wx.App(False)


def relative_luminance(colour: wx.Colour) -> float:
    """Luminance as WCAG defines it, for the contrast formula below."""
    channels = []
    for value in (colour.Red(), colour.Green(), colour.Blue()):
        fraction = value / 255
        channels.append(
            fraction / 12.92 if fraction <= 0.03928
            else ((fraction + 0.055) / 1.055) ** 2.4
        )
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(first: wx.Colour, second: wx.Colour) -> float:
    """The WCAG contrast ratio between two colours, from 1 to 21."""
    light = relative_luminance(first)
    dark = relative_luminance(second)
    if light < dark:
        light, dark = dark, light
    return (light + 0.05) / (dark + 0.05)


# ---------- the modes ----------
check("three modes are offered",
      set(theme.MODES) == {"system", "light", "dark"}, theme.MODES)
check("dark is the one out of the box", theme.DARK == "dark")

check("a mode can be chosen", theme.set_mode("light") == "light")
check("and read back", theme.get_mode() == "light")
check("an unknown mode falls back to following Windows",
      theme.set_mode("nonsense") == "system")

theme.set_mode("light")
check("light mode is not dark", not theme.is_dark())
theme.set_mode("dark")
check("dark mode is dark", theme.is_dark())

# ---------- contrast, in both directions ----------
theme.set_mode("dark")
dark_window, dark_text = theme.window_colour(), theme.text_colour()
dark_panel = theme.panel_colour()

ratio = contrast(dark_window, dark_text)
check("dark: text on the list ground clears WCAG AAA (7:1)",
      ratio >= 7.0, f"{ratio:.1f}:1")

panel_ratio = contrast(dark_panel, dark_text)
check("dark: text on panels clears WCAG AA (4.5:1)",
      panel_ratio >= 4.5, f"{panel_ratio:.1f}:1")

stripe = theme.stripe_colour()
check("dark: the banded rows have a colour", stripe is not None)
stripe_ratio = contrast(stripe, dark_text)
check("dark: text on a banded row still clears AAA",
      stripe_ratio >= 7.0, f"{stripe_ratio:.1f}:1")
check("dark: the band is a whisper, not a stripe",
      contrast(stripe, dark_window) < 1.2,
      f"{contrast(stripe, dark_window):.3f}:1")

theme.set_mode("light")
light_window, light_text = theme.window_colour(), theme.text_colour()
light_ratio = contrast(light_window, light_text)
check("light: text on the list ground clears WCAG AAA",
      light_ratio >= 7.0, f"{light_ratio:.1f}:1")

check("the two modes really are different grounds",
      dark_window != light_window,
      f"{dark_window.GetAsString()} vs {light_window.GetAsString()}")
check("dark is the darker of the two",
      relative_luminance(dark_window) < relative_luminance(light_window))

# ---------- the icons follow the ground ----------
theme.set_mode("dark")
dark_icon = theme.icon_colour()
theme.set_mode("light")
light_icon = theme.icon_colour()
check("the icons are drawn in a different colour in each mode",
      dark_icon != light_icon, f"{dark_icon} vs {light_icon}")

theme.set_mode("dark")
check("dark: the icons are light",
      relative_luminance(wx.Colour(theme.icon_colour())) > 0.5,
      theme.icon_colour())
theme.set_mode("light")
check("light: the icons are dark",
      relative_luminance(wx.Colour(theme.icon_colour())) < 0.5,
      theme.icon_colour())

# and the drawings really do come out different
icons.forget_drawings()
theme.set_mode("dark")
dark_drawing = bytes(icons.get("new").ConvertToImage().GetData())
icons.forget_drawings()
theme.set_mode("light")
light_drawing = bytes(icons.get("new").ConvertToImage().GetData())
check("the same icon is rendered differently in each mode",
      dark_drawing != light_drawing)

# ---------- high contrast wins over everything ----------
saved = theme._high_contrast
theme._high_contrast = True
theme.set_mode("dark")
check("high contrast refuses to be painted over", not theme.is_dark())
check("high contrast drops the row banding", theme.stripe_colour() is None)
check("high contrast takes its panel colour from the system",
      theme.panel_colour() ==
      wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNFACE))
theme._high_contrast = saved

# ---------- painting a window ----------
theme.set_mode("dark")
frame = wx.Frame(None)
panel = wx.Panel(frame)
field = wx.TextCtrl(panel)
label = wx.StaticText(panel, label="A caption")
theme.apply_window(frame)
check("a text field takes the dark ground",
      field.GetBackgroundColour() == theme.window_colour(),
      field.GetBackgroundColour().GetAsString())
check("a caption takes the light text colour",
      label.GetForegroundColour() == theme.text_colour())

theme.set_mode("light")
plain = wx.Frame(None)
plain_panel = wx.Panel(plain)
before = plain_panel.GetBackgroundColour().GetAsString()
theme.apply_window(plain)
check("light mode leaves the system's own colours alone",
      plain_panel.GetBackgroundColour().GetAsString() == before)
plain.Destroy()
frame.Destroy()

# ---------- spacing is named, not scattered ----------
# GAP_WIDE separates a caption from its field across the row; MARGIN is
# the breathing space at the edge of a window. Different axes, so they
# are not one ladder — only the three gaps are.
check("the gaps rise in order",
      theme.GAP_TIGHT < theme.GAP < theme.GAP_WIDE,
      (theme.GAP_TIGHT, theme.GAP, theme.GAP_WIDE))
check("the window margin is at least a full gap",
      theme.MARGIN >= theme.GAP, (theme.MARGIN, theme.GAP))
check("rows are taller than the cramped default", theme.ROW_HEIGHT >= 24,
      theme.ROW_HEIGHT)

theme.set_mode("dark")
app.Destroy()

sys.exit(finish("Theme tests"))
