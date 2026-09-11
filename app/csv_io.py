# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Reading and writing CSV files, compatible with Google Contacts.

This module recognizes several file shapes without asking the user:

* Newer Google Contacts export: First Name, Phone 1 - Value, Labels
* Older Google Contacts export: Given Name, Phone 1 - Type, Group Membership
* Outlook export: Mobile Phone, Business Phone, E-mail Address
* A plain Arabic file the user wrote themselves: الاسم, الموبايل, البريد

Export uses the newer Google shape, so the file uploads to a Google
account without trouble.

The Arabic strings in the tables below are data, not interface text:
they are the column headings the program must recognize in files people
actually have, so they are matched literally and never translated.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from . import textutil
from .models import Contact, Entry


def _norm(header: str) -> str:
    """Fold a column heading so matching works however it was written."""
    text = (header or "").replace("﻿", "").strip().strip('"').lower()
    text = text.replace("e-mail", "email").replace("e mail", "email")
    text = re.sub(r"\s+", " ", text)
    return textutil.normalize_text(text)


# The same folding, under a name other modules may use. Reading a
# spreadsheet has to match headings exactly as CSV import does, and two
# copies of this rule would drift apart the first time one was fixed.
normalize_header = _norm


def _build(mapping: dict[str, list[str]]) -> dict[str, str]:
    """Invert (field -> aliases) into (alias -> field)."""
    out: dict[str, str] = {}
    for field, aliases in mapping.items():
        for alias in aliases:
            out[_norm(alias)] = field
    return out


# Single-value columns, each feeding one field of the contact.
SINGLE_FIELDS = _build(
    {
        "given_name": ["first name", "given name", "الاسم الأول", "الاسم الاول"],
        "middle_name": ["middle name", "additional name", "الاسم الأوسط", "الاسم الاوسط"],
        "family_name": ["last name", "family name", "surname", "اسم العائلة", "العائلة"],
        "prefix": ["name prefix", "prefix", "title", "البادئة"],
        "suffix": ["name suffix", "suffix", "اللاحقة"],
        "nickname": ["nickname", "short name", "الاسم المستعار", "الكنية"],
        "organization": [
            "organization name", "company", "company name", "organization",
            "الجهة", "الشركة", "المدرسة", "المؤسسة", "جهة العمل",
        ],
        "job_title": [
            "organization title", "job title", "position",
            "الوظيفة", "المسمى الوظيفي", "الصف", "المرحلة",
        ],
        "department": ["organization department", "department", "القسم", "الشعبة"],
        "birthday": ["birthday", "date of birth", "تاريخ الميلاد", "الميلاد"],
        "notes": ["notes", "note", "ملاحظات", "ملاحظة"],
        "website": ["website", "web page", "url", "الموقع"],
        "address": ["address", "home address", "العنوان", "السكن"],
    }
)

# Whole-name columns, split into parts when no detailed columns exist.
FULL_NAME_FIELDS = {
    _norm(x) for x in ["name", "full name", "display name", "file as",
                       "الاسم", "الاسم الكامل", "اسم الطالب"]
}

# Group columns.
LABEL_FIELDS = {
    _norm(x) for x in ["labels", "group membership", "categories", "groups",
                       "المجموعة", "المجموعات", "التصنيف"]
}

# Phone columns with a fixed type (the Outlook shape, and plain files).
PHONE_FIELDS = _build(
    {
        "Mobile": ["mobile phone", "cell phone", "mobile",
                   "الموبايل", "المحمول", "الجوال", "رقم الموبايل",
                   "التليفون", "الهاتف", "رقم الهاتف", "تليفون", "رقم"],
        "Home": ["home phone", "home phone 2", "هاتف المنزل", "تليفون المنزل"],
        "Work": ["business phone", "work phone", "business phone 2",
                 "هاتف العمل", "تليفون العمل"],
        "Main": ["primary phone", "main phone", "الهاتف الأساسي"],
        "Work Fax": ["business fax", "work fax", "فاكس العمل"],
        "Home Fax": ["home fax", "فاكس المنزل"],
        "Other": ["other phone", "هاتف آخر", "رقم آخر"],
    }
)

EMAIL_FIELDS = _build(
    {
        "": ["email address", "email 2 address", "email 3 address", "email",
             "البريد", "الإيميل", "الايميل", "البريد الإلكتروني",
             "البريد الالكتروني", "بريد"],
        "Work": ["business email", "work email", "بريد العمل"],
        "Home": ["home email", "بريد المنزل"],
    }
)

