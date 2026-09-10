# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Normalising text and numbers so search and duplicate detection work.

The problem this solves: the same name can be spelled several ways
(محمد / محمّد, احمد / أحمد, يحيى / يحيي), and the same phone number can
be written several ways (01001234567 / +201001234567 / ٠١٠٠١٢٣٤٥٦٧).
Without normalising, searching misses matches and duplicates go
undetected.

The diacritic range below covers U+064B..U+065F, U+0670 and
U+06D6..U+06ED. Those characters are combining marks with no shape of
their own, so the range is hard to read in an editor; the codepoints are
spelled out here instead.
"""

from __future__ import annotations

import re
import unicodedata

# Arabic diacritics and marks, stripped before any comparison.
_DIACRITICS = re.compile(r"[ً-ٰٟۖ-ۭ]")
_TATWEEL = "ـ"  # the kashida stretching character

# Arabic-Indic and Persian digits mapped to ASCII digits.
_DIGITS = {}
for _i in range(10):
    _DIGITS[chr(0x0660 + _i)] = str(_i)  # Arabic-Indic
    _DIGITS[chr(0x06F0 + _i)] = str(_i)  # Persian
_DIGIT_TABLE = str.maketrans(_DIGITS)

# Letters that are written more than one way, folded to a single form.
_LETTER_TABLE = str.maketrans(
    {
        "أ": "ا",  # alef with hamza above -> alef
        "إ": "ا",  # alef with hamza below -> alef
        "آ": "ا",  # alef with madda       -> alef
        "ٱ": "ا",  # alef wasla            -> alef
        "ى": "ي",  # alef maksura          -> yeh
        "ئ": "ي",  # yeh with hamza        -> yeh
        "ؤ": "و",  # waw with hamza        -> waw
        "ة": "ه",  # teh marbuta           -> heh
    }
)

# One table covering letters and digits together. Merging the two halves
# the number of translate() calls, which is a measurable saving when
# importing thousands of names at once.
_NORM_TABLE = {**_LETTER_TABLE, **_DIGIT_TABLE}


def decode_bytes(data: bytes) -> str:
    """Detect a file's encoding and decode it.

    Files arrive in different encodings depending on where they came
    from: Google exports UTF-8, older Arabic Excel exports windows-1256,
    and some programs add a byte order mark.
    """
    if data.startswith(b"\xff\xfe\x00\x00") or data.startswith(b"\x00\x00\xfe\xff"):
        return data.decode("utf-32")
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8")
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16")
    for encoding in ("utf-8", "cp1256", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def normalize_digits(text: str) -> str:
    """Convert any Arabic or Persian digits to ASCII digits."""
    if not text:
        return ""
    return text.translate(_DIGIT_TABLE)


def normalize_text(text: str) -> str:
    """Return a folded form of the text, used only for comparison."""
    if not text:
        return ""
    out = unicodedata.normalize("NFKC", text)
    out = _DIACRITICS.sub("", out)
    out = out.replace(_TATWEEL, "")
    out = out.translate(_NORM_TABLE)
    out = re.sub(r"\s+", " ", out).strip()
    return out.casefold()


def phone_key(phone: str) -> str:
    """A comparison key for phone numbers: the last nine digits.

    Stripping punctuation and the country code makes 01001234567,
    +201001234567 and 00201001234567 all produce the same key, so the
    program can tell they belong to one person.
    """
    if not phone:
        return ""
    digits = re.sub(r"\D", "", normalize_digits(unicodedata.normalize("NFKC", phone)))
    if not digits:
        return ""
    return digits[-9:] if len(digits) >= 9 else digits


def clean_phone(phone: str) -> str:
    """Tidy a number for storage and display, keeping ASCII digits."""
    if not phone:
        return ""
    out = normalize_digits(unicodedata.normalize("NFKC", phone)).strip()
    # Keep only a leading plus, digits, and light grouping punctuation.
    out = re.sub(r"[^\d+()\-\s]", "", out)
    return re.sub(r"\s+", " ", out).strip()


def clean_email(email: str) -> str:
    """Tidy an address: trimmed and lower-cased."""
    if not email:
        return ""
    return normalize_digits(email).strip().lower()


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")


def is_valid_email(email: str) -> bool:
    """A shape check only; it does not verify the address exists."""
    return bool(_EMAIL_RE.match((email or "").strip()))


def is_valid_phone(phone: str) -> bool:
    """A number is accepted when it holds between 5 and 15 digits."""
    digits = re.sub(r"\D", "", normalize_digits(phone or ""))
    return 5 <= len(digits) <= 15
