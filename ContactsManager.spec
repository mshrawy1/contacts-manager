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

from PyInstaller.utils.hooks import collect_submodules

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
    name="ContactsManager",
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
