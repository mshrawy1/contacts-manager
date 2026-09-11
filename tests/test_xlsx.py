# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Spreadsheet tests: reading .xlsx, repairing numbers, building contacts.

The sample workbooks in tests/samples were written by Excel itself, not
by this program, and that is the point of them. A file this program
generated would only ever prove that it agrees with itself; what breaks a
reader is what Excel actually does -- storing text in a shared table,
storing a date as a number, dropping the cells of an empty column, and
turning 01001234567 into 1001234567 the moment the cell is not formatted
as text.

They are checked in rather than generated, so the suite runs on a machine
with no Excel on it. tests/make_samples.ps1 rebuilds them.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _harness import ROOT, check, finish, setup  # noqa: E402

setup()

from app import phones, xlsx_import, xlsx_io  # noqa: E402

SAMPLES = ROOT / "tests" / "samples"
EG = phones.get("EG")

# ---------- the files are all there ----------
for name in ("school_roster.xlsx", "phone_formats.xlsx", "multi_sheet.xlsx",
             "edge_cases.xlsx", "national_ids.xlsx"):
    check(f"sample {name} exists", (SAMPLES / name).exists())

# ---------- recognising a workbook ----------
check("an .xlsx is recognised",
      xlsx_io.looks_like_workbook(SAMPLES / "school_roster.xlsx"))
check("a file that is not a workbook is refused",
      not xlsx_io.looks_like_workbook(ROOT / "main.py"))
check("a missing file is refused, not raised",
      not xlsx_io.looks_like_workbook(SAMPLES / "nothing_here.xlsx"))

# ---------- sheets, in the order of their tabs ----------
names = xlsx_io.sheet_names(SAMPLES / "multi_sheet.xlsx")
check("every tab is listed", len(names) == 3, names)
check("tabs keep the order they appear in",
      names == ["تعليمات", "جهات الاتصال", "إحصائيات"], names)

by_name = xlsx_io.read_sheet(SAMPLES / "multi_sheet.xlsx", "جهات الاتصال")
by_index = xlsx_io.read_sheet(SAMPLES / "multi_sheet.xlsx", 1)
check("a tab can be read by name", by_name.rows[0][0] == "الاسم الأول",
      by_name.rows[0][:2])
check("reading by name and by position agree", by_name.rows == by_index.rows)

# ---------- Arabic survives the round trip ----------
roster = xlsx_io.read_sheet(SAMPLES / "school_roster.xlsx")
check("Arabic text is read intact", roster.rows[4][1] == "أحمد محمود سيد",
      roster.rows[4][1])
check("the tab name is Arabic too", roster.name == "الكشف", roster.name)

# ---------- the letterhead above the real headings ----------
check("a merged title row is read", "مدرسة النيل" in roster.rows[0][0],
      roster.rows[0][0])
check("the blank spacer row stays blank",
      not any(c.strip() for c in roster.rows[2]), roster.rows[2])

# ---------- cells are placed by their own reference ----------
# Only one cell on this row has anything in it, and it belongs in G.
check("a lone cell lands in its own column",
      roster.rows[6][6] == "ولي الأمر يفضل التواصل مساءً", roster.rows[6])
check("the columns before it stay empty", roster.rows[6][5] == "القاهرة - مدينة نصر")

# ---------- what Excel does to a number formatted as a number ----------
check("a numeric cell really has lost its leading zero",
      roster.rows[4][3] == "1001234567", roster.rows[4][3])
check("a numeric cell is not read as a float",
      "." not in roster.rows[4][3] and "e" not in roster.rows[4][3].lower())

formats = xlsx_io.read_sheet(SAMPLES / "phone_formats.xlsx")
check("a text-formatted number keeps its zero",
      formats.rows[1][1] == "01001234567", formats.rows[1][1])
check("an international number is kept as written",
      formats.rows[1][3] == "+201001234567", formats.rows[1][3])
check("Arabic-Indic digits are kept as written",
      formats.rows[1][4] == "٠١٠٠١٢٣٤٥٦٧", formats.rows[1][4])

# ---------- dates, formulas, booleans and errors ----------
edge = xlsx_io.read_sheet(SAMPLES / "edge_cases.xlsx")
check("a date is read as a date, not Excel's day count",
      edge.rows[1][1] == "2008-05-14", edge.rows[1][1])
check("a date in another display format still reads correctly",
      edge.rows[3][1] == "1999-12-31", edge.rows[3][1])
check("a line break inside a cell is kept", "\n" in edge.rows[1][2], edge.rows[1][2])
check("quotes and commas inside a cell are kept",
      '"علامات اقتباس"' in edge.rows[3][2], edge.rows[3][2])
