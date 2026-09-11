# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Translation tests.

These read the source code itself and check that every string handed to
`t()` has an entry in every catalogue, with matching placeholders. A
forgotten translation therefore fails the test suite instead of showing
up as English text in the middle of an Arabic window.
"""

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _harness import ROOT, check, finish, setup  # noqa: E402

setup()

from app import config, i18n, xlsx_import  # noqa: E402
from app.locales import ar  # noqa: E402

# Every line an import report can produce. Built by filling in a report
# rather than listed by hand, so a line added later is checked for a
# translation without anybody having to remember to add it here.
_FULL_REPORT = xlsx_import.Report(
    rows_read=1, contacts=1, phones_repaired=1, ids_blocked=1,
    rows_blank=1, rows_empty_contact=1,
)

# Strings translated through a variable rather than a literal, so the
# scan below cannot see them: the value types stored in the database, the
# program's own name, the fields a spreadsheet column can be mapped onto,
# and the lines of an import report.
INDIRECT = (
    set(config.PHONE_LABELS)
    | set(config.EMAIL_LABELS)
    | {config.APP_NAME}
    | {label for _, label in xlsx_import.FIELD_CHOICES if label}
    | {text for text, _ in _FULL_REPORT.lines()}
)

PLACEHOLDER_CHARS = "{}"


def source_files() -> list[Path]:
    return sorted(ROOT.glob("app/**/*.py")) + [ROOT / "main.py"]


def collect_keys() -> set[str]:
    """Every literal string passed as the first argument to t()."""
    keys: set[str] = set()
    for path in source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name != "t":
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                keys.add(first.value)
    return keys


def placeholders(text: str) -> set[str]:
    """The {named} slots inside a string."""
    out: set[str] = set()
    depth_start = None
    for index, char in enumerate(text):
        if char == "{":
            depth_start = index + 1
        elif char == "}" and depth_start is not None:
            out.add(text[depth_start:index].split("!")[0].split(":")[0])
            depth_start = None
    return out


keys = collect_keys() | INDIRECT
check("found translatable strings in the source", len(keys) > 100, len(keys))

# ---------- every key is translated ----------
missing = sorted(k for k in keys if k not in ar.TRANSLATIONS)
check("every string has an Arabic translation", not missing,
      f"{len(missing)} missing: {missing[:5]}")

# ---------- no leftover entries ----------
orphans = sorted(k for k in ar.TRANSLATIONS if k not in keys)
check("no leftover entries in the catalogue", not orphans,
      f"{len(orphans)} unused: {orphans[:5]}")

# ---------- placeholders survive translation ----------
mismatched = []
for key, value in ar.TRANSLATIONS.items():
    if placeholders(key) != placeholders(value):
        mismatched.append(key)
check("placeholders match between source and translation", not mismatched,
      f"{len(mismatched)}: {mismatched[:3]}")

# ---------- nothing left untranslated by accident ----------
same = sorted(
    k for k, v in ar.TRANSLATIONS.items()
    if k == v and not k.replace(" ", "").isascii()
)
check("no entry translates to itself unexpectedly", not same, same[:3])

# ---------- the translation machinery ----------
i18n.set_language("en")
check("English returns the source unchanged", i18n.t("New contact") == "New contact")
check("English is not right to left", not i18n.is_rtl())
check("English list separator", i18n.list_separator() == ", ")

i18n.set_language("ar")
check("Arabic is translated", i18n.t("New contact") == "جهة اتصال جديدة",
      i18n.t("New contact"))
check("Arabic is right to left", i18n.is_rtl())
check("Arabic list separator", i18n.list_separator() == "، ")
check("placeholders are filled in",
      i18n.t("{count} contacts.", count=7) == "7 جهة اتصال.",
      i18n.t("{count} contacts.", count=7))

check("an unknown string falls back to itself",
      i18n.t("a string nobody has translated") == "a string nobody has translated")
check("an unknown language falls back to English", i18n.set_language("zz") == "en")

i18n.set_language("ar")
check("a missing placeholder does not crash",
      isinstance(i18n.t("{count} contacts.", wrong=1), str))

# ---------- every declared language has a catalogue ----------
for code in i18n.available_languages():
    applied = i18n.set_language(code)
    check(f"language '{code}' loads", applied == code, applied)

check("English is the source language", i18n.SOURCE_LANGUAGE == "en")
check("Arabic is marked right to left", "ar" in i18n.RTL_LANGUAGES)

i18n.set_language("en")

sys.exit(finish("Translation tests"))
