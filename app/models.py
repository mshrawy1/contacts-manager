# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""The contact model.

This is the intermediate form that every supported file format converts
to and from, so importing and exporting never has to translate CSV
directly into vCard and lose fields on the way.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from . import i18n, textutil


@dataclass
class Entry:
    """A value with a type, such as a mobile number or a work e-mail."""

    value: str = ""
    label: str = ""

    def is_empty(self) -> bool:
        return not self.value.strip()


def _entries_from(raw) -> list[Entry]:
    """Turn stored data back into Entry objects."""
    out: list[Entry] = []
    for item in raw or []:
        if isinstance(item, Entry):
            out.append(item)
        elif isinstance(item, dict):
            out.append(Entry(value=item.get("value", ""), label=item.get("label", "")))
        elif isinstance(item, str):
            out.append(Entry(value=item))
    return [e for e in out if not e.is_empty()]


def display_label(name: str) -> str:
    """A name fit to show the user, with a placeholder when it is empty.

    The placeholder is applied here rather than inside `display_name` so
    that the stored copy of the name stays language-neutral: switching
    the interface language must not leave translated placeholder text
    frozen in the database.
    """
    return name or i18n.t("(no name)")


@dataclass
class Contact:
    """One contact and everything known about them."""

    local_id: int | None = None
    uid: str = ""
    prefix: str = ""
    given_name: str = ""
    middle_name: str = ""
    family_name: str = ""
    suffix: str = ""
    nickname: str = ""
    phones: list[Entry] = field(default_factory=list)
    emails: list[Entry] = field(default_factory=list)
    organization: str = ""
    job_title: str = ""
    department: str = ""
    address: str = ""
    website: str = ""
    birthday: str = ""
    notes: str = ""
    labels: list[str] = field(default_factory=list)
    created_at: float = 0.0
    updated_at: float = 0.0

    def __post_init__(self) -> None:
        self.phones = _entries_from(self.phones)
        self.emails = _entries_from(self.emails)
        self.labels = [str(x).strip() for x in (self.labels or []) if str(x).strip()]
        if not self.uid:
            self.uid = str(uuid.uuid4())
        now = time.time()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    @property
    def full_name(self) -> str:
        """The name as written, with no substitutes."""
        parts = [self.given_name, self.middle_name, self.family_name]
        return " ".join(p.strip() for p in parts if p and p.strip()).strip()

    @property
    def display_name(self) -> str:
        """The best available name, or an empty string if there is none."""
        for candidate in (
            self.full_name,
            self.nickname.strip(),
            self.organization.strip(),
            self.primary_phone,
            self.primary_email,
        ):
            if candidate:
                return candidate
        return ""

    @property
    def primary_phone(self) -> str:
        return self.phones[0].value if self.phones else ""

    @property
    def primary_email(self) -> str:
        return self.emails[0].value if self.emails else ""

    @property
    def sort_key(self) -> str:
        """Alphabetical sort key, normalised so Arabic sorts correctly."""
        return textutil.normalize_text(self.display_name)

    def phone_keys(self) -> set[str]:
        """Comparison keys for every number, used to detect duplicates."""
        return {k for k in (textutil.phone_key(p.value) for p in self.phones) if k}

    def email_keys(self) -> set[str]:
        return {k for k in (textutil.clean_email(e.value) for e in self.emails) if k}

    def name_key(self) -> str:
        return textutil.normalize_text(self.full_name)

    def search_blob(self) -> str:
        """Every searchable value, normalised and joined into one string.

        Normalised phone keys are deliberately left out: the search looks
        those up in the indexed `phone_keys` table instead, so repeating
        them here only lengthened the text and cost time on every save.
        """
        parts = [
            self.full_name,
            self.nickname,
            self.organization,
            self.job_title,
            self.department,
            self.address,
            self.website,
            self.notes,
            " ".join(self.labels),
            " ".join(p.value for p in self.phones),
            " ".join(e.value for e in self.emails),
        ]
        return textutil.normalize_text(" ".join(p for p in parts if p))

    def is_blank(self) -> bool:
        """A wholly empty contact, which import throws away."""
        return not any(
            [
                self.full_name.strip(),
                self.nickname.strip(),
                self.organization.strip(),
                self.phones,
                self.emails,
                self.notes.strip(),
            ]
        )

    def to_dict(self) -> dict:
        """Convert to a plain dictionary ready to be stored as JSON.

        Written out by hand rather than using `dataclasses.asdict`, which
        makes a nested deep copy and costs noticeable time when importing
        thousands of contacts at once.
        """
        return {
            "local_id": self.local_id,
            "uid": self.uid,
            "prefix": self.prefix,
            "given_name": self.given_name,
            "middle_name": self.middle_name,
            "family_name": self.family_name,
            "suffix": self.suffix,
            "nickname": self.nickname,
            "phones": [{"value": p.value, "label": p.label} for p in self.phones],
            "emails": [{"value": e.value, "label": e.label} for e in self.emails],
            "organization": self.organization,
            "job_title": self.job_title,
            "department": self.department,
            "address": self.address,
            "website": self.website,
            "birthday": self.birthday,
            "notes": self.notes,
            "labels": list(self.labels),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Contact":
        allowed = set(cls.__dataclass_fields__)
        clean = {k: v for k, v in (data or {}).items() if k in allowed}
        return cls(**clean)

    def copy(self) -> "Contact":
        return Contact.from_dict(self.to_dict())

    # Field names returned by merge_from. These are identifiers for the
    # caller to count and inspect, not text shown to the user.
    _MERGE_TEXT_FIELDS = (
        "prefix", "given_name", "middle_name", "family_name", "suffix",
        "nickname", "organization", "job_title", "department", "address",
        "website", "birthday",
    )

    def merge_from(self, other: "Contact") -> list[str]:
        """Fill in blank fields from another contact, erasing nothing.

        Returns the names of the fields that changed, so the caller can
        tell whether the merge actually did anything.
        """
        changed: list[str] = []

        for attr in self._MERGE_TEXT_FIELDS:
            mine = (getattr(self, attr) or "").strip()
            theirs = (getattr(other, attr) or "").strip()
            if not mine and theirs:
                setattr(self, attr, theirs)
                changed.append(attr)

        existing_phone_keys = self.phone_keys()
        for entry in other.phones:
            key = textutil.phone_key(entry.value)
            if key and key not in existing_phone_keys:
                self.phones.append(Entry(value=entry.value, label=entry.label))
                existing_phone_keys.add(key)
                changed.append("phones")

        existing_email_keys = self.email_keys()
        for entry in other.emails:
            key = textutil.clean_email(entry.value)
            if key and key not in existing_email_keys:
                self.emails.append(Entry(value=entry.value, label=entry.label))
                existing_email_keys.add(key)
                changed.append("emails")

        their_notes = (other.notes or "").strip()
        if their_notes and their_notes not in (self.notes or ""):
            if self.notes:
                self.notes = (self.notes + "\n" + their_notes).strip()
            else:
                self.notes = their_notes
            changed.append("notes")

        for label in other.labels:
            if label not in self.labels:
                self.labels.append(label)
                changed.append("labels")

        if changed:
            self.updated_at = time.time()
        return changed
