# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""CSV reading and writing tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _harness import check, finish, setup  # noqa: E402

setup()

import tempfile
from pathlib import Path
from app import csv_io
from app.models import Contact, Entry

# ---------- 1: the newer Google format
google_new = (
    "First Name,Middle Name,Last Name,Nickname,Organization Name,Organization Title,"
    "Birthday,Notes,Labels,E-mail 1 - Label,E-mail 1 - Value,Phone 1 - Label,"
    "Phone 1 - Value,Phone 2 - Label,Phone 2 - Value\n"
    "محمد,علي,حسن,حمادة,مدرسة النيل,الصف الثاني,2009-03-01,طالب متفوق,"
    "* myContacts ::: طلاب 2026,Home,m@ex.com,Mobile,01001234567,Home,0223334444\n"
)
people, unmapped = csv_io.parse_text(google_new)
check("new Google format: row count", len(people) == 1, len(people))
c = people[0]
check("new Google format: whole name", c.full_name == "محمد علي حسن", c.full_name)
check("new Google format: nickname", c.nickname == "حمادة", c.nickname)
check("new Google format: organization", c.organization == "مدرسة النيل", c.organization)
check("new Google format: class", c.job_title == "الصف الثاني", c.job_title)
check("new Google format: two numbers", len(c.phones) == 2, [p.value for p in c.phones])
check("new Google format: first number type", c.phones[0].label == "Mobile", c.phones[0].label)
check("new Google format: group without the star entry", c.labels == ["طلاب 2026"], c.labels)
check("new Google format: no unknown columns", unmapped == [], unmapped)

# ---------- 2: the older Google format
google_old = (
    "Name,Given Name,Family Name,Group Membership,E-mail 1 - Type,E-mail 1 - Value,"
    "Phone 1 - Type,Phone 1 - Value\n"
    "سارة أحمد,سارة,أحمد,* myContacts ::: أصدقاء,Home,s@ex.com,Mobile,01119998888\n"
)
p2, _ = csv_io.parse_text(google_old)
check("old Google format: name", p2[0].full_name == "سارة أحمد", p2[0].full_name)
check("old Google format: group", p2[0].labels == ["أصدقاء"], p2[0].labels)
check("old Google format: number", p2[0].primary_phone == "01119998888", p2[0].primary_phone)

# ---------- 3: the Outlook format
outlook = (
    "First Name,Last Name,Company,Job Title,E-mail Address,Mobile Phone,"
    "Business Phone,Notes\n"
    "خالد,سعيد,شركة النور,مدير,k@ex.com,01005556666,0227778888,ملاحظة\n"
)
p3, _ = csv_io.parse_text(outlook)
check("Outlook: organization", p3[0].organization == "شركة النور", p3[0].organization)
check("Outlook: job title", p3[0].job_title == "مدير", p3[0].job_title)
check("Outlook: mobile number", p3[0].phones[0].label == "Mobile", p3[0].phones[0].label)
check("Outlook: work number", p3[0].phones[1].label == "Work", p3[0].phones[1].label)

# ---------- 4: a plain Arabic file written by the user
simple_ar = (
    "الاسم,الموبايل,البريد,المجموعة,ملاحظات\n"
    "أحمد محمود سيد,٠١٠٠١٢٣٤٥٦٧,a@ex.com,طلاب 2026,ممتاز\n"
    "منى,01112223333,,طلاب 2026,\n"
)
p4, un4 = csv_io.parse_text(simple_ar)
check("plain Arabic file: two rows", len(p4) == 2, len(p4))
check("plain Arabic file: name split, first", p4[0].given_name == "أحمد", p4[0].given_name)
check("plain Arabic file: name split, middle", p4[0].middle_name == "محمود", p4[0].middle_name)
check("plain Arabic file: name split, last", p4[0].family_name == "سيد", p4[0].family_name)
check("plain Arabic file: Arabic digits converted", p4[0].primary_phone == "01001234567", p4[0].primary_phone)
check("plain Arabic file: group", p4[0].labels == ["طلاب 2026"], p4[0].labels)
check("plain Arabic file: a single-word name", p4[1].given_name == "منى" and not p4[1].family_name, p4[1].given_name)
check("plain Arabic file: no unknown columns", un4 == [], un4)

# ---------- 5: semicolon as the separator, as Arabic Excel writes it
semi = "الاسم;الموبايل\nعمر فاروق;01234567890\n"
p5, _ = csv_io.parse_text(semi)
check("semicolon separator is handled", p5[0].given_name == "عمر", p5[0].given_name)

# ---------- 6: a round trip through a file on disk
originals = [
    Contact(given_name="ليلى", family_name="مصطفى",
            phones=[Entry("01001112222", "Mobile"), Entry("0223334444", "Home")],
            emails=[Entry("layla@ex.com", "Home")],
            organization="مدرسة النيل", job_title="الصف الأول",
            notes="ملاحظة فيها فاصلة، وكلام تاني",
            labels=["طلاب 2026", "متفوقين"],
            address="١٢ شارع الجمهورية", birthday="2010-01-05"),
    Contact(given_name="يوسف", family_name="إبراهيم",
            phones=[Entry("01115556666", "Mobile")]),
]
tmp = Path(tempfile.gettempdir()) / "t_contacts.csv"
count = csv_io.write_file(tmp, originals)
check("writing: the count returned", count == 2, count)

back, un6 = csv_io.read_file(tmp)
check("reading back: the count", len(back) == 2, len(back))
check("reading back: no unknown columns", un6 == [], un6)
b0 = back[0]
check("reading back: the name", b0.full_name == "ليلى مصطفى", b0.full_name)
check("reading back: the numbers", [p.value for p in b0.phones] == ["01001112222", "0223334444"],
      [p.value for p in b0.phones])
check("reading back: the number types", [p.label for p in b0.phones] == ["Mobile", "Home"],
      [p.label for p in b0.phones])
check("reading back: a note containing a comma", b0.notes == "ملاحظة فيها فاصلة، وكلام تاني", b0.notes)
check("reading back: the groups", b0.labels == ["طلاب 2026", "متفوقين"], b0.labels)
check("reading back: the address", b0.address == "١٢ شارع الجمهورية", b0.address)
check("reading back: the date of birth", b0.birthday == "2010-01-05", b0.birthday)
check("reading back: the second contact with one number", back[1].primary_phone == "01115556666", back[1].primary_phone)

raw = tmp.read_bytes()
check("the file carries a byte order mark for Excel", raw.startswith(b"\xef\xbb\xbf"))
check("the file carries the Labels column", b"Labels" in raw)
tmp.unlink()

sys.exit(finish("CSV tests"))