check("TRUE and FALSE are read", (edge.rows[1][3], edge.rows[3][3]) == ("TRUE", "FALSE"),
      (edge.rows[1][3], edge.rows[3][3]))
check("a formula's result is read", edge.rows[1][4] == "سعاد الشريف", edge.rows[1][4])
check("an error cell reads as empty, not as #N/A", edge.rows[1][5] == "",
      repr(edge.rows[1][5]))
check("a blank row in the middle stays a blank row",
      not any(c.strip() for c in edge.rows[2]), edge.rows[2])

# ---------- the country table ----------
check("Egypt is in the table", EG is not None and EG.dial == "20")
check("an unknown code returns nothing", phones.get("ZZ") is None)
check("an empty code returns nothing", phones.get("") is None)
check("there is always a default", phones.default().code == phones.DEFAULT_CODE)
check("every country has a dial code",
      all(c.dial.isdigit() for c in phones.COUNTRIES))
check("no two countries share a code",
      len({c.code for c in phones.COUNTRIES}) == len(phones.COUNTRIES))
check("the country label carries its dial code",
      "+20" in phones.display_name(EG, False))
check("the label is translated", phones.display_name(EG, True).startswith("مصر"))

# ---------- repairing a number ----------
fixed, note = phones.repair("1001234567", EG)
check("a mobile that lost its zero is repaired", fixed == "01001234567", fixed)
check("the repair is reported", bool(note), note)

fixed, note = phones.repair("223334444", EG)
check("a landline that lost its zero is repaired", fixed == "0223334444", fixed)

for value, why in [
    ("01001234567", "already correct"),
    ("+201001234567", "already international"),
    ("00201001234567", "international with 00"),
    ("+966501234567", "a number from somewhere else"),
    ("12345", "too short for any Egyptian length"),
    ("123456789012", "too long for any Egyptian length"),
]:
    fixed, note = phones.repair(value, EG)
    check(f"untouched: {why}", not note, f"{value} -> {fixed}")

fixed, _ = phones.repair("٠١٠٠١٢٣٤٥٦٧", EG)
check("Arabic-Indic digits are folded", fixed == "01001234567", fixed)

check("no country means no repair", phones.repair("1001234567", None)[1] == "")
kuwait = phones.get("KW")
check("a country with no trunk digit gets no zero",
      phones.repair("22345678", kuwait)[0] == "22345678")

# ---------- international and back ----------
check("the international form is built",
      phones.to_international("01001234567", EG) == "+201001234567",
      phones.to_international("01001234567", EG))
check("00 is turned into +",
      phones.to_international("00201001234567", EG) == "+201001234567")
check("a foreign number keeps its own code",
      phones.to_international("+966501234567", EG) == "+966501234567")
check("the local form comes back",
      phones.to_national("+201001234567", EG) == "01001234567",
      phones.to_national("+201001234567", EG))
check("a foreign number is not shortened to a local one",
      phones.to_national("+966501234567", EG) == "+966501234567")
check("a number names its own country",
      phones.guess_country("+966501234567").code == "SA")
check("a local number names no country", phones.guess_country("01001234567") is None)

# ---------- finding the row of headings ----------
plans = xlsx_import.survey(SAMPLES / "school_roster.xlsx")
plan = plans[xlsx_import.best_sheet(plans)]
check("the header row is found below the letterhead", plan.header_row == 3,
      plan.header_row)
check("the headings are the real ones", plan.headers[1] == "اسم الطالب",
      plan.headers[:3])

multi = xlsx_import.survey(SAMPLES / "multi_sheet.xlsx")
check("the sheet with the contacts is chosen over the instructions",
      multi[xlsx_import.best_sheet(multi)].name == "جهات الاتصال",
      multi[xlsx_import.best_sheet(multi)].name)

# ---------- guessing what the columns hold ----------
check("a counting column is left alone", plan.mapping[0] == xlsx_import.IGNORE)
check("a whole-name column is recognised", plan.mapping[1] == xlsx_import.FULL_NAME)
check("a parent's phone column is recognised", plan.mapping[3] == "phone:Mobile",
      plan.mapping[3])
check("an e-mail column is recognised", plan.mapping[4] == "email:")
check("an address column is recognised", plan.mapping[5] == "address")

check("an unknown heading maps to nothing",
      xlsx_import.field_for_header("عمود لا يعرفه أحد") == xlsx_import.IGNORE)
check("an empty heading maps to nothing", xlsx_import.field_for_header("") ==
      xlsx_import.IGNORE)
check("column letters count past Z",
      [xlsx_import.column_letter(i) for i in (0, 25, 26, 27)]
      == ["A", "Z", "AA", "AB"])

