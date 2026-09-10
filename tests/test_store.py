# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Database and import tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _harness import check, finish, setup  # noqa: E402

setup()

import tempfile
from pathlib import Path
from app import importer
from app.models import Contact, Entry
from app.store import Store

db = Path(tempfile.gettempdir()) / "t_store_test.db"
for leftover in db.parent.glob("t_store_test.db*"):
    leftover.unlink(missing_ok=True)

store = Store(db)

# ---------- adding and reading
a = store.add(Contact(given_name="محمد", family_name="أحمد",
                      phones=[Entry("01001234567", "Mobile")],
                      organization="مدرسة النيل", labels=["طلاب 2026"]))
b = store.add(Contact(given_name="سارة", family_name="علي",
                      phones=[Entry("01119998888", "Mobile")],
                      emails=[Entry("sara@ex.com")]))
check("adding: the count", store.count() == 2, store.count())
check("adding: a local id was issued", a.local_id is not None and b.local_id is not None)

# ---------- searching
check("search by name", len(store.search("محمد")) == 1, len(store.search("محمد")))
check("search by a name spelled with a different hamza", len(store.search("احمد")) == 1)
check("search by organization", len(store.search("النيل")) == 1)
check("search by a number in another format", len(store.search("+20 100 123 4567")) == 1,
      len(store.search("+20 100 123 4567")))
check("search by Arabic-Indic digits", len(store.search("٠١٠٠١٢٣٤٥٦٧")) == 1)
check("search by two words", len(store.search("محمد النيل")) == 1)
check("search for something absent", len(store.search("زغلول")) == 0)

# ---------- confirmed matches versus name look-alikes
same_phone = Contact(given_name="محمد", family_name="أحمد",
                     phones=[Entry("+201001234567")], emails=[Entry("m@ex.com")])
check("a confirmed match on the number", len(store.find_strong_matches(same_phone)) == 1)

same_name_only = Contact(given_name="محمد", family_name="أحمد",
                         phones=[Entry("01277776666")])
check("no confirmed match on the name alone", len(store.find_strong_matches(same_name_only)) == 0)
check("a weak match on the name is reported", len(store.find_name_matches(same_name_only)) == 1)

# ---------- import: merging on the number
report = importer.import_into(store, [same_phone], mode=importer.MODE_MERGE)
check("import: merged rather than added", report.merged == 1 and report.added == 0,
      f"merged={report.merged} added={report.added}")
check("import: the total did not grow", store.count() == 2, store.count())
merged = store.get(a.local_id)
check("import: the address was added to the existing one", merged.primary_email == "m@ex.com", merged.primary_email)
check("import: the number was not duplicated", len(merged.phones) == 1, [p.value for p in merged.phones])

# ---------- import: same name with a different number is another person
report2 = importer.import_into(store, [same_name_only], mode=importer.MODE_MERGE)
check("same name, different number: added separately", report2.added == 1 and report2.merged == 0,
      f"added={report2.added} merged={report2.merged}")
check("same name: a warning was recorded", len(report2.name_conflicts) == 1, report2.name_conflicts)
check("same name: the total is now three", store.count() == 3, store.count())

# ---------- import: a duplicate inside one file
batch = [
    Contact(given_name="ليلى", phones=[Entry("01005550000")]),
    Contact(given_name="ليلى", family_name="مصطفى", phones=[Entry("+201005550000")]),
]
report3 = importer.import_into(store, batch, mode=importer.MODE_MERGE)
check("duplicate within one file: one added, one merged",
      report3.added == 1 and report3.merged == 1,
      f"added={report3.added} merged={report3.merged}")
layla = store.search("ليلى")
check("duplicate within one file: only one contact remains", len(layla) == 1, len(layla))
check("duplicate within one file: the last name was filled in", layla[0].family_name == "مصطفى",
      layla[0].family_name)

