# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build description for a single portable .exe.

Build it with:

    python -m PyInstaller ContactsManager.spec --noconfirm

or double-click build_exe.bat.

Two things here are easy to get wrong:

* The translation catalogues are loaded with importlib at run time, so
  nothing in the source refers to them by name and PyInstaller cannot
  see them. collect_submodules pulls them in explicitly; without this
  the built program would silently fall back to English only.
* console=False keeps a terminal window from flashing up. Errors still
  reach the user, because the program shows them in a message box and
  writes them to its log file.
"""

import re
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

# The built file is named with its version -- ContactsManagerV1.1.exe --
# because this program is portable. Nobody installs it, so two copies end
# up in a downloads folder with nothing to tell them apart, and the only
# way to find out which is which is to run them both.
#
# The number is read out of app/config.py rather than written here, so
# there is one place to change it and no way for the file name to drift
# away from the version the program reports. Read as text rather than
# imported, because the spec runs inside PyInstaller and the project is
# not necessarily importable from there.
#
# Renaming the file is safe for anyone upgrading: the data folder beside
# it is named from APP_ID, not from the executable, so contacts stay put.
_config = (Path(SPECPATH) / "app" / "config.py").read_text(encoding="utf-8")
APP_VERSION = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', _config).group(1)

# Every language module under app/locales, found by name rather than by
# following imports. wx.svg draws the Material Symbol icons and is only
# imported when one is first needed, so it is named here too.
hidden_imports = collect_submodules("app.locales") + ["wx.svg"]

# Large packages that are installed in the environment but never used by
# this program. Naming them keeps them out of the .exe.
excluded = [
    "tkinter",
    "unittest",
    "pydoc",
    "doctest",
    "test",
    "googleapiclient",
    "google",
    "google_auth_oauthlib",
    "google_auth_httplib2",
    "cryptography",
    "numpy",
    "PIL",
    "matplotlib",
    "pytest",
    "setuptools",
    "pip",
]

analysis = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name=f"ContactsManagerV{APP_VERSION}",
    # Gives the file a name and a description in Windows Properties and on
    # SmartScreen's "More info" screen.
    version="version_info.txt",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
