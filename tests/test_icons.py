# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Icon tests.

The program mixes two icon sets on purpose: Material Symbols — the set
Google Contacts is drawn with — for anything to do with managing
contacts, and Windows stock art for the plain verbs every dialog shares.
These checks hold that split in place and make sure every name the code
asks for actually produces a picture.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _harness import ROOT, check, finish, setup  # noqa: E402

setup()

import wx  # noqa: E402

from app.ui import icons, material_icons  # noqa: E402

app = wx.App(False)

# ---------- the embedded artwork ----------
check("Material artwork is embedded", len(material_icons.SVG) >= 20,
      len(material_icons.SVG))
check("every drawing is a complete SVG document",
      all(v.startswith("<svg") and v.rstrip().endswith("</svg>")
          for v in material_icons.SVG.values()))
check("the drawings carry no colour of their own, so they can be recoloured",
      not any('fill="#' in v for v in material_icons.SVG.values()))

licence = ROOT / "LICENSE-material-icons.txt"
check("the Apache licence ships with the artwork", licence.exists(), licence.name)
check("it really is the Apache licence",
      "Apache License" in licence.read_text(encoding="utf-8")[:200])

# ---------- the project's own licence ----------
# The Apache 2.0 artwork above is the reason the project is GPL version
# 3 rather than 2: Apache 2.0 is compatible with v3 and not with v2. If
# anyone ever downgrades the licence, these checks say why they cannot.
from app import config  # noqa: E402

project_licence = ROOT / "LICENSE"
check("the project ships its own licence", project_licence.exists())

licence_text = project_licence.read_text(encoding="utf-8")
check("it is the GNU General Public License",
      "GNU GENERAL PUBLIC LICENSE" in licence_text[:200])
check("it is version 3", "Version 3, 29 June 2007" in licence_text[:400],
      licence_text[:120].strip().replace(chr(10), " "))
check("the whole text is there, not a summary",
      len(licence_text) > 30000, len(licence_text))

check("the program states the same licence",
      config.LICENSE_ID == "GPL-3.0-or-later", config.LICENSE_ID)
check("and names it in full for the About screen",
      "General Public License" in config.LICENSE_NAME, config.LICENSE_NAME)
check("no half-filled copyright line is ever shown",
      config.copyright_line() == "" or config.COPYRIGHT_HOLDER,
      repr(config.copyright_line()))

third_party = ROOT / "THIRD-PARTY-LICENSES.md"
check("the third-party licences are written down", third_party.exists())
third_text = third_party.read_text(encoding="utf-8")
for component in ("wxPython", "Material Symbols", "PyInstaller"):
    check(f"'{component}' is accounted for", component in third_text)

# ---------- every name draws something ----------
names = icons.known_names()
check("there are icons to test", len(names) >= 25, len(names))

undrawable = [n for n in names if not icons.get(n).IsOk()]
check("every icon name produces a picture", not undrawable, undrawable)

wrong_size = [n for n in names if icons.get(n).GetSize() != wx.Size(16, 16)]
check("every icon comes back at the size asked for", not wrong_size, wrong_size)

# ---------- the split between the two sets ----------
material = [n for n in names if icons.source_of(n) == "material"]
windows = [n for n in names if icons.source_of(n) == "windows"]
check("most icons come from Material Symbols", len(material) >= 20, len(material))
check("the platform verbs come from Windows",
      set(windows) == {"save", "cancel", "close", "copy", "quit"}, sorted(windows))
check("every name belongs to one set or the other",
      len(material) + len(windows) == len(names))

for name in ("new", "edit", "delete", "duplicates", "import", "export",
             "merge", "restore", "label"):
    check(f"'{name}' uses the Google icon set",
          icons.source_of(name) == "material", icons.source_of(name))

for name in ("save", "cancel", "close", "copy"):
    check(f"'{name}' uses the Windows icon set",
          icons.source_of(name) == "windows", icons.source_of(name))

# ---------- distinct drawings, not the same picture repeated ----------
def fingerprint(name: str) -> bytes:
    """What the drawing actually looks like.

    The shapes are painted in one flat colour on a transparent ground, so
    the colour channels are identical for every icon and it is the alpha
    channel that holds the picture. Comparing colour alone would report
    every icon as the same image.
    """
    image = icons.get(name).ConvertToImage()
    alpha = image.GetAlpha() if image.HasAlpha() else b""
    return bytes(image.GetData()) + bytes(alpha)


sample = ["new", "edit", "delete", "import", "export", "search", "expand",
          "collapse", "merge", "restore"]
prints = {name: fingerprint(name) for name in sample}
check("the drawings differ from one another",
      len(set(prints.values())) == len(sample),
      f"{len(set(prints.values()))} distinct out of {len(sample)}")
check("expand and collapse are not the same arrow",
      fingerprint("expand") != fingerprint("collapse"))

# ---------- an unknown name fails quietly ----------
check("an unknown name returns nothing rather than raising",
      not icons.get("no-such-icon").IsOk())
check("an unknown name reports no source", icons.source_of("no-such-icon") == "")

# ---------- putting one on a button leaves the words alone ----------
frame = wx.Frame(None)
button = wx.Button(frame, wx.ID_ANY, "Import")
check("applying an icon reports success", icons.apply_to_button(button, "import"))
check("the button now carries a picture", button.GetBitmap().IsOk())
check("the label is untouched", button.GetLabel() == "Import", button.GetLabel())
check("a bad name reports failure", not icons.apply_to_button(button, "nonsense"))

menu = wx.Menu()
item = icons.make_menu_item(menu, wx.ID_ANY, "Import", "help text", "import")
check("a menu entry keeps its text", item.GetItemLabelText() == "Import",
      item.GetItemLabelText())
check("the menu entry was added", menu.GetMenuItemCount() == 1)
frame.Destroy()

# ---------- caching ----------
first = icons.get("new")
second = icons.get("new")
check("a repeated lookup returns the cached bitmap", first is second)

app.Destroy()

sys.exit(finish("Icon tests"))
