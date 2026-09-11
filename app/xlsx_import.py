# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Turning a spreadsheet into contacts.

A Google CSV export arrives with columns the program already knows by
name. A spreadsheet from a school or a company arrives with whatever the
person who made it happened to type, under two rows of letterhead, on
the third of five tabs, with the serial numbers in column A.

So this module does not try to be clever and quiet. It guesses, shows
its guesses, and lets the user correct every one of them. A wrong guess
that the user can see and change is a small annoyance; a wrong guess
made silently is corrupted data.

Nothing in here raises for a file that merely has an odd shape. An empty
sheet, a sheet with no header, a header that is not on the first row, a
column of things nobody can identify -- all of these produce a result
the user can work with and a plain statement of what was found.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import csv_io, phones, textutil, xlsx_io
from .models import Contact, Entry

# How far down the sheet to look for the header. Letterhead, logos and
# blank spacer rows are usually a handful of rows; past twenty, a row of
# headings is almost certainly not a heading.
HEADER_SEARCH_DEPTH = 20

# Rows shown in the mapping window so the user can see what they are
# about to import.
PREVIEW_ROWS = 8

# The longest a cell can be and still be treated as somebody's name. A
# spreadsheet often carries a paragraph of prose in a column next to the
# names, and if such a cell is mapped onto a name -- by a wrong guess or
# a wrong choice -- splitting it produces a contact whose first name is
# an entire sentence. Well past the longest real name, so no genuine one
# is ever caught by it; the text is kept as a note instead of thrown
# away.
MAX_NAME_LENGTH = 80

# Meaning: this column is not imported at all.
IGNORE = ""

# Meaning: one column holding a whole name, split into parts on import.
FULL_NAME = "full_name"

# Meaning: the groups the contact belongs to.
LABELS = "labels"

# Columns that count rather than describe. A sheet from an institution
# nearly always starts with one, and mapping it onto a phone number --
# which the alias "رقم" would otherwise do -- produces nonsense in every
# row of the file.
COUNTING_HEADERS = frozenset(
    csv_io.normalize_header(x) for x in [
        "م", "م.", "ت", "مسلسل", "رقم مسلسل", "المسلسل", "الرقم المسلسل",
        "#", "no", "no.", "num", "s/n", "sn", "serial", "index", "seq",
        "order", "count", "الترتيب", "رقم الطالب", "كود",
    ]
)

# Columns holding identity numbers, which this program will not import
# under any mapping.
#
# This is a deliberate refusal, not an omission. A national ID is not
# contact data -- nobody dials it -- and contacts here are made to be
# exported and uploaded to Google. Carrying a few hundred citizens'
# identity numbers into a foreign cloud service, because they happened
# to sit in the next column of a school's spreadsheet, is a harm the
# user would not have chosen and might not notice for years.
#
# The number is also dangerous specifically *here*: an Egyptian national
# ID is fourteen digits, and a phone number is accepted at anything from
# five to fifteen, so a single wrong mapping would file it as somebody's
# mobile and dial it into the export. The check below therefore guards
# the value as well as the heading.
SENSITIVE_HEADERS = frozenset(
    csv_io.normalize_header(x) for x in [
        "الرقم القومي", "رقم قومي", "الرقم القومى", "رقم البطاقة",
        "بطاقة الرقم القومي", "الرقم القومي لولي الأمر", "رقم الهوية",
        "الهوية الوطنية", "رقم الهوية الوطنية", "السجل المدني",
        "رقم جواز السفر", "جواز السفر", "الرقم التأميني", "التأمينات",
        "national id", "national identity", "id number", "identity number",
        "nid", "ssn", "social security number", "passport", "passport number",
        "iqama", "رقم الإقامة",
    ]
)

# Fourteen digits opening with 2 or 3 -- the century marker of an
# Egyptian national ID, followed by a birth date. Deliberately narrow:
# it must not swallow a long foreign phone number, so the shape has to
# match rather than merely the length.
NATIONAL_ID = re.compile(r"^[23]\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{7}$")


def looks_like_national_id(value: str) -> bool:
    """Whether a cell holds what appears to be an identity number."""
    digits = re.sub(r"\D", "", textutil.normalize_digits(value or ""))
    return bool(NATIONAL_ID.match(digits))


def is_sensitive_header(heading: str) -> bool:
    """Whether a column heading names an identity number."""
    return csv_io.normalize_header(heading) in SENSITIVE_HEADERS


