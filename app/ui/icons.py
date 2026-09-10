# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Icons for buttons and menu items, drawn from two sets on purpose.

A sighted user picks a command out of a row of buttons far faster from
its picture than by reading six labels, so every button carries one. The
two sources are chosen deliberately rather than mixed at random:

* **Material Symbols** — the icon set Google Contacts itself is drawn
  with — for everything to do with managing contacts: adding a person,
  merging duplicates, importing, labels, and so on. Someone who already
  uses Google Contacts recognises these immediately, which is the whole
  point of borrowing them.

* **Windows stock icons**, from `wx.ArtProvider`, for the plain verbs
  every dialog on the system shares: save, cancel, close, copy. Here
  matching the operating system matters more than matching Google — a
  Save button should look like every other Save button on the machine.

Material Symbols are published by Google under the Apache License 2.0
(see LICENSE-material-icons.txt); the artwork is embedded unmodified in
`material_icons.py`, so the program needs no image files and no network.

Two rules hold throughout:

* An icon always sits **beside** its text label, never instead of it.
  Dropping the words would hurt everyone: a screen reader would have
  nothing to announce, and a sighted user would be left guessing at a
  picture. Adding a bitmap does not change a button's accessible name.
* Every lookup can fail without consequence. If artwork is missing or
  cannot be drawn, the button simply appears without a picture.
