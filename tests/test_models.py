# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Model and text-normalization tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _harness import check, finish, setup  # noqa: E402

setup()

from app import textutil  # noqa: E402
from app.models import Contact, Entry, display_label  # noqa: E402

# ---------- normalizing Arabic text
check("diacritics are ignored", textutil.normalize_text("محمّد") == textutil.normalize_text("محمد"))
check("the shape of the hamza is ignored", textutil.normalize_text("أحمد") == textutil.normalize_text("احمد"))
check("alef maksura folds to yeh", textutil.normalize_text("يحيى") == textutil.normalize_text("يحيي"))
check("teh marbuta folds to heh", textutil.normalize_text("فاطمة") == textutil.normalize_text("فاطمه"))
check("the kashida is stripped", textutil.normalize_text("محـــمد") == textutil.normalize_text("محمد"))
check("extra spaces collapse", textutil.normalize_text("  محمد   علي ") == "محمد علي")
check("different names stay different",
      textutil.normalize_text("محمد") != textutil.normalize_text("محمود"))

# ---------- normalizing numbers
check("local and international forms match",
      textutil.phone_key("01001234567") == textutil.phone_key("+201001234567"))
check("a number with a leading double zero matches",
      textutil.phone_key("00201001234567") == textutil.phone_key("01001234567"))
check("Arabic-Indic digits match", textutil.phone_key("٠١٠٠١٢٣٤٥٦٧") == textutil.phone_key("01001234567"))
check("spaces and dashes are ignored", textutil.phone_key("0100 123 4567") == textutil.phone_key("0100-123-4567"))
check("different numbers stay different",
      textutil.phone_key("01001234567") != textutil.phone_key("01009999999"))
check("a number is tidied for display", textutil.clean_phone("٠١٠٠ ١٢٣ ٤٥٦٧") == "0100 123 4567",
      textutil.clean_phone("٠١٠٠ ١٢٣ ٤٥٦٧"))

# ---------- shape checks
check("a good address is accepted", textutil.is_valid_email("a@b.com"))
check("a bad address is rejected", not textutil.is_valid_email("bad@"))
check("an address with no dot is rejected", not textutil.is_valid_email("a@b"))
check("a plausible number is accepted", textutil.is_valid_phone("01001234567"))
check("too short a number is rejected", not textutil.is_valid_phone("123"))

# ---------- the displayed name
check("the whole name reads correctly", Contact(given_name="محمد", family_name="أحمد").display_name == "محمد أحمد")
check("falls back to the organization when unnamed",
      Contact(organization="مدرسة النيل").display_name == "مدرسة النيل")
check("falls back to the number when nothing else",
      Contact(phones=[Entry("01001234567")]).display_name == "01001234567")
check("a nameless contact returns an empty string", Contact(notes="حاجة").display_name == "")
check("the placeholder is applied only when displaying",
      display_label(Contact(notes="حاجة").display_name) == "(no name)",
      display_label(Contact(notes="حاجة").display_name))
check("an empty contact is detected as empty", Contact().is_blank())
check("a contact with a number is not empty", not Contact(phones=[Entry("01001234567")]).is_blank())

# ---------- merging
target = Contact(given_name="محمد", family_name="أحمد",
                 phones=[Entry("01001234567", "Mobile")])
source = Contact(given_name="محمد", family_name="أحمد",
                 phones=[Entry("+201001234567"), Entry("01119998888", "Home")],
                 emails=[Entry("m@ex.com")], organization="مدرسة النيل",
                 notes="ملاحظة جديدة", labels=["طلاب"])
changed = target.merge_from(source)

check("merge: a duplicate number is not added again", len(target.phones) == 2,
      [p.value for p in target.phones])
check("merge: a new number is added", target.phones[1].value == "01119998888")
check("merge: the address is added", target.primary_email == "m@ex.com")
check("merge: the organization is filled in", target.organization == "مدرسة النيل")
check("merge: the note is carried over", target.notes == "ملاحظة جديدة")
check("merge: the group is carried over", target.labels == ["طلاب"])
check("merge: the changed fields are reported", len(changed) > 0, changed)

# merging never overwrites what is already there
keeper = Contact(given_name="سارة", organization="المدرسة القديمة", notes="ملاحظتي")
keeper.merge_from(Contact(given_name="سارة", organization="مدرسة تانية", notes="ملاحظتي"))
check("merge: an existing organization is not replaced", keeper.organization == "المدرسة القديمة",
      keeper.organization)
check("merge: an identical note is not repeated", keeper.notes == "ملاحظتي", keeper.notes)

# merging the same source twice changes nothing
again = target.merge_from(source)
check("merging twice changes nothing the second time", again == [], again)

# ---------- saving and reloading
original = Contact(given_name="ليلى", phones=[Entry("01001112222", "Mobile")],
                   labels=["أ", "ب"])
restored = Contact.from_dict(original.to_dict())
check("round trip: the name survives", restored.display_name == original.display_name)
check("round trip: the identifier survives", restored.uid == original.uid)
check("round trip: the number type survives", restored.phones[0].label == "Mobile")
check("round trip: the groups survive", restored.labels == ["أ", "ب"])
check("a copy is independent of the original", original.copy() is not original)

# ---------- the search text
searchable = Contact(given_name="محمد", organization="مدرسة النيل",
                     phones=[Entry("01001234567")]).search_blob()
check("the search text holds the name", "محمد" in searchable)
check("the search text holds the organization", "النيل" in searchable)
check("the search text holds the number itself", "01001234567" in searchable)

sys.exit(finish("Model tests"))
