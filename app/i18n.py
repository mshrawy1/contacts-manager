# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Translation layer.

English is the source language: every user-facing string is written in
English directly in the code, and `t()` looks it up in the catalogue for
the active language. A string with no translation falls back to the
English original, so a half-finished catalogue degrades gracefully
instead of showing blank labels or key names.

Adding a language:

1. Copy ``locales/ar.py`` to ``locales/<code>.py`` and translate the
   values, leaving the English keys untouched.
2. Add the code and its native name to ``LANGUAGES`` below.
3. Add the code to ``RTL_LANGUAGES`` if it is written right to left.

``tests/test_i18n.py`` checks every string the code passes to ``t()``
against every catalogue, so a missed translation fails the test suite.
"""

from __future__ import annotations

import importlib
import locale

SOURCE_LANGUAGE = "en"

# Language code -> the language's own name, shown in the language menu.
LANGUAGES = {
    "en": "English",
    "ar": "العربية",
}

RTL_LANGUAGES = {"ar"}

_current = SOURCE_LANGUAGE
_catalog: dict[str, str] = {}


def available_languages() -> dict[str, str]:
    """Language codes mapped to the name each language calls itself."""
    return dict(LANGUAGES)


def get_language() -> str:
    return _current


def is_rtl() -> bool:
    """True when the active language reads right to left."""
    return _current in RTL_LANGUAGES


def language_name(code: str) -> str:
    return LANGUAGES.get(code, code)


def _load_catalog(code: str) -> dict[str, str]:
    """Import one language module and return its translations."""
    if code == SOURCE_LANGUAGE:
        return {}
    try:
        module = importlib.import_module(f".locales.{code}", package=__package__)
    except ImportError:
        return {}
    return dict(getattr(module, "TRANSLATIONS", {}))


def set_language(code: str) -> str:
    """Switch the active language and return the code actually applied."""
    global _current, _catalog
    code = (code or "").strip().lower()
    if code not in LANGUAGES:
        code = SOURCE_LANGUAGE
    _current = code
    _catalog = _load_catalog(code)
    return code


def t(text: str, **kwargs) -> str:
    """Translate a source string, then fill in any placeholders.

    Placeholders are named, so a translation is free to reorder them —
    which matters, because word order changes between languages.
    """
    out = _catalog.get(text, text)
    if kwargs:
        try:
            return out.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            # A broken translation must never crash the program; fall
            # back to the English original, which is known to be correct.
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                return text
    return out


def detect_language() -> str:
    """Guess the language from the operating system settings."""
    try:
        import ctypes

        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        if (lang_id & 0x3FF) == 0x01:  # primary language ID for Arabic
            return "ar"
    except (AttributeError, OSError):
        pass

    try:
        code = (locale.getlocale()[0] or "").lower()
    except (TypeError, ValueError):
        code = ""
    for known in LANGUAGES:
        if code.startswith(known):
            return known
    if code.startswith("arabic"):
        return "ar"
    return SOURCE_LANGUAGE


def list_separator() -> str:
    """The separator used between items in a joined list."""
    return "، " if is_rtl() else ", "


# Start from the system language until the saved preference is loaded.
set_language(detect_language())
