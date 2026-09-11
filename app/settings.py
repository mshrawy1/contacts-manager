# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Program settings, kept in a small JSON file of their own.

The database holds contacts and nothing else. Anything about how the
program behaves — the chosen language, for instance — lives here, in a
plain text file the user can open, copy between machines, or simply
delete to get the defaults back.

Keeping the two apart matters in practice: the contacts file can be
handed to someone else, restored from a backup, or replaced wholesale
without dragging one person's preferences along with it.

One exception stays in the database on purpose: the schema version.
That describes the database itself and has to travel with it, or a
contacts file copied to another machine would be upgraded wrongly.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import config

# Every setting the program understands, with the value used when the
# file is missing or does not mention it.
DEFAULTS: dict[str, object] = {
    # Empty means "follow the operating system on first run".
    "language": "",
    # "dark", "light", or "system" to follow Windows. Dark by default,
    # because the program is used for long stretches of data entry.
    "appearance": "dark",
    # The country new phone numbers are read as belonging to. It is a
    # preference rather than a fixed setting: the contact form offers it
    # on every contact, and whatever is chosen there becomes the next
    # contact's starting point, so the common case costs no clicks and
    # the uncommon one is always one dropdown away.
    "country": "EG",
    # Whether exported numbers are written as +20 100 123 4567 rather
    # than 01001234567. On by default because the exported file exists
    # to be handed to Google Contacts or a phone, and the international
    # form is the one that still dials from abroad.
    "export_international": True,
}


class Settings:
    """Reads and writes the settings file, and never raises at the caller."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else config.SETTINGS_FILE
        self._values: dict[str, object] = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        """Read the file, ignoring anything unreadable or malformed.

        A corrupt settings file must never stop the program from
        starting; the defaults are good enough to run with.
        """
        try:
            raw = self.path.read_text(encoding="utf-8")
        except OSError:
            return

        try:
            stored = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return

        if isinstance(stored, dict):
            for key, value in stored.items():
                if key in DEFAULTS:
                    self._values[key] = value

    def save(self) -> bool:
        """Write the file. Returns False if it could not be written.

        Written to a temporary file first and then moved into place, so
        an interrupted save cannot leave a half-written file behind.
        """
        temporary = self.path.with_suffix(".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps(self._values, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.path)
            return True
        except OSError:
            try:
                temporary.unlink()
            except OSError:
                pass
            return False

    def get(self, key: str, default: object = None) -> object:
        if default is None:
            default = DEFAULTS.get(key, "")
        return self._values.get(key, default)

    def set(self, key: str, value: object) -> bool:
        """Change one setting and write the file straight away."""
        self._values[key] = value
        return self.save()

    def as_dict(self) -> dict[str, object]:
        return dict(self._values)


def migrate_from_database(store, settings: Settings) -> bool:
    """Move settings that older versions kept in the database.

    Version 1.0 moved the language out of the contacts file. This lifts
    it across once and clears it from the database, so an existing
    installation keeps the language it was set to.
    """
    legacy = store.get_meta("language", "")
    if not legacy:
        return False

    if not settings.get("language"):
        settings.set("language", legacy)
    store.clear_meta("language")
    return True