# Extra headings seen on institutional sheets, which the CSV tables do
# not carry because no export format produces them.
EXTRA_PHONES = {
    csv_io.normalize_header(x): "Mobile" for x in [
        "رقم ولي الأمر", "تليفون ولي الأمر", "هاتف ولي الأمر", "موبايل ولي الأمر",
        "رقم الأب", "رقم الأم", "رقم الوالد", "رقم الوالدة", "رقم التواصل",
        "رقم الجوال", "جوال", "رقم المحمول", "رقم للتواصل", "تليفون للتواصل",
        "phone number", "contact number", "mobile number", "whatsapp",
        "رقم الواتس", "رقم الواتساب",
    ]
}

EXTRA_SINGLES = {
    csv_io.normalize_header("محل الإقامة"): "address",
    csv_io.normalize_header("مكان الإقامة"): "address",
    csv_io.normalize_header("عنوان السكن"): "address",
    csv_io.normalize_header("المدينة"): "address",
    csv_io.normalize_header("اسم ولي الأمر"): "full_name_parent",
    csv_io.normalize_header("ملاحظات المعلم"): "notes",
    csv_io.normalize_header("الفصل"): "job_title",
    csv_io.normalize_header("المجموعة"): "labels",
}

# The fields a column can be mapped onto, in the order they appear in
# the mapping window. The English text is the source string; it is
# translated for display, and the key is what gets stored.
FIELD_CHOICES: tuple[tuple[str, str], ...] = (
    (IGNORE, "Do not import"),
    (FULL_NAME, "Full name"),
    ("given_name", "First name"),
    ("middle_name", "Middle name"),
    ("family_name", "Last name"),
    ("nickname", "Nickname"),
    ("phone:Mobile", "Mobile phone"),
    ("phone:Home", "Home phone"),
    ("phone:Work", "Work phone"),
    ("phone:Other", "Other phone"),
    ("email:", "E-mail"),
    ("email:Work", "Work e-mail"),
    ("email:Home", "Home e-mail"),
    ("organization", "Organization"),
    ("job_title", "Job title"),
    ("department", "Department"),
    ("address", "Address"),
    ("website", "Website"),
    ("birthday", "Birthday"),
    (LABELS, "Groups"),
    ("notes", "Notes"),
)

FIELD_KEYS = frozenset(key for key, _ in FIELD_CHOICES)

# Plain fields that are copied straight onto the contact.
PLAIN_FIELDS = frozenset([
    "given_name", "middle_name", "family_name", "prefix", "suffix",
    "nickname", "organization", "job_title", "department", "address",
    "website", "birthday", "notes",
])


@dataclass
class Report:
    """What happened during an import, in numbers the user can check."""

    rows_read: int = 0
    rows_blank: int = 0
    rows_empty_contact: int = 0
    contacts: int = 0
    phones_repaired: int = 0
    ids_blocked: int = 0
    sensitive_columns: list[str] = field(default_factory=list)
    unmapped: list[str] = field(default_factory=list)

    def lines(self) -> list[tuple[str, object]]:
        """The findings as (source string, value) pairs, ready to translate."""
        out: list[tuple[str, object]] = [
            ("Rows read: {count}", self.rows_read),
            ("Contacts found: {count}", self.contacts),
        ]
        if self.phones_repaired:
            out.append(("Phone numbers repaired: {count}", self.phones_repaired))
        if self.ids_blocked:
            out.append(("Identity numbers left out: {count}", self.ids_blocked))
        if self.rows_blank:
            out.append(("Blank rows skipped: {count}", self.rows_blank))
        if self.rows_empty_contact:
            out.append(("Rows with nothing to import: {count}", self.rows_empty_contact))
        return out


@dataclass
class SheetPlan:
    """Everything needed to read one tab, and everything guessed about it."""

    name: str
    rows: list[list[str]]
    header_row: int = 0
    mapping: dict[int, str] = field(default_factory=dict)

    @property
    def headers(self) -> list[str]:
        """The column headings, or invented ones when there is no header."""
        if 0 <= self.header_row < len(self.rows):
            return list(self.rows[self.header_row])
        return [column_letter(i) for i in range(self.width)]

    @property
    def width(self) -> int:
        return max((len(row) for row in self.rows), default=0)

    @property
    def data_rows(self) -> list[list[str]]:
        """The rows below the header, blank ones included."""
        return self.rows[self.header_row + 1:] if self.header_row >= 0 else self.rows

    def preview(self, count: int = PREVIEW_ROWS) -> list[list[str]]:
        """A few real rows, for showing beside the mapping choices."""
        out = [row for row in self.data_rows if any(c.strip() for c in row)]
        return out[:count]

    def is_usable(self) -> bool:
        """Whether there is anything here worth importing."""
        return bool(self.preview(1)) and any(
            key for key in self.mapping.values() if key
        )