"""

from __future__ import annotations

import wx

from . import material_icons, theme

# wx.svg draws the Material Symbol artwork. Bound under its own name so
# that referring to it never shadows the wx module itself.
try:
    import wx.svg as wx_svg
except ImportError:  # pragma: no cover - present in every supported build
    wx_svg = None

BUTTON_SIZE = (16, 16)
MENU_SIZE = (16, 16)

# The platform-standard verbs, where the Windows look is the right one.
# Preferred art identifier first, then fallbacks. These are plain strings
# in wxPython, so naming them directly cannot raise AttributeError on a
# build that lacks a particular constant.
_STOCK: dict[str, tuple[str, ...]] = {
    "save": ("wxART_FILE_SAVE", "wxART_TICK_MARK"),
    "cancel": ("wxART_CROSS_MARK", "wxART_CLOSE", "wxART_QUIT"),
    "close": ("wxART_CLOSE", "wxART_CROSS_MARK", "wxART_QUIT"),
    "copy": ("wxART_COPY",),
    "quit": ("wxART_QUIT", "wxART_CLOSE"),
}

# Windows art to fall back on if a Material drawing cannot be rendered.
_STOCK_FALLBACK: dict[str, tuple[str, ...]] = {
    "new": ("wxART_NEW",),
    "edit": ("wxART_EDIT", "wxART_NORMAL_FILE"),
    "delete": ("wxART_DELETE",),
    "select_all": ("wxART_TICK_MARK", "wxART_LIST_VIEW"),
    "duplicates": ("wxART_FIND_AND_REPLACE", "wxART_FIND"),
    "import": ("wxART_FILE_OPEN",),
    "export": ("wxART_FILE_SAVE_AS",),
    "search": ("wxART_FIND",),
    "list": ("wxART_LIST_VIEW", "wxART_REPORT_VIEW"),
    "refresh": ("wxART_REDO",),
    "speak": ("wxART_TIP", "wxART_INFORMATION"),
    "expand": ("wxART_GO_DOWN", "wxART_PLUS"),
    "collapse": ("wxART_GO_UP", "wxART_MINUS"),
    "add": ("wxART_PLUS", "wxART_NEW"),
    "restore": ("wxART_UNDO", "wxART_GO_BACK"),
    "trash": ("wxART_DELETE",),
    "empty": ("wxART_DELETE",),
    "merge": ("wxART_TICK_MARK",),
    "merge_all": ("wxART_LIST_VIEW",),
    "backup": ("wxART_HARDDISK", "wxART_FLOPPY"),
    "language": ("wxART_HELP_SETTINGS", "wxART_TIP"),
    "help": ("wxART_HELP", "wxART_QUESTION"),
    "about": ("wxART_INFORMATION", "wxART_HELP"),
    "label": ("wxART_ADD_BOOKMARK",),
    "contacts": ("wxART_LIST_VIEW",),
}

# Rendered bitmaps, keyed by name, size and colour, so the SVG work is
# done once per icon rather than on every repaint.
_cache: dict[tuple, wx.Bitmap] = {}


def _icon_colour() -> str:
    """The colour to draw the icons in, as #RRGGBB.

    Handed over by the theme, which knows whether the window is light or
    dark. Because the colour is part of the cache key below, switching
    appearance redraws every icon in the new colour by itself — there is
    no second set of artwork to keep in step.
    """
    return theme.icon_colour()


def _render_material(name: str, size: tuple[int, int], colour: str) -> wx.Bitmap:
    """Rasterise one embedded Material drawing at the size wanted."""
    markup = material_icons.SVG.get(name)
    if not markup:
        return wx.NullBitmap

    # The drawings carry no fill of their own, so state one explicitly.
    markup = markup.replace("<path ", f'<path fill="{colour}" ')

    if wx_svg is None:
        return wx.NullBitmap

    try:
        image = wx_svg.SVGimage.CreateFromBytes(markup.encode("utf-8"))
        bitmap = image.ConvertToScaledBitmap(wx.Size(*size))
    except (AttributeError, RuntimeError, ValueError, wx.wxAssertionError):
        return wx.NullBitmap

    return bitmap if bitmap.IsOk() else wx.NullBitmap


def _render_stock(names: tuple[str, ...], size: tuple[int, int],
                  client: str) -> wx.Bitmap:
    """Take the first usable image from a list of Windows art identifiers."""
    for art_id in names:
        try:
            bitmap = wx.ArtProvider.GetBitmap(art_id, client, size)
        except (wx.wxAssertionError, TypeError, ValueError):
            continue
        if bitmap.IsOk():
            return bitmap
    return wx.NullBitmap


def get(name: str, size: tuple[int, int] = BUTTON_SIZE,
        client: str = wx.ART_BUTTON) -> wx.Bitmap:
    """Return the best available image for a name, or a null bitmap.

    Platform verbs are looked for in the Windows set first and the
    Material set second; everything else the other way round.
    """
    colour = _icon_colour()
    key = (name, size, colour, client)
    if key in _cache:
        return _cache[key]

    if name in _STOCK:
        bitmap = _render_stock(_STOCK[name], size, client)
        if not bitmap.IsOk():
            bitmap = _render_material(name, size, colour)
    else:
        bitmap = _render_material(name, size, colour)
        if not bitmap.IsOk():
            bitmap = _render_stock(_STOCK_FALLBACK.get(name, ()), size, client)

    _cache[key] = bitmap
    return bitmap


def source_of(name: str) -> str:
    """Which set a name is served from: "material", "windows", or "".

    Used by the tests, and by anyone wondering why a particular button
    looks the way it does.
    """
    if name in _STOCK:
        return "windows"
    if name in material_icons.SVG:
        return "material"
    if name in _STOCK_FALLBACK:
        return "windows"
    return ""


def known_names() -> list[str]:
    """Every icon name the program can draw."""
    return sorted(set(material_icons.SVG) | set(_STOCK) | set(_STOCK_FALLBACK))


def forget_drawings() -> None:
    """Throw away the rendered icons, after the colours change.

    The colour is part of the cache key, so stale entries would never be
    returned anyway; this simply stops the old ones taking up room once
    they can no longer be wanted.
    """
    _cache.clear()


def apply_to_button(button: wx.Button, name: str) -> bool:
    """Put an icon on a button, leaving its label untouched.

    Returns whether an image was actually found, which is what the tests
    check so a mistyped name cannot pass unnoticed.
    """
    bitmap = get(name)
    if not bitmap.IsOk():
        return False

    button.SetBitmap(bitmap)
    # A little air between the picture and the words.
    try:
        button.SetBitmapMargins((4, 0))
    except (AttributeError, TypeError):
        pass
    return True


def make_menu_item(menu: wx.Menu, identifier: int, text: str,
                   help_text: str = "", name: str = "") -> wx.MenuItem:
    """Build a menu entry carrying an icon, and add it to the menu.

    On Windows the image has to be attached before the item joins the
    menu, so the item is created here rather than through Menu.Append.
    """
    item = wx.MenuItem(menu, identifier, text, help_text)
    if name:
        bitmap = get(name, MENU_SIZE, wx.ART_MENU)
        if bitmap.IsOk():
            try:
                item.SetBitmap(bitmap)
            except (wx.wxAssertionError, TypeError):
                pass
    menu.Append(item)
    return item