# ---------- building the contacts ----------
contacts, report = xlsx_import.build(plan, EG)
check("every data row became a contact", len(contacts) == 10, len(contacts))
check("the report counts the rows", report.rows_read == 10, report.rows_read)
check("every broken number was repaired", report.phones_repaired == 10,
      report.phones_repaired)

first = contacts[0]
check("the first name is split out", first.given_name == "أحمد", first.given_name)
check("the middle name is split out", first.middle_name == "محمود", first.middle_name)
check("the last name is split out", first.family_name == "سيد", first.family_name)
check("the repaired number is on the contact",
      first.phones[0].value == "01001234567", first.phones[0].value)
check("the number carries its type", first.phones[0].label == "Mobile")
check("the e-mail came across", first.emails[0].value == "parent1@example.com")
check("the class became the job title", first.job_title == "الصف الأول",
      first.job_title)

# ---------- rows that are not contacts ----------
edge_plans = xlsx_import.survey(SAMPLES / "edge_cases.xlsx")
edge_contacts, edge_report = xlsx_import.build(edge_plans[0], EG)
check("a blank row is counted and skipped", edge_report.rows_blank == 1,
      edge_report.rows_blank)
check("a paragraph is not turned into a name",
      all(len(c.given_name) <= xlsx_import.MAX_NAME_LENGTH for c in edge_contacts),
      [len(c.given_name) for c in edge_contacts])
check("a date column becomes the birthday",
      edge_contacts[0].birthday == "2008-05-14", edge_contacts[0].birthday)

# ---------- identity numbers never get in ----------
check("a national ID is recognised", xlsx_import.looks_like_national_id("29805151234567"))
check("a phone number is not mistaken for one",
      not xlsx_import.looks_like_national_id("01001234567"))
check("fourteen digits alone are not enough",
      not xlsx_import.looks_like_national_id("99999999999999"))
check("an impossible month is not an ID",
      not xlsx_import.looks_like_national_id("29913151234567"))
check("the heading is recognised", xlsx_import.is_sensitive_header("الرقم القومي"))
check("the English heading is recognised too",
      xlsx_import.is_sensitive_header("National ID"))

id_plans = xlsx_import.survey(SAMPLES / "national_ids.xlsx")
id_plan = id_plans[0]
check("an identity column is never mapped",
      id_plan.mapping[2] == xlsx_import.IGNORE, id_plan.mapping[2])

id_contacts, id_report = xlsx_import.build(id_plan, EG)
check("the identity column is named in the report",
      id_report.sensitive_columns == ["الرقم القومي"], id_report.sensitive_columns)
check("contacts still came out of the file", len(id_contacts) == 3, len(id_contacts))

SECRETS = ["29805151234567", "30112201234568", "27703101234569",
           "28809091234561", "29001011234562"]


def everything(contact) -> str:
    """Every scrap of text on a contact, for checking nothing leaked."""
    return " ".join([
        contact.given_name, contact.middle_name, contact.family_name,
        contact.nickname, contact.notes, contact.organization,
        contact.job_title, contact.department, contact.address,
        contact.website, contact.birthday, " ".join(contact.labels),
        " ".join(e.value for e in contact.phones),
        " ".join(e.value for e in contact.emails),
    ])


check("no identity number reached a contact",
      not any(s in everything(c) for c in id_contacts for s in SECRETS))

# The stronger test: force the mapping a careless user might make.
id_plan.mapping[2] = "phone:Mobile"
id_plan.mapping[4] = "notes"
forced, forced_report = xlsx_import.build(id_plan, EG)
check("an identity number forced onto a phone field is still refused",
      not any(s in everything(c) for c in forced for s in SECRETS))
check("the refusals are counted", forced_report.ids_blocked == 5,
      forced_report.ids_blocked)
check("ordinary text in the same column still came through",
      any("ملاحظة عادية" in c.notes for c in forced),
      [c.notes for c in forced])

# ---------- a sheet with nothing usable ----------
empty = xlsx_import.SheetPlan(name="empty", rows=[], header_row=-1)
check("an empty sheet is not usable", not empty.is_usable())
check("an empty sheet yields no contacts", xlsx_import.build(empty, EG)[0] == [])
check("finding a header in nothing returns -1", xlsx_import.find_header_row([]) == -1)

# ---------- the exported copy carries country codes ----------
changed = phones.internationalize(contacts, EG)
check("every number was given its country code", changed == 10, changed)
check("the number now carries the code",
      contacts[0].phones[0].value == "+201001234567", contacts[0].phones[0].value)
check("running it twice changes nothing more",
      phones.internationalize(contacts, EG) == 0)

sys.exit(finish("Spreadsheet tests"))
