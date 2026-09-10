# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Unified import and export across every supported format.

This module answers one question per incoming contact: is this person
already in the database? The answer is decided on phone number and
email address only, never on the name, because names like "Mohamed
Ahmed" belong to many different people — merging on a name match would
silently fuse unrelated records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import csv_io, vcf_io
from .i18n import t
from .models import Contact, display_label
from .store import Store

# How to handle a contact that already exists.
MODE_MERGE = "merge"      # fill in what is missing (the default)
MODE_ADD_ALL = "add_all"  # add everything, duplicates included
MODE_SKIP = "skip"        # leave the existing record untouched

CSV_SUFFIXES = {".csv", ".txt", ".tsv"}
VCF_SUFFIXES = {".vcf", ".vcard"}


@dataclass
class ImportReport:
    """The summary shown to the user after an import finishes."""

    total_read: int = 0
    added: int = 0
    merged: int = 0
    skipped: int = 0
    unmapped_columns: list[str] = field(default_factory=list)
    name_conflicts: list[str] = field(default_factory=list)
    backup_path: str = ""

    def summary(self) -> str:
        """A line-by-line summary, written so a screen reader can read it."""
        lines = [
            t("Read from the file: {count} contacts.", count=self.total_read),
            t("Added as new: {count}.", count=self.added),
            t("Merged into existing: {count}.", count=self.merged),
            t("Skipped: {count}.", count=self.skipped),
        ]

        if self.name_conflicts:
            lines.append("")
            lines.append(
                t(
                    "Note: {count} of these names already existed with different "
                    "phone numbers. They were added as separate contacts so that "
                    "different people are not merged by mistake. The names are:",
                    count=len(self.name_conflicts),
                )
            )
            for name in self.name_conflicts[:15]:
                lines.append(f"  - {name}")
            if len(self.name_conflicts) > 15:
                lines.append(
                    "  " + t("... and {count} more.", count=len(self.name_conflicts) - 15)
                )

        if self.unmapped_columns:
            lines.append("")
            lines.append(t("Columns in the file that were not recognized and ignored:"))
            lines.append("  " + ", ".join(self.unmapped_columns))

        if self.backup_path:
            lines.append("")
            lines.append(t("A backup was saved before importing: {path}",
                           path=self.backup_path))

        return "\n".join(lines)


def read_file(path: Path | str) -> tuple[list[Contact], list[str]]:
    """Read any supported file, returning (contacts, unrecognized columns)."""
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix in CSV_SUFFIXES:
        return csv_io.read_file(path)
    if suffix in VCF_SUFFIXES:
        return vcf_io.read_file(path), []

    raise ValueError(
        t(
            "File type '{suffix}' is not supported. The program reads .csv "
            "and .vcf files only.",
            suffix=suffix or t("no extension"),
        )
    )


def import_into(
    store: Store,
    incoming: list[Contact],
    mode: str = MODE_MERGE,
    unmapped: list[str] | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> ImportReport:
    """Bring contacts into the database using the chosen mode.

    A backup is taken first, and the whole run happens inside one
    transaction so a failure halfway through cannot leave the data in a
    partly-imported state.
    """
    report = ImportReport(
        total_read=len(incoming),
        unmapped_columns=list(unmapped or []),
    )

    backup = store.backup()
    if backup:
        report.backup_path = str(backup)

    total = len(incoming)
    try:
        for index, contact in enumerate(incoming, start=1):
            if contact.is_blank():
                report.skipped += 1
            else:
                _import_one(store, contact, mode, report)
            if progress:
                progress(index, total)
        store.conn.commit()
    except Exception:
        store.conn.rollback()
        raise

    return report


def _import_one(store: Store, contact: Contact, mode: str, report: ImportReport) -> None:
    """Handle a single contact coming in from a file."""
    if mode == MODE_ADD_ALL:
        store.add(contact, commit=False)
        report.added += 1
        return

    # Confirmed matches only: same phone number or same email address.
    matches = store.find_strong_matches(contact)

    if not matches:
        # No confirmed match. Check for someone with the same name so the
        # user can be told, but still add this as a separate contact: a
        # name on its own proves nothing.
        if store.find_name_matches(contact):
            name = display_label(contact.display_name)
            if name not in report.name_conflicts:
                report.name_conflicts.append(name)
        store.add(contact, commit=False)
        report.added += 1
        return

    if mode == MODE_SKIP:
        report.skipped += 1
        return

    target = matches[0]
    if target.merge_from(contact):
        store.update(target, commit=False)
        report.merged += 1
    else:
        report.skipped += 1


def export_file(path: Path | str, contacts: list[Contact]) -> int:
    """Write contacts to a file chosen by its extension; returns the count."""
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix in CSV_SUFFIXES:
        return csv_io.write_file(path, contacts)
    if suffix in VCF_SUFFIXES:
        return vcf_io.write_file(path, contacts)

    raise ValueError(
        t(
            "File type '{suffix}' is not supported for export. Choose .csv "
            "or .vcf.",
            suffix=suffix or t("no extension"),
        )
    )
