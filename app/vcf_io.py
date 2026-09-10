# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Reading and writing vCard files (.vcf).

Files exported from phones carry three traps that mangle Arabic, all of
them handled here:

1. Folding: a long line is split across lines, with continuations
   starting with a space.
2. QUOTED-PRINTABLE encoding: Arabic is written as =D9=85=D8=AD and has
   to be decoded back.
3. The encoding itself: some files are UTF-8, older ones windows-1256.

vCard 2.1, 3.0 and 4.0 are all read; 3.0 is written, being the version
most widely understood by Google and by phones.
"""

from __future__ import annotations

import quopri
from pathlib import Path

from .models import Contact, Entry
from .textutil import decode_bytes  # noqa: F401  (re-exported for convenience)

# vCard value types mapped to the type names this program uses.
_PHONE_TYPE_MAP = {
    "CELL": "Mobile",
    "MOBILE": "Mobile",
    "IPHONE": "Mobile",
    "HOME": "Home",
    "WORK": "Work",
    "MAIN": "Main",
    "PREF": "Main",
    "OTHER": "Other",
}

_EMAIL_TYPE_MAP = {
    "HOME": "Home",
    "WORK": "Work",
    "INTERNET": "",
    "PREF": "",
    "OTHER": "Other",
}

# The types written back out on export.
_PHONE_TYPE_OUT = {
    "Mobile": "CELL",
    "Home": "HOME",
    "Work": "WORK",
    "Main": "MAIN",
    "Work Fax": "WORK,FAX",
    "Home Fax": "HOME,FAX",
    "Other": "OTHER",
}

_EMAIL_TYPE_OUT = {"Home": "HOME", "Work": "WORK", "Other": "OTHER"}


# ---------------------------------------------------------------- parsing


def _is_quoted_printable(line: str) -> bool:
    """Whether this line's value is QUOTED-PRINTABLE encoded."""
    head = line.split(":", 1)[0]
    return "QUOTED-PRINTABLE" in head.upper()


def _unfold(text: str) -> list[str]:
    """Join split lines back together.

    Handles both kinds of continuation: the standard one starting with a
    space, and the one following a trailing "=" on a QUOTED-PRINTABLE line.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for raw in normalized.split("\n"):
        if lines and raw[:1] in (" ", "\t"):
            lines[-1] += raw[1:]
        elif lines and lines[-1].endswith("=") and _is_quoted_printable(lines[-1]):
            lines[-1] = lines[-1][:-1] + raw.lstrip()
        else:
            lines.append(raw)
    return lines


def _split_on_colon(line: str) -> tuple[str, str]:
    """Split at the first colon that is not inside quotes."""
    in_quotes = False
    for index, char in enumerate(line):
        if char == '"':
            in_quotes = not in_quotes
        elif char == ":" and not in_quotes:
            return line[:index], line[index + 1:]
    return line, ""


def _split_unquoted(text: str, sep: str) -> list[str]:
    """Split on a separator, ignoring separators inside quotes."""
    parts: list[str] = []
    current: list[str] = []
    in_quotes = False
    for char in text:
        if char == '"':
            in_quotes = not in_quotes
            current.append(char)
        elif char == sep and not in_quotes:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return parts


def _parse_params(chunks: list[str]) -> dict[str, list[str]]:
    """Read a line's parameters, including the 2.1 style with no TYPE=."""
    params: dict[str, list[str]] = {}
    for chunk in chunks:
        if not chunk:
            continue
        if "=" in chunk:
            key, _, value = chunk.partition("=")
            key = key.strip().upper()
            values = [v.strip().strip('"') for v in value.split(",") if v.strip()]
        else:
            key, values = "TYPE", [chunk.strip().strip('"')]
        params.setdefault(key, []).extend(values)
    return params


def _unescape(value: str) -> str:
    r"""Undo escaping: \n becomes a newline, \, becomes a comma, and so on."""
    out: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\" and index + 1 < len(value):
            nxt = value[index + 1]
            out.append("\n" if nxt in "nN" else nxt)
            index += 2
        else:
            out.append(char)
            index += 1
    return "".join(out)


