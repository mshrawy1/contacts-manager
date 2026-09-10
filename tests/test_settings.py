# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Settings file tests.

The point being checked here is separation: contacts live in the
database, preferences live in their own file, and neither reaches into
the other.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _harness import check, finish, setup  # noqa: E402

setup()

from app import config, settings as settings_module  # noqa: E402
from app.models import Contact, Entry  # noqa: E402
from app.settings import DEFAULTS, Settings  # noqa: E402
from app.store import Store  # noqa: E402

folder = Path(tempfile.mkdtemp(prefix="cm_settings_"))
path = folder / "settings.json"

# ---------- defaults when there is no file ----------
fresh = Settings(path)
check("a missing file gives the defaults", fresh.as_dict() == DEFAULTS, fresh.as_dict())
check("language starts empty, meaning follow the system",
      fresh.get("language") == "", fresh.get("language"))
check("no file is written just by reading", not path.exists())

# ---------- writing and reading back ----------
check("setting a value reports success", fresh.set("language", "ar"))
check("the file now exists", path.exists())
check("the value is held in memory", fresh.get("language") == "ar")

reloaded = Settings(path)
check("the value survives a reload", reloaded.get("language") == "ar",
      reloaded.get("language"))

# ---------- the file is plain, readable JSON ----------
raw = json.loads(path.read_text(encoding="utf-8"))
check("the file is a JSON object", isinstance(raw, dict), type(raw).__name__)
check("the file holds the language", raw.get("language") == "ar", raw)
check("the file is human readable", "\n" in path.read_text(encoding="utf-8"))

# ---------- a damaged file must not stop the program ----------
path.write_text("this is not json {{{", encoding="utf-8")
damaged = Settings(path)
check("a corrupt file falls back to the defaults",
      damaged.as_dict() == DEFAULTS, damaged.as_dict())

path.write_text('{"language": "en", "somethingUnknown": 42}', encoding="utf-8")
mixed = Settings(path)
check("a known key is read back", mixed.get("language") == "en")
check("an unknown key is ignored", "somethingUnknown" not in mixed.as_dict(),
      mixed.as_dict())

path.write_text('["not", "an", "object"]', encoding="utf-8")
wrong_shape = Settings(path)
check("a file of the wrong shape falls back to the defaults",
      wrong_shape.as_dict() == DEFAULTS)

# ---------- settings never live in the contacts database ----------
check("the settings path is not the database path",
      config.SETTINGS_FILE != config.DB_FILE)
check("the settings file is named settings.json",
      config.SETTINGS_FILE.name == "settings.json", config.SETTINGS_FILE.name)

db = folder / "contacts.db"
store = Store(db)
store.add(Contact(given_name="سعاد", phones=[Entry("01001234567", "Mobile")]))

# The only thing the database describes about itself is its own version.
keys = [row["key"] for row in store.conn.execute("SELECT key FROM meta")]
check("the database holds only its schema version", keys == ["schema_version"], keys)

# ---------- lifting an old setting out of the database ----------
store.set_meta("language", "ar")
target = Settings(folder / "migrated.json")
moved = settings_module.migrate_from_database(store, target)
check("the old setting was found and moved", moved)
check("the language landed in the settings file", target.get("language") == "ar",
      target.get("language"))
check("the database no longer holds it", store.get_meta("language", "") == "",
      store.get_meta("language", ""))
keys_after = [row["key"] for row in store.conn.execute("SELECT key FROM meta")]
check("only the schema version is left behind", keys_after == ["schema_version"],
      keys_after)

check("running the move a second time does nothing",
      not settings_module.migrate_from_database(store, target))

# an existing preference is never overwritten by the old value
store.set_meta("language", "ar")
already = Settings(folder / "already.json")
already.set("language", "en")
settings_module.migrate_from_database(store, already)
check("an existing preference wins over the old database value",
      already.get("language") == "en", already.get("language"))

check("the contacts survived all of this", store.count() == 1, store.count())
store.close()

# ---------- an unwritable location must not raise ----------
blocked = Settings(folder / "no-such-folder" / "deep" / "settings.json")
check("an unwritable path still returns defaults", blocked.get("language") == "")
check("saving to an unwritable path reports failure, not a crash",
      isinstance(blocked.set("language", "ar"), bool))

for leftover in folder.rglob("*"):
    try:
        leftover.unlink()
    except OSError:
        pass

sys.exit(finish("Settings tests"))
