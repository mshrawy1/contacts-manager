# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Countries and the repair of phone numbers.

This exists because of one specific failure that ruins imported data
without announcing itself. A spreadsheet cell holding 01001234567 in an
ordinary number format is stored by Excel as the number 1001234567: the
leading zero is gone from the file, not merely from the display. Import
such a sheet naively and every number in it is wrong, and nobody finds
out until somebody tries to place a call.

The digits alone cannot be repaired, because 1001234567 is genuinely
ambiguous. Ten digits beginning with 1 could be an Egyptian mobile that
has lost its zero, or a complete number somewhere else. Knowing the
country settles it, which is why the country is asked for rather than
guessed: in Egypt a national number is ten or eleven digits with its
trunk zero, so nine or ten digits without one can only be a number that
has lost it.

The same knowledge gives the international form, +20 100 123 4567, which
is what Google Contacts and a phone both prefer, since it keeps working
when the phone is abroad.

About the tables below: the dial codes are fixed facts. The lengths are
filled in only where the national numbering plan is settled and well
known. Where a country's plan is varied enough that a length rule would
be a guess, the lengths are left empty, and an empty tuple simply means
no zero is ever restored for that country -- the number is cleaned and
left as the user wrote it. Getting this wrong silently is worse than not
acting, so the uncertain cases do nothing.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from . import textutil


class Country(NamedTuple):
    """One entry in the country list.

    `trunk` is the digit dialled before a national number inside the
    country, which is "0" nearly everywhere and empty in the Gulf states
    that dial the subscriber number directly. `lengths` counts the
    national number *including* that trunk digit.
    """

    code: str
    dial: str
    name: str
    name_ar: str
    trunk: str
    lengths: tuple[int, ...]


# The Arab states first, because they are who this program is mostly
# for, then the rest in alphabetical order. The list is deliberately not
# every country on earth: a combo box of two hundred and fifty entries is
# hard to move through with a keyboard and harder with a screen reader.
COUNTRIES: tuple[Country, ...] = (
    Country("EG", "20", "Egypt", "مصر", "0", (10, 11)),
    Country("SA", "966", "Saudi Arabia", "السعودية", "0", (10,)),
    Country("AE", "971", "United Arab Emirates", "الإمارات", "0", (9, 10)),
    Country("KW", "965", "Kuwait", "الكويت", "", (8,)),
    Country("QA", "974", "Qatar", "قطر", "", (8,)),
    Country("BH", "973", "Bahrain", "البحرين", "", (8,)),
    Country("OM", "968", "Oman", "عُمان", "", (8,)),
    Country("JO", "962", "Jordan", "الأردن", "0", (9, 10)),
    Country("LB", "961", "Lebanon", "لبنان", "0", (7, 8)),
    Country("SY", "963", "Syria", "سوريا", "0", (9, 10)),
    Country("IQ", "964", "Iraq", "العراق", "0", (10, 11)),
    Country("PS", "970", "Palestine", "فلسطين", "0", (9, 10)),
    Country("YE", "967", "Yemen", "اليمن", "0", (8, 9)),
    Country("LY", "218", "Libya", "ليبيا", "0", (9, 10)),
    Country("SD", "249", "Sudan", "السودان", "0", (10,)),
    Country("TN", "216", "Tunisia", "تونس", "", (8,)),
    Country("DZ", "213", "Algeria", "الجزائر", "0", (9, 10)),
    Country("MA", "212", "Morocco", "المغرب", "0", (10,)),
    Country("MR", "222", "Mauritania", "موريتانيا", "", (8,)),
    Country("SO", "252", "Somalia", "الصومال", "0", ()),
    Country("DJ", "253", "Djibouti", "جيبوتي", "", (8,)),
    Country("KM", "269", "Comoros", "جزر القمر", "", (7,)),
    Country("AU", "61", "Australia", "أستراليا", "0", (10,)),
    Country("BE", "32", "Belgium", "بلجيكا", "0", ()),
    Country("BR", "55", "Brazil", "البرازيل", "0", ()),
    Country("CA", "1", "Canada", "كندا", "", (10,)),
    Country("CN", "86", "China", "الصين", "0", ()),
    Country("ET", "251", "Ethiopia", "إثيوبيا", "0", (10,)),
    Country("FR", "33", "France", "فرنسا", "0", (10,)),
    Country("DE", "49", "Germany", "ألمانيا", "0", ()),
    Country("GR", "30", "Greece", "اليونان", "", (10,)),
    Country("IN", "91", "India", "الهند", "0", (10, 11)),
    Country("ID", "62", "Indonesia", "إندونيسيا", "0", ()),
    Country("IR", "98", "Iran", "إيران", "0", (11,)),
    Country("IT", "39", "Italy", "إيطاليا", "", ()),
    Country("JP", "81", "Japan", "اليابان", "0", (11,)),
    Country("KE", "254", "Kenya", "كينيا", "0", (10,)),
    Country("MY", "60", "Malaysia", "ماليزيا", "0", ()),
    Country("MX", "52", "Mexico", "المكسيك", "", (10,)),
    Country("NL", "31", "Netherlands", "هولندا", "0", (10,)),
    Country("NG", "234", "Nigeria", "نيجيريا", "0", (11,)),
    Country("PK", "92", "Pakistan", "باكستان", "0", (10, 11)),
    Country("PH", "63", "Philippines", "الفلبين", "0", (11,)),
    Country("RU", "7", "Russia", "روسيا", "8", (11,)),
    Country("ZA", "27", "South Africa", "جنوب أفريقيا", "0", (10,)),
    Country("KR", "82", "South Korea", "كوريا الجنوبية", "0", ()),
    Country("ES", "34", "Spain", "إسبانيا", "", (9,)),
    Country("SE", "46", "Sweden", "السويد", "0", ()),
    Country("CH", "41", "Switzerland", "سويسرا", "0", (10,)),
    Country("TR", "90", "Turkey", "تركيا", "0", (11,)),
    Country("GB", "44", "United Kingdom", "المملكة المتحدة", "0", (10, 11)),
    Country("US", "1", "United States", "الولايات المتحدة", "", (10,)),
)