def column_letter(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA, for a sheet with no headings of its own."""
    letters = ""
    index += 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


# ------------------------------------------------------------ guessing


def field_for_header(raw: str) -> str:
    """The field a heading most likely means, or IGNORE when unclear."""
    key = csv_io.normalize_header(raw)
    if not key or key in COUNTING_HEADERS or key in SENSITIVE_HEADERS:
        return IGNORE

    if key in EXTRA_PHONES:
        return "phone:" + EXTRA_PHONES[key]
    if key in EXTRA_SINGLES:
        target = EXTRA_SINGLES[key]
        if target == "full_name_parent":
            # A parent's name is a name, but not the student's; it is the
            # contact being created, so it maps to the whole name.
            return FULL_NAME
        return LABELS if target == "labels" else target

    if key in csv_io.FULL_NAME_FIELDS:
        return FULL_NAME
    if key in csv_io.LABEL_FIELDS:
        return LABELS
    if key in csv_io.SINGLE_FIELDS:
        found = csv_io.SINGLE_FIELDS[key]
        return found if found in PLAIN_FIELDS else IGNORE
    if key in csv_io.PHONE_FIELDS:
        return "phone:" + csv_io.PHONE_FIELDS[key]
    if key in csv_io.EMAIL_FIELDS:
        return "email:" + csv_io.EMAIL_FIELDS[key]
    return IGNORE


def guess_mapping(headers: list[str]) -> dict[int, str]:
    """Map each column onto a field, as far as the headings allow.

    A field that two columns both claim is given to the first, and the
    second is left unmapped rather than silently overwriting: two
    columns called "phone" are two different numbers, and the user
    decides which is which.
    """
    out: dict[int, str] = {}
    taken: set[str] = set()
    for index, heading in enumerate(headers):
        key = field_for_header(heading)
        if not key:
            out[index] = IGNORE
            continue
        # Several phone or e-mail columns are normal and wanted; several
        # columns claiming to be the first name are not.
        if key in taken and not key.startswith(("phone:", "email:")):
            out[index] = IGNORE
            continue
        out[index] = key
        taken.add(key)
    return out


def _score_header(row: list[str]) -> tuple[int, int]:
    """How much a row looks like a row of headings.

    Two numbers, in order: how many cells name a field the program
    recognises, and how many cells hold anything at all. The first
    matters far more -- a row of ten names scores nothing on it, while a
    row of ten headings scores highly -- and the second only separates
    rows that tie.
    """
    known = sum(1 for cell in row if field_for_header(cell))
    filled = sum(1 for cell in row if cell.strip())
    return known, filled


def find_header_row(rows: list[list[str]]) -> int:
    """Work out which row holds the column headings.

    Institutional sheets put a school name, a year and a blank line above
    the real headings, so the first row is often the worst guess
    available. Returns -1 when no row looks like a header at all, which
    the caller treats as a sheet whose data starts immediately.
    """
    best_index = -1
    best_score = (0, 0)
    limit = min(len(rows), HEADER_SEARCH_DEPTH)

    for index in range(limit):
        row = rows[index]
        if not any(cell.strip() for cell in row):
            continue
        # A header with nothing under it is not a header.
        if not any(any(c.strip() for c in later) for later in rows[index + 1:]):
            continue
        score = _score_header(row)
        if score[0] and score > best_score:
            best_score = score
            best_index = index

    if best_index >= 0:
        return best_index

    # Nothing recognisable. Fall back to the first row carrying more than
    # one value, which is what a header looks like even when its wording
    # is unknown to us.
    for index in range(limit):
        if sum(1 for cell in rows[index] if cell.strip()) > 1:
            return index
    return -1


def plan_sheet(sheet: xlsx_io.Sheet) -> SheetPlan:
    """Read a tab and guess everything guessable about it."""
    plan = SheetPlan(name=sheet.name, rows=sheet.rows)
    plan.header_row = find_header_row(sheet.rows)
    plan.mapping = guess_mapping(plan.headers)
    return plan


def survey(path: Path | str) -> list[SheetPlan]:
    """Open a workbook and plan every tab in it.

    A tab that cannot be read for any reason becomes an empty plan
    rather than stopping the others: one broken sheet in a five-sheet
    workbook must not cost the user the other four.
    """
    plans: list[SheetPlan] = []
    for sheet in xlsx_io.read_all(path):
        try:
            plans.append(plan_sheet(sheet))
        except Exception:  # noqa: BLE001 (one bad tab must not end the import)
            plans.append(SheetPlan(name=sheet.name, rows=[], header_row=-1))
    return plans


def best_sheet(plans: list[SheetPlan]) -> int:
    """Which tab to offer first.

    The one with the most mapped columns and the most rows under them,
    because a workbook often opens on an instructions tab while the
    contacts sit on the second.
    """
    best_index = 0
    best_score = (-1, -1)
    for index, plan in enumerate(plans):
        mapped = sum(1 for key in plan.mapping.values() if key)
        score = (mapped, len(plan.preview(1000)))
        if score > best_score:
            best_score = score
            best_index = index
    return best_index


# ----------------------------------------------------------- importing


def _apply(contact: Contact, key: str, value: str,
           country: phones.Country | None, report: Report) -> None:
    """Put one cell onto the contact, according to its mapping."""
    value = value.strip()
    if not value:
        return

    # Checked for every field, not only phones: a heading the program
    # did not recognise as sensitive, or a mapping the user set by hand,
    # must still not carry an identity number into the contact.
    if looks_like_national_id(value):
        report.ids_blocked += 1
        return

    if key == FULL_NAME:
        if len(value) > MAX_NAME_LENGTH:
            contact.notes = (contact.notes + "\n" + value).strip()
            return
        parts = value.split()
        if not parts:
            return
        if not contact.given_name:
            contact.given_name = parts[0]
            if len(parts) > 2:
                contact.middle_name = " ".join(parts[1:-1])
            if len(parts) > 1:
                contact.family_name = parts[-1]
        return

    if key == LABELS:
        for piece in value.replace(";", ",").split(","):
            piece = piece.strip()
            if piece and piece not in contact.labels:
                contact.labels.append(piece)
        return

    if key.startswith("phone:"):
        fixed, note = phones.repair(value, country)
        if note:
            report.phones_repaired += 1
        if fixed and not any(
            textutil.phone_key(e.value) == textutil.phone_key(fixed)
            for e in contact.phones
        ):
            contact.phones.append(Entry(value=fixed, label=key.split(":", 1)[1]))
        return

    if key.startswith("email:"):
        address = textutil.clean_email(value)
        if address and not any(e.value == address for e in contact.emails):
            contact.emails.append(Entry(value=address, label=key.split(":", 1)[1]))
        return

    if (key in ("given_name", "middle_name", "family_name", "nickname")
            and len(value) > MAX_NAME_LENGTH):
        contact.notes = (contact.notes + "\n" + value).strip()
        return

    if key in PLAIN_FIELDS:
        current = getattr(contact, key, "")
        if not current:
            setattr(contact, key, value)
        elif key == "notes":
            # Several note columns are worth keeping, one under the other.
            setattr(contact, key, current + "\n" + value)


def build(plan: SheetPlan, country: phones.Country | None) -> tuple[list[Contact], Report]:
    """Turn the planned sheet into contacts.

    A row yields a contact only when something identifying came out of
    it. A row of nothing but a serial number and a class produces a
    contact with no name, no number and no address, which is not a
    contact and is counted and skipped instead.
    """
    report = Report()
    out: list[Contact] = []

    for row in plan.data_rows:
        report.rows_read += 1
        if not any(cell.strip() for cell in row):
            report.rows_blank += 1
            continue

        contact = Contact()
        for index, key in plan.mapping.items():
            if key and index < len(row):
                _apply(contact, key, row[index], country, report)

        has_name = any([contact.given_name, contact.family_name,
                        contact.middle_name, contact.nickname,
                        contact.organization])
        if not (has_name or contact.phones or contact.emails):
            report.rows_empty_contact += 1
            continue

        out.append(contact)

    report.contacts = len(out)
    report.sensitive_columns = [
        heading.strip()
        for heading in plan.headers
        if csv_io.normalize_header(heading) in SENSITIVE_HEADERS
    ]
    report.unmapped = [
        heading.strip()
        for index, heading in enumerate(plan.headers)
        if heading.strip()
        and not plan.mapping.get(index)
        and heading.strip() not in report.sensitive_columns
    ]
    return out, report
