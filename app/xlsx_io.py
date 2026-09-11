# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Reading .xlsx workbooks, using nothing but the standard library.

An .xlsx file is a ZIP archive of XML documents, and `zipfile` and
`xml.etree` both ship with Python. Reading one therefore needs no
external package, which matters here: the program is handed out as a
single portable .exe, and every dependency added to it is weight the
user carries around for the life of the program.

What this module does *not* do is as important as what it does. It does
not evaluate formulas, keep styling, or write anything. It turns a sheet
into a rectangle of strings, and stops. Working out which column holds a
phone number is somebody else's job.

Three things here are easy to get wrong and are handled deliberately:

* **Sheet order.** The file names under xl/worksheets/ do not follow the
  order of the tabs, so sheet3.xml can perfectly well be the first tab.
  The order comes from xl/workbook.xml, and the file each entry points
  at comes from the relationships file beside it.

* **Dates.** Excel stores a date as a plain number and records
  separately that the cell should be *displayed* as a date. A reader
  that ignores styles turns a birthday into 39582.

* **Missing cells.** A row holds only the cells that have something in
  them, so the fourth cell in the XML may belong in column H. Every cell
  is placed by its own reference, never by its position in the row.

Not supported, deliberately: the older binary .xls format, which shares
nothing with this one but a file extension, and .ods. Both open in Excel
or LibreOffice and save as .xlsx in a couple of seconds.
"""

from __future__ import annotations

import re
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import NamedTuple
from xml.etree import ElementTree

# The namespaces Excel writes. They are part of the format, not a detail
# of one writer, so matching on them is safe.
MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
DOC_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"

# Number formats that are built into the format itself and always mean a
# date or a time. Anything else has to be judged from its format code.
BUILTIN_DATE_FORMATS = frozenset(
    list(range(14, 23)) + list(range(27, 37)) + list(range(45, 48))
    + list(range(50, 59))
)

# Excel counts days from an epoch two days before 1900-01-01. The gap is
# not a mistake in this code: Excel believes 1900 was a leap year, and
# every spreadsheet in the world now depends on that belief.
EPOCH_1900 = datetime(1899, 12, 30)
EPOCH_1904 = datetime(1904, 1, 1)

# Excel escapes characters it cannot put in XML as _xXXXX_.
ESCAPED_CHAR = re.compile(r"_x([0-9A-Fa-f]{4})_")

# A cell reference is a column of letters followed by a row of digits.
CELL_REF = re.compile(r"^([A-Z]+)(\d+)$")


class Sheet(NamedTuple):
    """One tab of a workbook, as a rectangle of strings."""

    name: str
    rows: list[list[str]]


class WorkbookError(Exception):
    """The file is not a workbook this module can read."""


# ------------------------------------------------------------- helpers


def _column_index(reference: str) -> int:
    """Turn the letters of a cell reference into a zero-based column.

    A -> 0, B -> 1, Z -> 25, AA -> 26. Institutional sheets run well
    past Z, so the carrying has to be right rather than a lookup of
    single letters.
    """
    total = 0
    for char in reference:
        if not char.isalpha():
            break
        total = total * 26 + (ord(char.upper()) - 64)
    return total - 1


def _unescape(text: str) -> str:
    """Undo Excel's _xXXXX_ escapes for characters XML cannot hold.

    A literal underscore-x sequence in the user's own text is written
    _x005F_ first, so that one is put back before the rest are decoded;
    otherwise text that merely looks like an escape would be mangled.
    """
    if "_x" not in text:
        return text
    placeholder = "\x00"
    text = text.replace("_x005F_", placeholder)
    text = ESCAPED_CHAR.sub(lambda m: chr(int(m.group(1), 16)), text)
    return text.replace(placeholder, "_x005F_")


def _number_text(raw: str) -> str:
    """Render a stored number the way a person wrote it.

    Excel stores every number as a float, so a phone number read back
    naively becomes 1001234567.0 and a long one turns into scientific
    notation. Whole numbers are therefore printed as whole numbers.
    """
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return raw
    if value.is_integer() and abs(value) < 1e15:
        return str(int(value))
    return repr(value)


def _looks_like_date(code: str) -> bool:
    """Judge a custom number format by its code.

    Quoted text, escaped characters, and the bracketed colour and
    condition parts are removed first: a currency format such as
    "SAR"#,##0.00 would otherwise be read as a date because of the
    letters inside the quotes.
    """
    cleaned = re.sub(r'"[^"]*"', "", code)
    cleaned = re.sub(r"\[[^\]]*\]", "", cleaned)
    cleaned = re.sub(r"\\.", "", cleaned)
    return bool(re.search(r"[ymdhs]", cleaned, re.IGNORECASE))


def _serial_to_text(serial: float, epoch: datetime) -> str:
    """Turn Excel's day count into something a person can read.

    A whole number is a date and is written as one. A value carrying a
    fraction also has a time in it, and both parts are kept.
    """
    try:
        moment = epoch + timedelta(days=float(serial))
    except (OverflowError, ValueError):
        return _number_text(str(serial))
    if abs(float(serial) - int(float(serial))) < 1e-9:
        return moment.strftime("%Y-%m-%d")
    return moment.strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------- the archive


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    """The workbook's string table.

    Excel stores every piece of text once here and refers to it by
    number from the cells. A string split into differently formatted
    runs arrives as several <t> elements inside one entry, and they are
    joined back into the one string the user typed.
    """
    try:
        data = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    out: list[str] = []
    for entry in ElementTree.fromstring(data):
        pieces = [node.text or "" for node in entry.iter(MAIN + "t")]
        out.append(_unescape("".join(pieces)))
    return out


def _date_styles(archive: zipfile.ZipFile) -> list[bool]:
    """For each style in the workbook, whether it displays a date.

    A cell points at a style, the style points at a number format, and
    only the number format says whether 39582 is a quantity or a
    birthday.
    """
    try:
        data = archive.read("xl/styles.xml")
    except KeyError:
        return []
    root = ElementTree.fromstring(data)

    custom: dict[int, bool] = {}
    for fmt in root.iter(MAIN + "numFmt"):
        try:
            number = int(fmt.get("numFmtId", "-1"))
        except ValueError:
            continue
        custom[number] = _looks_like_date(fmt.get("formatCode", ""))

    out: list[bool] = []
    container = root.find(MAIN + "cellXfs")
    for style in (container if container is not None else []):
        try:
            number = int(style.get("numFmtId", "0"))
        except ValueError:
            number = 0
        out.append(custom.get(number, number in BUILTIN_DATE_FORMATS))
    return out


def _sheet_parts(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    """The tabs in the order they appear, each with the file holding it.

    The name shown on the tab lives in xl/workbook.xml; the file that
    holds the cells is found by following the relationship id from
    there through xl/_rels/workbook.xml.rels. Guessing from the file
    names instead would silently read the wrong tab.
    """
    try:
        book = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    except KeyError as error:
        raise WorkbookError("no workbook inside the file") from error

    targets: dict[str, str] = {}
    try:
        rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    except KeyError:
        rels = None
    for relation in (rels if rels is not None else []):
        target = relation.get("Target", "")
        if target.startswith("/"):
            target = target[1:]
        elif not target.startswith("xl/"):
            target = "xl/" + target
        targets[relation.get("Id", "")] = target

    names = archive.namelist()
    out: list[tuple[str, str]] = []
    for index, sheet in enumerate(book.iter(MAIN + "sheet")):
        name = sheet.get("name") or f"Sheet{index + 1}"
        path = targets.get(sheet.get(DOC_REL + "id", ""), "")
        if path not in names:
            # A workbook written by something other than Excel may not
            # carry usable relationships. Fall back to position.
            guess = f"xl/worksheets/sheet{index + 1}.xml"
            path = guess if guess in names else ""
        if path:
            out.append((name, path))
    return out


def _uses_1904(archive: zipfile.ZipFile) -> bool:
    """Whether the workbook counts days from 1904 instead of 1900.

    Old Mac spreadsheets do. Reading a date four years wrong is worse
    than the two lines it takes to check.
    """
    try:
        book = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    except KeyError:
        return False
    for properties in book.iter(MAIN + "workbookPr"):
        if properties.get("date1904") in ("1", "true"):
            return True
    return False


def _read_rows(
    archive: zipfile.ZipFile,
    path: str,
    strings: list[str],
    date_styles: list[bool],
    epoch: datetime,
) -> list[list[str]]:
    """Turn one sheet into rows of text.

    Rows and cells are both placed by the reference they carry rather
    than by the order they arrive in, because Excel leaves out anything
    empty: a row holding only column H has a single cell in the XML.
    """
    rows: dict[int, dict[int, str]] = {}

    with archive.open(path) as handle:
        for event, element in ElementTree.iterparse(handle, ("end",)):
            if element.tag != MAIN + "c":
                continue

            reference = element.get("r", "")
            match = CELL_REF.match(reference)
            if match:
                column = _column_index(match.group(1))
                row = int(match.group(2)) - 1
            else:
                continue

            kind = element.get("t", "n")
            value = element.find(MAIN + "v")
            text = ""

            if kind == "s":
                # An index into the shared string table.
                try:
                    text = strings[int(value.text)] if value is not None else ""
                except (ValueError, IndexError):
                    text = ""
            elif kind == "inlineStr":
                inline = element.find(MAIN + "is")
                if inline is not None:
                    text = _unescape("".join(
                        node.text or "" for node in inline.iter(MAIN + "t")
                    ))
            elif kind == "str":
                # A formula that worked out to text. The cached result is
                # used; the formula itself is not evaluated.
                text = _unescape(value.text or "") if value is not None else ""
            elif kind == "b":
                text = "TRUE" if (value is not None and value.text == "1") else "FALSE"
            elif kind == "e":
                # #N/A and friends. An error is not data, so the cell is
                # read as empty rather than carrying "#N/A" into a name.
                text = ""
            elif value is not None and value.text is not None:
                raw = value.text
                try:
                    style = int(element.get("s", "-1"))
                except ValueError:
                    style = -1
                if 0 <= style < len(date_styles) and date_styles[style]:
                    text = _serial_to_text(raw, epoch)
                else:
                    text = _number_text(raw)

            if text:
                rows.setdefault(row, {})[column] = text

            # iterparse keeps every element it has seen; clearing each
            # cell as it finishes keeps a large sheet from being held in
            # memory twice over.
            element.clear()

    if not rows:
        return []

    width = max(max(cells) for cells in rows.values()) + 1
    return [
        [rows.get(index, {}).get(column, "") for column in range(width)]
        for index in range(max(rows) + 1)
    ]


# ------------------------------------------------------------- reading


def looks_like_workbook(path: Path | str) -> bool:
    """Whether this file is an .xlsx we can open.

    The extension is not trusted on its own: a renamed .xls would pass
    that test and then fail confusingly deeper in.
    """
    try:
        with zipfile.ZipFile(path) as archive:
            return "xl/workbook.xml" in archive.namelist()
    except (zipfile.BadZipFile, OSError):
        return False


def sheet_names(path: Path | str) -> list[str]:
    """The tab names, in the order they appear in the workbook."""
    try:
        with zipfile.ZipFile(path) as archive:
            return [name for name, _ in _sheet_parts(archive)]
    except zipfile.BadZipFile as error:
        raise WorkbookError("the file is not a workbook") from error


def read_sheet(path: Path | str, which: int | str = 0) -> Sheet:
    """Read one tab, by position or by name."""
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as error:
        raise WorkbookError("the file is not a workbook") from error

    with archive:
        parts = _sheet_parts(archive)
        if not parts:
            raise WorkbookError("the workbook has no sheets")

        if isinstance(which, str):
            wanted = [p for p in parts if p[0] == which]
            if not wanted:
                raise WorkbookError(f"no sheet named {which!r}")
            name, inside = wanted[0]
        else:
            if not 0 <= which < len(parts):
                raise WorkbookError(f"no sheet at position {which}")
            name, inside = parts[which]

        strings = _shared_strings(archive)
        styles = _date_styles(archive)
        epoch = EPOCH_1904 if _uses_1904(archive) else EPOCH_1900
        return Sheet(name, _read_rows(archive, inside, strings, styles, epoch))


def read_all(path: Path | str) -> list[Sheet]:
    """Read every tab in the workbook."""
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as error:
        raise WorkbookError("the file is not a workbook") from error

    with archive:
        strings = _shared_strings(archive)
        styles = _date_styles(archive)
        epoch = EPOCH_1904 if _uses_1904(archive) else EPOCH_1900
        return [
            Sheet(name, _read_rows(archive, inside, strings, styles, epoch))
            for name, inside in _sheet_parts(archive)
        ]
