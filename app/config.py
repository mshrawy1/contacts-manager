# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""File locations and application-wide constants."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Contacts Manager"
APP_ID = "ContactsManager"
APP_VERSION = "1.1"

# Licensing, stated once so the About screen, the documentation and any
# future packaging all read the same thing from here.
#
# GPL-3.0 rather than 2.0 for a concrete reason: the Material Symbols
# icons embedded in the interface are Apache 2.0, which is compatible
# with version 3 of the GPL but not with version 2. See
# THIRD-PARTY-LICENSES.md.
LICENSE_ID = "GPL-3.0-or-later"
LICENSE_NAME = "GNU General Public License v3.0 or later"

# The About screen omits the copyright line entirely when no holder is
# set, so a half-filled notice is never put in front of anyone.
COPYRIGHT_YEAR = "2026"
COPYRIGHT_HOLDER = "Mahmoud Shrawy"


def copyright_line() -> str:
    """The copyright notice, or an empty string if no holder is set."""
    if not COPYRIGHT_HOLDER:
        return ""
    return f"Copyright (C) {COPYRIGHT_YEAR} {COPYRIGHT_HOLDER}"


def app_dir() -> Path:
    """The folder holding the program's own files."""
    if getattr(sys, "frozen", False):  # running as a bundled .exe
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _is_usable(folder: Path) -> bool:
    """Whether a folder can be created and written to."""
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / ".write-test"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def data_dir() -> Path:
    """Where the database, backups and log live.

    A built .exe keeps its data in a folder beside itself, so the whole
    program travels on a USB stick with its contacts intact. If that
    place cannot be written to — running from a read-only drive, or from
    Program Files — it falls back to the per-user application data
    folder. Running from source always uses the per-user folder, so
    development never litters the project directory.
    """
    if getattr(sys, "frozen", False):
        beside = app_dir() / f"{APP_ID}Data"
        if _is_usable(beside):
            return beside

    base = os.environ.get("APPDATA") or str(Path.home())
    path = Path(base) / APP_ID
    path.mkdir(parents=True, exist_ok=True)
    return path


def backup_dir() -> Path:
    """The folder holding automatic backups."""
    path = data_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


DB_FILE = data_dir() / "contacts.db"
LOG_FILE = data_dir() / "app.log"

# Program settings live in their own file. The database is for
# contacts and nothing else.
SETTINGS_FILE = data_dir() / "settings.json"

# How many automatic backups to keep before the oldest is deleted.
MAX_BACKUPS = 20

# Canonical value-type names. These are stored in the database and
# written to exported files verbatim, because Google and vCard expect
# these exact English words. The interface shows them translated.
PHONE_LABELS = ["Mobile", "Home", "Work", "Main", "Work Fax", "Home Fax", "Other"]
EMAIL_LABELS = ["Home", "Work", "Other"]
