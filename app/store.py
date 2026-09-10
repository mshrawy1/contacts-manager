# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Local storage in a SQLite database.

Each contact is stored whole as JSON so new fields can be added later
without changing the table shape. Alongside it, a normalised copy of the
name, phone and e-mail is kept in separate columns, which is what makes
searching, sorting and duplicate detection fast.

A note on speed: the table in the window needs six strings per row, not
the whole object. So there are two ways to read:

* `list_rows` reads the ready-made columns straight from SQL without
  unpacking any JSON. This is what the window uses for listing and
  searching, and it stays fast with tens of thousands of records.
* `all` and `get` build the full object, and are called only when
  editing or exporting.
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from . import config, textutil
from .models import Contact

# Raised whenever the table shape changes, so upgrades run by themselves.
SCHEMA_VERSION = 3

SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts (
    local_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    uid           TEXT    NOT NULL UNIQUE,
    data          TEXT    NOT NULL,
    display_name  TEXT    NOT NULL DEFAULT '',
    sort_key      TEXT    NOT NULL DEFAULT '',
    search_blob   TEXT    NOT NULL DEFAULT '',
    primary_phone TEXT    NOT NULL DEFAULT '',
    primary_email TEXT    NOT NULL DEFAULT '',
    organization  TEXT    NOT NULL DEFAULT '',
    job_title     TEXT    NOT NULL DEFAULT '',
    labels_text   TEXT    NOT NULL DEFAULT '',
    created_at    REAL    NOT NULL DEFAULT 0,
    updated_at    REAL    NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_contacts_sort   ON contacts(sort_key);
CREATE INDEX IF NOT EXISTS idx_contacts_search ON contacts(search_blob);

CREATE TABLE IF NOT EXISTS phone_keys (
    local_id INTEGER NOT NULL,
    key      TEXT    NOT NULL,
    PRIMARY KEY (local_id, key)
);
CREATE INDEX IF NOT EXISTS idx_phone_key ON phone_keys(key);

CREATE TABLE IF NOT EXISTS email_keys (
    local_id INTEGER NOT NULL,
    key      TEXT    NOT NULL,
    PRIMARY KEY (local_id, key)
);
CREATE INDEX IF NOT EXISTS idx_email_key ON email_keys(key);

CREATE TABLE IF NOT EXISTS contact_labels (
    local_id INTEGER NOT NULL,
    label    TEXT    NOT NULL,
    PRIMARY KEY (local_id, label)
);
CREATE INDEX IF NOT EXISTS idx_contact_label ON contact_labels(label);

CREATE TABLE IF NOT EXISTS groups (
    name       TEXT PRIMARY KEY,
    created_at REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS trash (
    trash_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    data       TEXT NOT NULL,
    deleted_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

# The columns the window's table needs, in order.
ROW_COLUMNS = (
    "local_id, uid, display_name, primary_phone, primary_email, "
    "organization, job_title, labels_text"
)


class ContactRow(NamedTuple):
    """A lightweight row for the table: only the strings on screen.

    Used instead of the full object so that listing and searching never
    unpack JSON per contact. When the user opens one for editing, the
    full object is fetched with `store.get`.

    The field order here must stay identical to `ROW_COLUMNS`, because
    rows are built straight from SQL with `_make`, which is the fastest
    route available.
    """

    local_id: int
    uid: str
    display_name: str
    primary_phone: str
    primary_email: str
    organization: str
    job_title: str
    labels_text: str


class Store:
    """Every database operation goes through here."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else config.DB_FILE
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode = WAL")
        # Safe enough for a desktop program, and much faster to write.
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        self._migrate()

    # ---------- upgrading ----------

    def _migrate(self) -> None:
        """Bring an older database up to date without losing anything."""
        version = int(self.get_meta("schema_version", "0") or 0)
        if version >= SCHEMA_VERSION:
            return

        existing = {
            row["name"] for row in self.conn.execute("PRAGMA table_info(contacts)")
        }
        for column in ("job_title", "labels_text"):
            if column not in existing:
                self.conn.execute(
                    f"ALTER TABLE contacts ADD COLUMN {column} TEXT NOT NULL DEFAULT ''"
                )

        # Rebuild the derived columns and tables from the stored JSON.
        rows = self.conn.execute("SELECT local_id, data FROM contacts").fetchall()
        for row in rows:
            contact = Contact.from_dict(json.loads(row["data"]))
            self.conn.execute(
                "UPDATE contacts SET job_title = ?, labels_text = ? WHERE local_id = ?",
                (contact.job_title, ", ".join(contact.labels), row["local_id"]),
            )
            self.conn.executemany(
                "INSERT OR IGNORE INTO contact_labels (local_id, label) VALUES (?, ?)",
                [(row["local_id"], label) for label in contact.labels],
            )

        # Groups used to exist only as text inside contacts, so they
        # vanished when the last contact using one was deleted. Register
        # every label already in use as a group in its own right.
        self.conn.execute(
            "INSERT OR IGNORE INTO groups (name, created_at) "
            "SELECT DISTINCT label, ? FROM contact_labels",
            (time.time(),),
        )

        self.conn.commit()
        self.set_meta("schema_version", str(SCHEMA_VERSION))

    # ---------- connection ----------

    def close(self) -> None:
        try:
            self.conn.commit()
        finally:
            self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---------- internals ----------

    @staticmethod
    def _row_to_contact(row: sqlite3.Row) -> Contact:
        contact = Contact.from_dict(json.loads(row["data"]))
        contact.local_id = row["local_id"]
        return contact

    def _write_derived(self, local_id: int, contact: Contact,
                       clear_first: bool = True) -> None:
        """Refresh the key and group tables belonging to one contact.

        On insert there are no old rows to clear, and skipping those
        deletes saves noticeable time on a large import.
        """
        if clear_first:
            self.conn.execute("DELETE FROM phone_keys     WHERE local_id = ?", (local_id,))
            self.conn.execute("DELETE FROM email_keys     WHERE local_id = ?", (local_id,))
            self.conn.execute("DELETE FROM contact_labels WHERE local_id = ?", (local_id,))

        self.conn.executemany(
            "INSERT OR IGNORE INTO phone_keys (local_id, key) VALUES (?, ?)",
            [(local_id, k) for k in contact.phone_keys()],
        )
        self.conn.executemany(
            "INSERT OR IGNORE INTO email_keys (local_id, key) VALUES (?, ?)",
            [(local_id, k) for k in contact.email_keys()],
        )
        self.conn.executemany(
            "INSERT OR IGNORE INTO contact_labels (local_id, label) VALUES (?, ?)",
            [(local_id, label) for label in contact.labels],
        )
        # A label typed into a contact becomes a group in its own right,
        # so it stays available for filtering even after that contact is
        # deleted. Removing one for good is done from the groups screen.
        now = time.time()
        self.conn.executemany(
            "INSERT OR IGNORE INTO groups (name, created_at) VALUES (?, ?)",
            [(label, now) for label in contact.labels],
        )

    @staticmethod
    def _columns(contact: Contact) -> tuple:
        return (
            contact.uid,
            json.dumps(contact.to_dict(), ensure_ascii=False),
            contact.display_name,
            contact.sort_key,
            contact.search_blob(),
            contact.primary_phone,
            contact.primary_email,
            contact.organization,
            contact.job_title,
            ", ".join(contact.labels),
            contact.created_at,
            contact.updated_at,
        )

    # ---------- adding and editing ----------

    def add(self, contact: Contact, commit: bool = True) -> Contact:
        """Add a new contact and return it with its local id filled in."""
        cur = self.conn.execute(
            """INSERT INTO contacts
                 (uid, data, display_name, sort_key, search_blob,
                  primary_phone, primary_email, organization, job_title,
                  labels_text, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            self._columns(contact),
        )
        contact.local_id = int(cur.lastrowid)
        self._write_derived(contact.local_id, contact, clear_first=False)
        if commit:
            self.conn.commit()
        return contact

    def add_many(self, contacts: list[Contact]) -> list[Contact]:
        """Add a batch in one transaction, far quicker than one at a time."""
        added: list[Contact] = []
        for contact in contacts:
            added.append(self.add(contact, commit=False))
        self.conn.commit()
        return added

    def update(self, contact: Contact, commit: bool = True) -> Contact:
        """Save changes to a contact that already exists."""
        if contact.local_id is None:
            raise ValueError("cannot update a contact that has no local id")
        contact.updated_at = time.time()
        self.conn.execute(
            """UPDATE contacts SET
                 uid = ?, data = ?, display_name = ?, sort_key = ?, search_blob = ?,
                 primary_phone = ?, primary_email = ?, organization = ?,
                 job_title = ?, labels_text = ?, created_at = ?, updated_at = ?
               WHERE local_id = ?""",
            self._columns(contact) + (contact.local_id,),
        )
        self._write_derived(contact.local_id, contact, clear_first=True)
        if commit:
            self.conn.commit()
        return contact

    def save(self, contact: Contact) -> Contact:
        """Add or update depending on whether a local id is present."""
        if contact.local_id is None:
            return self.add(contact)
        return self.update(contact)

    # ---------- deleting and restoring ----------

    def delete(self, local_id: int, commit: bool = True) -> None:
        """Move a contact to deleted items rather than erasing it."""
        row = self.conn.execute(
            "SELECT data FROM contacts WHERE local_id = ?", (local_id,)
        ).fetchone()
        if row is None:
            return
        self.conn.execute(
            "INSERT INTO trash (data, deleted_at) VALUES (?, ?)",
            (row["data"], time.time()),
        )
        self.conn.execute("DELETE FROM contacts       WHERE local_id = ?", (local_id,))
        self.conn.execute("DELETE FROM phone_keys     WHERE local_id = ?", (local_id,))
        self.conn.execute("DELETE FROM email_keys     WHERE local_id = ?", (local_id,))
        self.conn.execute("DELETE FROM contact_labels WHERE local_id = ?", (local_id,))
        if commit:
            self.conn.commit()

    def delete_many(self, local_ids: list[int]) -> int:
        for local_id in local_ids:
            self.delete(local_id, commit=False)
        self.conn.commit()
        return len(local_ids)

    def trash_items(self) -> list[tuple[int, Contact, float]]:
        """What is in deleted items, most recent first."""
        rows = self.conn.execute(
            "SELECT trash_id, data, deleted_at FROM trash ORDER BY deleted_at DESC"
        ).fetchall()
        out = []
        for row in rows:
            contact = Contact.from_dict(json.loads(row["data"]))
            contact.local_id = None
            out.append((row["trash_id"], contact, row["deleted_at"]))
        return out

    def restore(self, trash_id: int) -> Contact | None:
        """Bring a contact back out of deleted items."""
        row = self.conn.execute(
            "SELECT data FROM trash WHERE trash_id = ?", (trash_id,)
        ).fetchone()
        if row is None:
            return None
        data = json.loads(row["data"])
        data["local_id"] = None
        # If that uid has been taken in the meantime, issue a fresh one.
        if data.get("uid") and self.get_by_uid(data["uid"]) is not None:
            data["uid"] = ""
        contact = Contact.from_dict(data)
        self.add(contact, commit=False)
        self.conn.execute("DELETE FROM trash WHERE trash_id = ?", (trash_id,))
        self.conn.commit()
        return contact

    def empty_trash(self) -> int:
        cur = self.conn.execute("DELETE FROM trash")
        self.conn.commit()
        return cur.rowcount

    # ---------- reading ----------

    def count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0])

    def get(self, local_id: int) -> Contact | None:
        row = self.conn.execute(
            "SELECT * FROM contacts WHERE local_id = ?", (local_id,)
        ).fetchone()
        return self._row_to_contact(row) if row else None

    def get_many(self, local_ids: list[int]) -> list[Contact]:
        """Fetch a set of full contacts in display order."""
        if not local_ids:
            return []
        marks = ",".join("?" for _ in local_ids)
        rows = self.conn.execute(
            f"SELECT * FROM contacts WHERE local_id IN ({marks}) "
            "ORDER BY sort_key, local_id",
            list(local_ids),
        ).fetchall()
        return [self._row_to_contact(r) for r in rows]

    def get_by_uid(self, uid: str) -> Contact | None:
        row = self.conn.execute("SELECT * FROM contacts WHERE uid = ?", (uid,)).fetchone()
        return self._row_to_contact(row) if row else None

    def all(self) -> list[Contact]:
        """Every contact as a full object, for export and bulk work."""
        rows = self.conn.execute(
            "SELECT * FROM contacts ORDER BY sort_key, local_id"
        ).fetchall()
        return [self._row_to_contact(r) for r in rows]

    # ---------- searching ----------

    def _search_where(self, query: str) -> tuple[str, list[str]]:
        """Build the search condition shared by both read paths."""
        terms = [t for t in textutil.normalize_text(query).split(" ") if t]
        if not terms:
            return "", []

        params: list[str] = [f"%{t}%" for t in terms]
        where = " AND ".join("search_blob LIKE ?" for _ in terms)

        # If the query looks like a number, also match the normalised key.
        key = textutil.phone_key(query)
        if key:
            where = (
                f"({where}) OR local_id IN "
                "(SELECT local_id FROM phone_keys WHERE key LIKE ?)"
            )
            params.append(f"%{key}%")

        return where, params

    def list_rows(self, query: str = "", label: str = "") -> list[ContactRow]:
        """The fast path: display rows straight from SQL, no JSON unpacked."""
        clauses: list[str] = []
        params: list[str] = []

        where, search_params = self._search_where(query or "")
        if where:
            clauses.append(f"({where})")
            params.extend(search_params)

        if label:
            clauses.append(
                "local_id IN (SELECT local_id FROM contact_labels WHERE label = ?)"
            )
            params.append(label)

        sql = f"SELECT {ROW_COLUMNS} FROM contacts"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY sort_key, local_id"

        # A cursor with plain tuples rather than sqlite3.Row: quicker to
        # build, and the column order is guaranteed to match ContactRow.
        cursor = self.conn.cursor()
        cursor.row_factory = None
        rows = cursor.execute(sql, params).fetchall()
        return list(map(ContactRow._make, rows))

    def search(self, query: str, limit: int | None = None) -> list[Contact]:
        """Search returning full objects, for export and for tests."""
        query = (query or "").strip()
        if not query:
            return self.all()

        where, params = self._search_where(query)
        if not where:
            return self.all()

        sql = f"SELECT * FROM contacts WHERE {where} ORDER BY sort_key, local_id"
        if limit:
            sql += f" LIMIT {int(limit)}"
        rows = self.conn.execute(sql, params).fetchall()
        return [self._row_to_contact(r) for r in rows]

    # ---------- groups ----------

    def all_labels(self) -> list[str]:
        """Every known group, sorted, whether or not anyone is in it."""
        names = {row["name"] for row in self.conn.execute("SELECT name FROM groups")}
        names |= {
            row["label"]
            for row in self.conn.execute("SELECT DISTINCT label FROM contact_labels")
        }
        return sorted(names, key=textutil.normalize_text)

    def label_counts(self) -> dict[str, int]:
        """How many contacts are in each group, including the empty ones."""
        counts = {name: 0 for name in self.all_labels()}
        for row in self.conn.execute(
            "SELECT label, COUNT(*) AS total FROM contact_labels GROUP BY label"
        ):
            counts[row["label"]] = row["total"]
        return counts

    def create_group(self, name: str) -> bool:
        """Add an empty group. Returns False if the name is already taken."""
        name = (name or "").strip()
        if not name:
            return False
        if name in self.all_labels():
            return False
        self.conn.execute(
            "INSERT OR IGNORE INTO groups (name, created_at) VALUES (?, ?)",
            (name, time.time()),
        )
        self.conn.commit()
        return True

    def rename_group(self, old: str, new: str) -> int:
        """Rename a group everywhere; returns how many contacts changed.

        The name lives in three places — the groups table, the lookup
        table, and the stored copy of each contact — so every one of them
        has to be rewritten together.
        """
        old, new = (old or "").strip(), (new or "").strip()
        if not old or not new or old == new:
            return 0

        affected = self.by_label(old)
        for contact in affected:
            renamed: list[str] = []
            for label in contact.labels:
                candidate = new if label == old else label
                if candidate not in renamed:
                    renamed.append(candidate)
            contact.labels = renamed
            self.update(contact, commit=False)

        self.conn.execute("DELETE FROM groups WHERE name = ?", (old,))
        self.conn.execute(
            "INSERT OR IGNORE INTO groups (name, created_at) VALUES (?, ?)",
            (new, time.time()),
        )
        self.conn.commit()
        return len(affected)

    def delete_group(self, name: str) -> int:
        """Remove a group and take it off every contact. Contacts survive."""
        name = (name or "").strip()
        if not name:
            return 0

        affected = self.by_label(name)
        for contact in affected:
            contact.labels = [label for label in contact.labels if label != name]
            self.update(contact, commit=False)

        self.conn.execute("DELETE FROM groups WHERE name = ?", (name,))
        self.conn.commit()
        return len(affected)

    def by_label(self, label: str) -> list[Contact]:
        rows = self.conn.execute(
            "SELECT * FROM contacts WHERE local_id IN "
            "(SELECT local_id FROM contact_labels WHERE label = ?) "
            "ORDER BY sort_key, local_id",
            (label,),
        ).fetchall()
        return [self._row_to_contact(r) for r in rows]

    # ---------- duplicate detection ----------

    def find_strong_matches(
        self, contact: Contact, ignore_id: int | None = None
    ) -> list[Contact]:
        """Confirmed matches: same phone number or same e-mail address.

        This is the only kind of match automatic merging acts on, because
        a number or an address belongs to exactly one person.
        """
        ids: set[int] = set()

        for key in contact.phone_keys():
            for row in self.conn.execute(
                "SELECT local_id FROM phone_keys WHERE key = ?", (key,)
            ):
                ids.add(row["local_id"])

        for key in contact.email_keys():
            for row in self.conn.execute(
                "SELECT local_id FROM email_keys WHERE key = ?", (key,)
            ):
                ids.add(row["local_id"])

        return self._ids_to_contacts(ids, ignore_id)

    def find_name_matches(
        self, contact: Contact, ignore_id: int | None = None
    ) -> list[Contact]:
        """A match on the full name alone.

        This is weak evidence and no proof of being the same person:
        names like "Mohamed Ahmed" recur across wholly different people,
        especially in a list of students. So the program shows this kind
        of match to the user and never merges on it by itself.
        """
        name = contact.name_key()
        if not name:
            return []
        ids = {
            row["local_id"]
            for row in self.conn.execute(
                "SELECT local_id FROM contacts WHERE sort_key = ?", (name,)
            )
        }
        return self._ids_to_contacts(ids, ignore_id)

    def find_matches(self, contact: Contact, ignore_id: int | None = None) -> list[Contact]:
        """Every match, confirmed and weak, for showing to the user."""
        strong = self.find_strong_matches(contact, ignore_id)
        seen = {c.local_id for c in strong}
        weak = [c for c in self.find_name_matches(contact, ignore_id)
                if c.local_id not in seen]
        return strong + weak

    def _ids_to_contacts(
        self, ids: set[int], ignore_id: int | None = None
    ) -> list[Contact]:
        ids = set(ids)
        ids.discard(ignore_id)
        return self.get_many(sorted(ids))

    def duplicate_groups(self, include_names: bool = False) -> list[list[Contact]]:
        """Gather look-alikes into groups of two or more.

        By default contacts are grouped on phone number and e-mail only.
        With `include_names` on, people sharing an identical name join in
        too — and the user then has to review the result carefully before
        merging anything.

        Keys come straight from the indexed tables, and no contact is
        loaded in full unless it actually landed in a group.
        """
        parent: dict[int, int] = {}

        def find(node: int) -> int:
            parent.setdefault(node, node)
            while parent[node] != node:
                parent[node] = parent[parent[node]]
                node = parent[node]
            return node

        def union(a: int, b: int) -> None:
            root_a, root_b = find(a), find(b)
            if root_a != root_b:
                parent[max(root_a, root_b)] = min(root_a, root_b)

        # Any key shared by more than one contact links them together.
        queries = [
            "SELECT key, local_id FROM phone_keys ORDER BY key",
            "SELECT key, local_id FROM email_keys ORDER BY key",
        ]
        if include_names:
            queries.append(
                "SELECT sort_key AS key, local_id FROM contacts "
                "WHERE sort_key <> '' ORDER BY sort_key"
            )

        involved: set[int] = set()
        for sql in queries:
            previous_key = None
            first_id = None
            for row in self.conn.execute(sql):
                key, local_id = row["key"], row["local_id"]
                find(local_id)
                if key == previous_key:
                    union(first_id, local_id)
                    involved.add(first_id)
                    involved.add(local_id)
                else:
                    previous_key, first_id = key, local_id

        if not involved:
            return []

        # Load full objects only for those that ended up in a group.
        contacts = {c.local_id: c for c in self.get_many(sorted(involved))}
        groups: dict[int, list[Contact]] = {}
        for local_id in sorted(involved):
            contact = contacts.get(local_id)
            if contact is not None:
                groups.setdefault(find(local_id), []).append(contact)
        return [g for g in groups.values() if len(g) > 1]

    # ---------- database metadata ----------
    #
    # The meta table describes the database itself — currently only the
    # schema version, which has to travel with the file so that a
    # contacts database copied to another machine is upgraded correctly.
    # Program settings do not belong here; they live in settings.json.

    def get_meta(self, key: str, default: str = "") -> str:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
        self.conn.commit()

    def clear_meta(self, key: str) -> None:
        """Remove an entry, used when a setting moves out to its own file."""
        self.conn.execute("DELETE FROM meta WHERE key = ?", (key,))
        self.conn.commit()

    # ---------- backups ----------

    def backup(self) -> Path | None:
        """Take a copy of the database before any large operation."""
        if not self.path.exists() or self.count() == 0:
            return None
        self.conn.commit()
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = config.backup_dir() / f"contacts-{stamp}.db"
        dest = sqlite3.connect(str(target))
        try:
            self.conn.backup(dest)
        finally:
            dest.close()
        self._prune_backups()
        return target

    @staticmethod
    def _prune_backups() -> None:
        """Keep the newest few copies and delete the rest."""
        files = sorted(
            config.backup_dir().glob("contacts-*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old in files[config.MAX_BACKUPS:]:
            try:
                old.unlink()
            except OSError:
                pass