BY_CODE = {country.code: country for country in COUNTRIES}

# The country assumed when none has been chosen. Egypt, because that is
# where the program was written and who first asked for it; the user
# changes it in the contact form whenever a number belongs somewhere
# else, and the choice is remembered as the new default.
DEFAULT_CODE = "EG"

# What a repair did, so the import summary can say so plainly rather
# than quietly handing back different numbers from the ones in the file.
UNCHANGED = ""
RESTORED_TRUNK = "restored a leading zero lost by the spreadsheet"
ADDED_PLUS = "wrote the country code in international form"


def get(code: str | None) -> Country | None:
    """Look up a country by its two-letter code."""
    if not code:
        return None
    return BY_CODE.get(code.strip().upper())


def default() -> Country:
    """The fallback country, guaranteed to exist."""
    return BY_CODE[DEFAULT_CODE]


def display_name(country: Country, arabic: bool) -> str:
    """How the country is named in the list, dial code included.

    The dial code is part of the label rather than a second column
    because a screen reader then reads country and code together in one
    breath, and because two people in different countries can share a
    name in translation but never a code.
    """
    name = country.name_ar if arabic else country.name
    return f"{name} (+{country.dial})"


def _digits(value: str) -> str:
    """Every digit in the text, with Arabic-Indic digits folded first."""
    return re.sub(r"\D", "", textutil.normalize_digits(value or ""))


def split_international(value: str) -> tuple[Country | None, str] | None:
    """If the number already carries a country code, take it apart.

    Returns the country and the national part, or None when the number
    is not in international form. Longer dial codes are tried first so
    that 971 is not read as the 97 of nothing or the 9 of nothing.
    """
    text = textutil.normalize_digits(value or "").strip()
    if text.startswith("00"):
        rest = _digits(text[2:])
    elif text.startswith("+"):
        rest = _digits(text)
    else:
        return None
    if not rest:
        return None
    for country in sorted(COUNTRIES, key=lambda c: -len(c.dial)):
        if rest.startswith(country.dial):
            return country, rest[len(country.dial):]
    return None


def repair(value: str, country: Country | None) -> tuple[str, str]:
    """Put back what the spreadsheet took out.

    Returns the number and a note saying what was done, empty when
    nothing was. Only one thing is ever repaired -- a trunk digit that a
    numeric cell has eaten -- and only when the arithmetic leaves no
    doubt: the number must be exactly one digit short of a length that
    is valid for the country, and must not already begin with a trunk
    digit or a country code.
    """
    cleaned = textutil.clean_phone(value)
    if not cleaned:
        return "", UNCHANGED

    # Already international. Nothing was lost, so nothing is restored.
    if split_international(cleaned) is not None:
        return cleaned, UNCHANGED

    if country is None or not country.lengths or not country.trunk:
        return cleaned, UNCHANGED

    digits = _digits(cleaned)
    if not digits or digits.startswith(country.trunk):
        return cleaned, UNCHANGED

    # The test that makes this safe: with the trunk digit back, does the
    # number become exactly as long as a real one in this country?
    if len(digits) + len(country.trunk) not in country.lengths:
        return cleaned, UNCHANGED

    return country.trunk + digits, RESTORED_TRUNK


def to_international(value: str, country: Country | None) -> str:
    """The +20... form, which is what a phone and Google both want.

    A number already in international form is returned tidied. A number
    with no country to place it in is returned unchanged, because a
    wrong country code is worse than none.
    """
    cleaned = textutil.clean_phone(value)
    if not cleaned:
        return ""

    known = split_international(cleaned)
    if known is not None:
        found, national = known
        return f"+{found.dial}{national}"

    if country is None:
        return cleaned

    digits = _digits(cleaned)
    if not digits:
        return cleaned
    if country.trunk and digits.startswith(country.trunk):
        digits = digits[len(country.trunk):]
    return f"+{country.dial}{digits}"


def to_national(value: str, country: Country | None) -> str:
    """The local form, 01001234567, for a number written internationally.

    Used when showing a number to somebody in the same country, where
    the local form is the one they recognise.
    """
    cleaned = textutil.clean_phone(value)
    known = split_international(cleaned)
    if known is None:
        return cleaned
    found, national = known
    if country is not None and found.code != country.code:
        # A genuinely foreign number keeps its country code; shortening
        # it would produce something undiallable.
        return f"+{found.dial}{national}"
    return found.trunk + national if found.trunk else national


def guess_country(value: str) -> Country | None:
    """The country a number names itself, if it names one at all."""
    known = split_international(value)
    return known[0] if known else None


def internationalize(contacts, country: Country | None) -> int:
    """Rewrite the numbers on these contacts in +code form.

    Returns how many were changed. A number that already carries a
    country code keeps the one it has, so the one Saudi colleague in an
    Egyptian list is not quietly moved to Egypt.

    Meant for a copy of the contacts on their way into an exported file,
    not for the stored records: the user typed their numbers in the form
    they recognise, and that is the form they should keep seeing.
    """
    changed = 0
    for contact in contacts:
        for entry in contact.phones:
            fixed = to_international(entry.value, country)
            if fixed and fixed != entry.value:
                entry.value = fixed
                changed += 1
    return changed