# ---------- skip mode
report4 = importer.import_into(store, [Contact(given_name="أي حد", phones=[Entry("01005550000")])],
                               mode=importer.MODE_SKIP)
check("skip mode leaves the existing record alone", report4.skipped == 1 and report4.added == 0, report4.skipped)

# ---------- groups
check("the list of groups", store.all_labels() == ["طلاب 2026"], store.all_labels())
check("filtering by group", len(store.by_label("طلاب 2026")) == 1)

# ---------- groups are things in their own right ----------
check("a label typed into a contact becomes a group",
      "طلاب 2026" in store.all_labels(), store.all_labels())

check("an empty group can be made", store.create_group("خريجون"))
check("the empty group is listed", "خريجون" in store.all_labels(), store.all_labels())
check("it has no members yet", store.label_counts()["خريجون"] == 0,
      store.label_counts()["خريجون"])
check("the same name cannot be made twice", not store.create_group("خريجون"))
check("a blank name is refused", not store.create_group("   "))

counts = store.label_counts()
check("members are counted", counts["طلاب 2026"] == 1, counts["طلاب 2026"])

# renaming reaches the contacts as well as the list
moved = store.rename_group("طلاب 2026", "طلاب الثانوية")
check("renaming reports how many contacts changed", moved == 1, moved)
check("the old name is gone", "طلاب 2026" not in store.all_labels())
check("the new name is there", "طلاب الثانوية" in store.all_labels())
renamed = store.by_label("طلاب الثانوية")
check("the contact carries the new name", len(renamed) == 1, len(renamed))
check("the stored copy was rewritten too",
      renamed[0].labels == ["طلاب الثانوية"], renamed[0].labels)
check("searching finds the new name", len(store.search("الثانوية")) >= 1)

# a group outlives its last contact
solo = store.add(Contact(given_name="وحيد", phones=[Entry("01500000001")],
                         labels=["مجموعة مؤقتة"]))
check("the new group appeared", "مجموعة مؤقتة" in store.all_labels())
store.delete(solo.local_id)
check("the group survives losing its last member",
      "مجموعة مؤقتة" in store.all_labels(), store.all_labels())
check("but it now has no members", store.label_counts()["مجموعة مؤقتة"] == 0)

# deleting a group leaves the contacts alone
before_contacts = store.count()
removed = store.delete_group("طلاب الثانوية")
check("deleting reports how many contacts were touched", removed == 1, removed)
check("the group is gone", "طلاب الثانوية" not in store.all_labels())
check("the contacts are still there", store.count() == before_contacts, store.count())
check("the label was taken off the contact",
      all("طلاب الثانوية" not in c.labels for c in store.all()))

store.delete_group("خريجون")
store.delete_group("مجموعة مؤقتة")

# The contact deleted above is still sitting in the bin; clear it so the
# checks that follow start from a known state.
store.empty_trash()

# ---------- deleted items
before = store.count()
store.delete(b.local_id)
check("deleting: the total went down", store.count() == before - 1, store.count())
check("deleting: it went to deleted items", len(store.trash_items()) == 1)
trash_id = store.trash_items()[0][0]
restored = store.restore(trash_id)
check("restoring: it came back", store.count() == before, store.count())
check("restoring: with the same name", restored.display_name == "سارة علي", restored.display_name)
check("restoring: deleted items is empty again", len(store.trash_items()) == 0)

# ---------- duplicate detection
store.add(Contact(given_name="نسخة", phones=[Entry("01001234567")]))
groups = store.duplicate_groups()
check("duplicates are detected by number", len(groups) == 1 and len(groups[0]) == 2,
      [[c.display_name for c in g] for g in groups])

# ---------- backups
backup = store.backup()
check("a backup was created", backup is not None and Path(backup).exists(), backup)

store.close()
for leftover in db.parent.glob("t_store_test.db*"):
    leftover.unlink(missing_ok=True)

sys.exit(finish("Database and import tests"))
