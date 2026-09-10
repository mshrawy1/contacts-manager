# Third-party licences

Contacts Manager is released under the **GNU General Public License,
version 3 or later** — the full text is in [LICENSE](LICENSE).

This file lists everything the program uses that somebody else wrote,
what each is licensed under, and why each is compatible with GPL-3.0.
It is here because the GPL requires that people receiving the program
can find out what is in it, and because anyone auditing the project
should not have to work it out for themselves.

---

## What ships inside the built .exe

### wxPython — the interface

* **Version:** 4.3.1
* **Licence:** wxWindows Library Licence
* **Home:** <https://wxpython.org>

The wxWindows Library Licence is the LGPL 2.1 with an added exception
that permits distributing binaries built against it under terms of your
own choosing. It places no condition on this program's licence, and is
compatible with the GPL.

wxPython is what makes the program readable by screen readers: it draws
real Windows controls rather than painting its own, which is why NVDA
and JAWS understand the tables, fields and menus without any special
handling.

### Material Symbols — the icons

* **Licence:** Apache License 2.0 — full text in
  [LICENSE-material-icons.txt](LICENSE-material-icons.txt)
* **Home:** <https://github.com/google/material-design-icons>

The drawings are embedded unmodified in `app/ui/material_icons.py`, as
SVG markup rather than image files, so the program carries its icons
inside itself.

**This is why the project is GPL version 3 and not version 2.** The
Apache 2.0 licence is compatible with GPLv3 but *not* with GPLv2: its
patent-termination clause counts as an extra restriction under the older
licence. Choosing GPLv3 is what makes it lawful to ship these icons.
(NVDA sidesteps the same problem by being "GPLv2 **or later**", which
allows it to be used under v3 where needed.)

---

## What is used to build, but ships no code of its own

### PyInstaller — packaging

* **Version:** 6.22.2
* **Licence:** GPL 2.0 or later, **with a special exception**
* **Home:** <https://pyinstaller.org>

The exception states plainly that PyInstaller may be used to build and
distribute programs under any licence, free or not. Its bootloader is
the only part of PyInstaller present in the finished `.exe`, and the
exception covers it. Nothing about packaging changes this program's
licence.

### Python — the language

* **Licence:** Python Software Foundation Licence
* **Home:** <https://www.python.org>

A permissive licence, compatible with the GPL. The standard library
modules the program relies on — `sqlite3`, `csv`, `json`, `quopri`,
`unicodedata` — are covered by it.

---

## What is *not* used

Worth stating, because people ask:

* **No Google API, SDK or account access.** The program exchanges
  contacts with Google through CSV and vCard files that the user
  exports and imports themselves. Nothing authenticates, and no
  password ever reaches the program.
* **No network access of any kind at run time.** The program never
  opens a connection. The Material Symbols artwork was fetched once
  while the program was being written and embedded in the source.
* **No telemetry, analytics or crash reporting.** Errors are written to
  a log file on the user's own machine and nowhere else.

---

## Checking this for yourself

The licences above are not taken on trust; they can be read off the
installed packages:

```bash
python -c "import importlib.metadata as m; print(m.metadata('wxPython')['License'])"
```

```bash
python -c "import importlib.metadata as m; print(m.metadata('pyinstaller')['License'])"
```
