# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""vCard reading and writing tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _harness import check, finish, setup  # noqa: E402

setup()

import quopri
from app.models import Contact, Entry
from app import vcf_io

def qp(text):
    return quopri.encodestring(text.encode("utf-8")).decode("ascii")


# ---------- 1: vCard 2.1 with quoted-printable Arabic, as phones export it
name = "محمد أحمد"
org = "مدرسة النيل الثانوية"
v21 = (
    "BEGIN:VCARD\r\n"
    "VERSION:2.1\r\n"
    "N;CHARSET=UTF-8;ENCODING=QUOTED-PRINTABLE:" + qp("أحمد") + ";" + qp("محمد") + ";;;\r\n"
    "FN;CHARSET=UTF-8;ENCODING=QUOTED-PRINTABLE:" + qp(name) + "\r\n"
    "ORG;CHARSET=UTF-8;ENCODING=QUOTED-PRINTABLE:" + qp(org) + "\r\n"
    "TEL;CELL:+20 100 123 4567\r\n"
    "TEL;HOME;VOICE:0223456789\r\n"
    "EMAIL;INTERNET;HOME:mohamed@example.com\r\n"
    "END:VCARD\r\n"
)
people = vcf_io.parse_text(v21)
check("2.1: one contact was read", len(people) == 1, str(len(people)))
c = people[0]
check("2.1: the Arabic first name is intact", c.given_name == "محمد", repr(c.given_name))
check("2.1: the Arabic last name is intact", c.family_name == "أحمد", repr(c.family_name))
check("2.1: the organization is intact", c.organization == org, repr(c.organization))
check("2.1: both numbers were read", len(c.phones) == 2, str([p.value for p in c.phones]))
check("2.1: the mobile type is recognized", c.phones[0].label == "Mobile", c.phones[0].label)
check("2.1: the home type is recognized", c.phones[1].label == "Home", c.phones[1].label)
check("2.1: the email address is read", c.primary_email == "mohamed@example.com", c.primary_email)

# ---------- 2: folded lines, and quoted-printable across two lines
long_note = "ملاحظة طويلة جداً عن الطالب وحالته الدراسية والاجتماعية وكل التفاصيل المهمة"
folded = (
    "BEGIN:VCARD\r\n"
    "VERSION:3.0\r\n"
    "FN:طالب مطوي\r\n"
    "NOTE:" + long_note[:20] + "\r\n " + long_note[20:] + "\r\n"
    "END:VCARD\r\n"
)
p2 = vcf_io.parse_text(folded)
check("folding: the note comes back whole", p2[0].notes == long_note, repr(p2[0].notes[:40]))

# ---------- 3: a full round trip
original = Contact(
    given_name="سارة", family_name="عبد الرحمن", middle_name="محمود",
    phones=[Entry("01112223334", "Mobile"), Entry("0233445566", "Work")],
    emails=[Entry("sara@example.com", "Work")],
    organization="مدرسة النيل", job_title="الصف الثالث الثانوي",
    notes="ملاحظة فيها فاصلة، وفاصلة منقوطة؛ وسطر\nجديد",
    labels=["طلاب 2026", "الصف الثالث"],
    address="١٢ شارع الجمهورية، القاهرة",
    birthday="2008-05-14",
)
text = vcf_io.to_vcard(original)
back = vcf_io.parse_text(text)[0]
check("round trip: first name", back.given_name == original.given_name, back.given_name)
check("round trip: middle name", back.middle_name == original.middle_name, back.middle_name)
check("round trip: last name", back.family_name == original.family_name, back.family_name)
check("round trip: phone numbers", [p.value for p in back.phones] == [p.value for p in original.phones])
check("round trip: phone types", [p.label for p in back.phones] == ["Mobile", "Work"],
      str([p.label for p in back.phones]))
check("round trip: organization", back.organization == original.organization, back.organization)
check("round trip: job title", back.job_title == original.job_title, back.job_title)
check("round trip: notes with commas and line breaks", back.notes == original.notes, repr(back.notes))
check("round trip: groups", back.labels == original.labels, str(back.labels))
check("round trip: date of birth", back.birthday == original.birthday, back.birthday)
check("round trip: the identifier is stable", back.uid == original.uid)

# confirm the folding happened and no line exceeds 75 bytes
too_long = [ln for ln in text.split("\r\n") if len(ln.encode("utf-8")) > 75]
check("every line is under 75 bytes", not too_long, str(too_long[:1]))

# ---------- 4: a file in the older Arabic Windows encoding
cp = "BEGIN:VCARD\r\nVERSION:2.1\r\nFN:خالد سعيد\r\nTEL:0100000000\r\nEND:VCARD\r\n"
decoded = vcf_io.decode_bytes(cp.encode("cp1256"))
p4 = vcf_io.parse_text(decoded)
check("cp1256: the name decodes correctly", p4[0].display_name == "خالد سعيد", p4[0].display_name)

# ---------- 5: a file holding several cards in a row
multi = vcf_io.to_vcard(original) + v21
p5 = vcf_io.parse_text(multi)
check("a file with several cards reads both", len(p5) == 2, str(len(p5)))

sys.exit(finish("vCard tests"))