# Google's numbered columns, such as Phone 1 - Value and Email 2 - Label.
NUMBERED = re.compile(
    r"^(email|phone|address|website|organization|im|relation|event|custom field)"
    r"\s*(\d+)\s*-\s*(.+)$"
)

# The separator Google puts between group names.
LABEL_SEP = " ::: "


# ---------------------------------------------------------------- reading


def _sniff_delimiter(sample: str) -> str:
    """Guess the separator from the first line: comma, semicolon or tab."""
    first = sample.split("\n", 1)[0]
    counts = {d: first.count(d) for d in (",", ";", "\t")}
    best = max(counts, key=lambda d: counts[d])
    return best if counts[best] > 0 else ","


def _split_labels(value: str) -> list[str]:
    """Split the groups column, dropping Google's internal groups."""
    if not value:
        return []
    if LABEL_SEP.strip() in value:
        parts = [p.strip() for p in value.split(LABEL_SEP.strip())]
    else:
        parts = re.split(r"[;,]", value)
    out: list[str] = []
    for part in parts:
        label = part.strip()
        # Google's internal groups start with a star, e.g. "* myContacts".
        if not label or label.startswith("*"):
            continue
        if label not in out:
            out.append(label)
    return out


def _plan_columns(header: list[str]) -> tuple[list, list[str]]:
    """Decide where each column goes, and report the ones not understood."""
    plan: list = []
    unmapped: list[str] = []

    for raw in header:
        key = _norm(raw)
        if not key:
            plan.append(None)
            continue

        match = NUMBERED.match(key)
        if match:
            kind, index, part = match.group(1), int(match.group(2)), match.group(3).strip()
            plan.append(("num", kind, index, part))
            continue

        if key in SINGLE_FIELDS:
            plan.append(("field", SINGLE_FIELDS[key]))
        elif key in FULL_NAME_FIELDS:
            plan.append(("fullname",))
        elif key in LABEL_FIELDS:
            plan.append(("labels",))
        elif key in PHONE_FIELDS:
            plan.append(("phone", PHONE_FIELDS[key]))
        elif key in EMAIL_FIELDS:
            plan.append(("email", EMAIL_FIELDS[key]))
        else:
            plan.append(None)
            if raw.strip():
                unmapped.append(raw.strip())

    return plan, unmapped


def _apply_full_name(contact: Contact, full: str) -> None:
    """Split a whole name into first, middle and last."""
    parts = full.split()
    if not parts:
        return
    contact.given_name = parts[0]
    if len(parts) > 1:
        contact.family_name = parts[-1]
    if len(parts) > 2:
        contact.middle_name = " ".join(parts[1:-1])


def _finish_numbered(contact: Contact, groups: dict) -> None:
    """Turn the gathered numbered columns into values on the contact."""
    for index in sorted(groups.get("phone", {})):
        item = groups["phone"][index]
        value = textutil.clean_phone(item.get("value", ""))
        if value:
            contact.phones.append(Entry(value=value, label=item.get("label", "").strip()))

    for index in sorted(groups.get("email", {})):
        item = groups["email"][index]
        value = textutil.clean_email(item.get("value", ""))
        if value:
            contact.emails.append(Entry(value=value, label=item.get("label", "").strip()))

    for index in sorted(groups.get("address", {})):
        item = groups["address"][index]
        formatted = item.get("formatted", "").strip()
        if not formatted:
            pieces = [
                item.get(part, "").strip()
                for part in ("street", "city", "region", "postal code", "country")
            ]
            formatted = ", ".join(p for p in pieces if p)
        if formatted and not contact.address:
            contact.address = formatted

    for index in sorted(groups.get("website", {})):
        value = groups["website"][index].get("value", "").strip()
        if value and not contact.website:
            contact.website = value

    for index in sorted(groups.get("organization", {})):
        item = groups["organization"][index]
        if not contact.organization:
            contact.organization = item.get("name", "").strip()
        if not contact.job_title:
            contact.job_title = item.get("title", "").strip()
        if not contact.department:
            contact.department = item.get("department", "").strip()