def _split_structured(value: str, sep: str = ";") -> list[str]:
    """Split a compound value such as N or ADR, respecting escapes."""
    parts: list[str] = []
    current: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\" and index + 1 < len(value):
            current.append(char)
            current.append(value[index + 1])
            index += 2
            continue
        if char == sep:
            parts.append("".join(current))
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    parts.append("".join(current))
    return [_unescape(p).strip() for p in parts]


def _decode_value(value: str, params: dict[str, list[str]]) -> str:
    """Decode QUOTED-PRINTABLE when present, using the stated charset."""
    encoding = " ".join(params.get("ENCODING", [])).upper()
    if "QUOTED-PRINTABLE" not in encoding:
        return value

    charset = (params.get("CHARSET") or ["UTF-8"])[0]
    raw = quopri.decodestring(value.encode("utf-8", errors="replace"))
    for candidate in (charset, "utf-8", "cp1256"):
        try:
            return raw.decode(candidate)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def _pick_label(params: dict[str, list[str]], mapping: dict[str, str]) -> str:
    """Choose the matching type name from the vCard types given."""
    types = [t.upper() for t in params.get("TYPE", [])]
    if "FAX" in types:
        if "WORK" in types:
            return "Work Fax"
        if "HOME" in types:
            return "Home Fax"
        return "Other"
    for kind in types:
        label = mapping.get(kind)
        if label:
            return label
    return ""


def parse_text(text: str) -> list[Contact]:
    """Parse a whole vCard file and return the contacts inside it."""
    contacts: list[Contact] = []
    current: Contact | None = None
    formatted_name = ""
    has_structured_name = False

    for line in _unfold(text):
        if not line.strip():
            continue

        head, value = _split_on_colon(line)
        chunks = _split_unquoted(head, ";")
        name = chunks[0].strip().upper()
        # There may be a group prefix, such as "item1.TEL".
        if "." in name:
            name = name.rsplit(".", 1)[1]
        params = _parse_params(chunks[1:])

        if name == "BEGIN" and value.strip().upper() == "VCARD":
            current = Contact()
            formatted_name = ""
            has_structured_name = False
            continue

        if name == "END" and value.strip().upper() == "VCARD":
            if current is not None:
                if not has_structured_name and formatted_name:
                    _apply_formatted_name(current, formatted_name)
                if not current.is_blank():
                    contacts.append(current)
            current = None
            continue

        if current is None:
            continue

        value = _decode_value(value, params)

        if name == "N":
            parts = _split_structured(value)
            parts += [""] * (5 - len(parts))
            current.family_name = parts[0]
            current.given_name = parts[1]
            current.middle_name = parts[2]
            current.prefix = parts[3]
            current.suffix = parts[4]
            if any(parts[:3]):
                has_structured_name = True

        elif name == "FN":
            formatted_name = _unescape(value).strip()

        elif name == "NICKNAME":
            current.nickname = _unescape(value).strip()

        elif name == "TEL":
            if value.strip():
                current.phones.append(
                    Entry(value=_unescape(value).strip(),
                          label=_pick_label(params, _PHONE_TYPE_MAP))
                )

        elif name == "EMAIL":
            if value.strip():
                current.emails.append(
                    Entry(value=_unescape(value).strip(),
                          label=_pick_label(params, _EMAIL_TYPE_MAP))
                )

        elif name == "ORG":
            parts = _split_structured(value)
            current.organization = parts[0] if parts else ""
            if len(parts) > 1 and parts[1]:
                current.department = parts[1]

        elif name == "TITLE":
            current.job_title = _unescape(value).strip()

        elif name == "ADR":
            parts = _split_structured(value)
            joined = ", ".join(p for p in parts if p)
            if joined and not current.address:
                current.address = joined

        elif name == "NOTE":
            note = _unescape(value).strip()
            if note:
                current.notes = (
                    (current.notes + "\n" + note).strip() if current.notes else note
                )

        elif name == "BDAY":
            current.birthday = _unescape(value).strip()

        elif name == "URL":
            if not current.website:
                current.website = _unescape(value).strip()

        elif name == "CATEGORIES":
            for label in _split_structured(value, ","):
                if label and label not in current.labels:
                    current.labels.append(label)

        elif name == "UID":
            uid = _unescape(value).strip()
            if uid:
                current.uid = uid

    return contacts