def parse_text(text: str) -> tuple[list[Contact], list[str]]:
    """Parse CSV text, returning (contacts, unrecognized columns)."""
    if not text.strip():
        return [], []

    delimiter = _sniff_delimiter(text)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return [], []

    plan, unmapped = _plan_columns(rows[0])
    contacts: list[Contact] = []

    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue

        contact = Contact()
        groups: dict[str, dict[int, dict[str, str]]] = {}
        full_name = ""

        for index, rule in enumerate(plan):
            if rule is None or index >= len(row):
                continue
            value = (row[index] or "").strip()
            if not value:
                continue

            kind = rule[0]
            if kind == "field":
                setattr(contact, rule[1], value)
            elif kind == "fullname":
                full_name = value
            elif kind == "labels":
                for label in _split_labels(value):
                    if label not in contact.labels:
                        contact.labels.append(label)
            elif kind == "phone":
                cleaned = textutil.clean_phone(value)
                if cleaned:
                    contact.phones.append(Entry(value=cleaned, label=rule[1]))
            elif kind == "email":
                cleaned = textutil.clean_email(value)
                if cleaned:
                    contact.emails.append(Entry(value=cleaned, label=rule[1]))
            elif kind == "num":
                _, group, number, part = rule
                slot = groups.setdefault(group, {}).setdefault(number, {})
                # Type and Label both describe what the value is.
                slot["label" if part in ("label", "type") else part] = value

        _finish_numbered(contact, groups)

        if not contact.full_name and full_name:
            _apply_full_name(contact, full_name)

        if not contact.is_blank():
            contacts.append(contact)

    return contacts, unmapped


def read_file(path: Path | str) -> tuple[list[Contact], list[str]]:
    """Read a CSV file from disk in whatever encoding it uses."""
    data = Path(path).read_bytes()
    return parse_text(textutil.decode_bytes(data))


# ---------------------------------------------------------------- writing


BASE_HEADERS = [
    "First Name", "Middle Name", "Last Name", "Name Prefix", "Name Suffix",
    "Nickname", "Organization Name", "Organization Title",
    "Organization Department", "Birthday", "Notes", "Labels",
]


def build_header(max_phones: int, max_emails: int, has_address: bool,
                 has_website: bool) -> list[str]:
    """Build the heading row using Google's own column names."""
    header = list(BASE_HEADERS)
    for i in range(1, max_emails + 1):
        header += [f"E-mail {i} - Label", f"E-mail {i} - Value"]
    for i in range(1, max_phones + 1):
        header += [f"Phone {i} - Label", f"Phone {i} - Value"]
    if has_address:
        header += ["Address 1 - Label", "Address 1 - Formatted"]
    if has_website:
        header += ["Website 1 - Label", "Website 1 - Value"]
    return header


def _row_for(contact: Contact, max_phones: int, max_emails: int,
             has_address: bool, has_website: bool) -> list[str]:
    labels = contact.labels
    label_cell = LABEL_SEP.join(["* myContacts"] + labels) if labels else "* myContacts"

    row = [
        contact.given_name, contact.middle_name, contact.family_name,
        contact.prefix, contact.suffix, contact.nickname,
        contact.organization, contact.job_title, contact.department,
        contact.birthday, contact.notes, label_cell,
    ]

    for i in range(max_emails):
        entry = contact.emails[i] if i < len(contact.emails) else Entry()
        row += [entry.label or ("Home" if entry.value else ""), entry.value]

    for i in range(max_phones):
        entry = contact.phones[i] if i < len(contact.phones) else Entry()
        row += [entry.label or ("Mobile" if entry.value else ""), entry.value]

    if has_address:
        row += ["Home" if contact.address else "", contact.address]
    if has_website:
        row += ["Profile" if contact.website else "", contact.website]

    return row


def write_file(path: Path | str, contacts: list[Contact]) -> int:
    """Write a CSV file in Google's shape; returns how many were written.

    Encoded as UTF-8 with a byte order mark so Excel opens Arabic
    correctly; Google accepts the mark without complaint.
    """
    max_phones = max((len(c.phones) for c in contacts), default=0) or 1
    max_emails = max((len(c.emails) for c in contacts), default=0) or 1
    has_address = any(c.address for c in contacts)
    has_website = any(c.website for c in contacts)

    header = build_header(max_phones, max_emails, has_address, has_website)

    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for contact in contacts:
            writer.writerow(
                _row_for(contact, max_phones, max_emails, has_address, has_website)
            )

    return len(contacts)