def _apply_formatted_name(contact: Contact, formatted: str) -> None:
    """When the file gives only a whole name, split it into parts."""
    parts = formatted.split()
    if not parts:
        return
    if len(parts) == 1:
        contact.given_name = parts[0]
    else:
        contact.given_name = parts[0]
        contact.family_name = parts[-1]
        if len(parts) > 2:
            contact.middle_name = " ".join(parts[1:-1])


def read_file(path: Path | str) -> list[Contact]:
    """Read a .vcf file from disk."""
    data = Path(path).read_bytes()
    return parse_text(decode_bytes(data))


# ---------------------------------------------------------------- writing


def _escape(value: str) -> str:
    """Escape the characters that carry special meaning in vCard."""
    if not value:
        return ""
    out = value.replace("\\", "\\\\")
    out = out.replace("\n", "\\n").replace("\r", "")
    out = out.replace(",", "\\,").replace(";", "\\;")
    return out


def _fold(line: str, limit: int = 73) -> str:
    """Split a long line per the standard, never cutting a character in two."""
    if len(line.encode("utf-8")) <= limit:
        return line
    pieces: list[str] = []
    current = b""
    for char in line:
        encoded = char.encode("utf-8")
        if len(current) + len(encoded) > limit:
            pieces.append(current.decode("utf-8"))
            current = encoded
        else:
            current += encoded
    if current:
        pieces.append(current.decode("utf-8"))
    return "\r\n ".join(pieces)


def to_vcard(contact: Contact) -> str:
    """Convert one contact into vCard 3.0 text."""
    lines: list[str] = ["BEGIN:VCARD", "VERSION:3.0"]

    name_parts = [
        _escape(contact.family_name),
        _escape(contact.given_name),
        _escape(contact.middle_name),
        _escape(contact.prefix),
        _escape(contact.suffix),
    ]
    lines.append("N:" + ";".join(name_parts))
    lines.append("FN:" + _escape(contact.display_name))

    if contact.nickname:
        lines.append("NICKNAME:" + _escape(contact.nickname))

    if contact.organization or contact.department:
        lines.append(
            "ORG:" + _escape(contact.organization) + ";" + _escape(contact.department)
        )
    if contact.job_title:
        lines.append("TITLE:" + _escape(contact.job_title))

    for entry in contact.phones:
        kind = _PHONE_TYPE_OUT.get(entry.label, "VOICE")
        lines.append(f"TEL;TYPE={kind}:" + _escape(entry.value))

    for entry in contact.emails:
        kind = _EMAIL_TYPE_OUT.get(entry.label)
        prefix = f"EMAIL;TYPE=INTERNET,{kind}:" if kind else "EMAIL;TYPE=INTERNET:"
        lines.append(prefix + _escape(entry.value))

    if contact.address:
        # Standard order: po box, extended, street, city, region, code, country.
        lines.append("ADR;TYPE=HOME:;;" + _escape(contact.address) + ";;;;")

    if contact.website:
        lines.append("URL:" + _escape(contact.website))
    if contact.birthday:
        lines.append("BDAY:" + _escape(contact.birthday))
    if contact.notes:
        lines.append("NOTE:" + _escape(contact.notes))
    if contact.labels:
        lines.append("CATEGORIES:" + ",".join(_escape(x) for x in contact.labels))
    if contact.uid:
        lines.append("UID:" + _escape(contact.uid))

    lines.append("END:VCARD")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def write_file(path: Path | str, contacts: list[Contact]) -> int:
    """Write contacts to a .vcf file; returns how many were written."""
    text = "".join(to_vcard(contact) for contact in contacts)
    Path(path).write_bytes(text.encode("utf-8"))
    return len(contacts)
