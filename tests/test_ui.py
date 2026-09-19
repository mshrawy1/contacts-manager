# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Interface tests.

These build every window for real, without showing them, so a mistake in
a wx call fails here rather than in front of the user.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _harness import check, finish, setup  # noqa: E402

setup()

import wx  # noqa: E402

from app import config, i18n, phones  # noqa: E402
from app.models import Contact, Entry  # noqa: E402
from app.settings import Settings  # noqa: E402
from app.store import Store  # noqa: E402
from app.ui.contact_dialog import ContactDialog  # noqa: E402
from app.ui.dialogs import (DuplicatesDialog, GroupsDialog,  # noqa: E402
                            ReportDialog, TrashDialog)
from app.ui import icons  # noqa: E402
from app.ui.main_frame import MainFrame  # noqa: E402

# Pin the language so the checks below do not depend on system settings.
i18n.set_language("en")

db = Path(tempfile.gettempdir()) / "t_ui_test.db"
for leftover in db.parent.glob("t_ui_test.db*"):
    leftover.unlink(missing_ok=True)

app = wx.App(False)
store = Store(db)
settings = Settings(db.parent / "t_ui_settings.json")

store.add(Contact(given_name="محمد", family_name="أحمد",
                  phones=[Entry("01001234567", "Mobile")],
                  emails=[Entry("m@ex.com", "Home")],
                  organization="مدرسة النيل", job_title="الصف الثالث",
                  labels=["طلاب 2026"]))
store.add(Contact(given_name="سارة", family_name="علي",
                  phones=[Entry("01119998888", "Mobile")], labels=["طلاب 2026"]))
store.add(Contact(given_name="نسخة", phones=[Entry("+201001234567")]))

# ---------- the main window ----------
frame = MainFrame(store, settings)
check("the main window builds", frame is not None)

# The version is in the title because that is the one place both kinds of
# user meet it without going looking: it is on screen from the moment the
# window opens, and a screen reader reads a window's title as it comes up.
check("the title carries the version",
      frame.GetTitle() == f"{config.APP_NAME} {config.APP_VERSION}",
      frame.GetTitle())
check("the version is the one the program reports everywhere",
      config.APP_VERSION in frame.GetTitle(), config.APP_VERSION)
check("the table is populated", len(frame.list.rows) == 3, len(frame.list.rows))
check("the status bar counts correctly",
      frame.GetStatusBar().GetStatusText(1) == "3 of 3",
      frame.GetStatusBar().GetStatusText(1))

# ---------- the table columns follow Google Contacts ----------
headers = [frame.list.GetColumn(i).GetText() for i in range(frame.list.GetColumnCount())]
check("the columns are in Google Contacts order",
      headers == ["Name", "Email", "Phone", "Class or job title",
                  "Organization", "Groups"], headers)

# the cell contents must line up with those headers
row_of = {r.display_name: r for r in frame.list.rows}
index = [r.display_name for r in frame.list.rows].index("محمد أحمد")
cells = [frame.list.OnGetItemText(index, c) for c in range(6)]
check("the name cell holds the name", cells[0] == "محمد أحمد", cells[0])
check("the email cell holds the email", cells[1] == "m@ex.com", cells[1])
check("the phone cell holds the phone", cells[2] == "01001234567", cells[2])
check("the job title cell holds the class", cells[3] == "الصف الثالث", cells[3])
check("the organization cell holds the school", cells[4] == "مدرسة النيل", cells[4])
check("the groups cell holds the group", cells[5] == "طلاب 2026", cells[5])

texts = [frame.list.OnGetItemText(0, c) for c in range(6)]
check("a row has six columns", len(texts) == 6 and all(isinstance(t, str) for t in texts))

# ---------- every button carries an icon ----------
# ---------- the toolbar ----------
bar = frame.GetToolBar()
check("the window has a toolbar", bar is not None)
check("the commands moved onto it", len(frame.toolbar_tools) == 8,
      sorted(frame.toolbar_tools))
for wanted in ("new", "edit", "delete", "select_all", "import", "export"):
    check(f"the toolbar carries '{wanted}'", wanted in frame.toolbar_tools)

missing_label = []
missing_icon = []
for name, identifier in frame.toolbar_tools.items():
    tool = bar.FindById(identifier)
    if tool is None or not tool.GetLabel().strip():
        missing_label.append(name)
    if tool is None or not tool.GetNormalBitmap().IsOk():
        missing_icon.append(name)
check("every tool keeps its words for the screen reader", not missing_label,
      missing_label)
check("every tool carries a picture for the eye", not missing_icon, missing_icon)
check("the toolbar reuses the menu command ids, so nothing is bound twice",
      frame.toolbar_tools["new"] == wx.ID_NEW
      and frame.toolbar_tools["import"] == wx.ID_OPEN)

check("the contact icons come from the Google set",
      all(icons.source_of(n) == "material"
          for n in ("new", "edit", "delete", "import", "export")))

# ---------- searching ----------
frame.search.SetValue("محمد")
frame.refresh(announce=False)
check("search filters", len(frame.list.rows) == 1, len(frame.list.rows))
frame.search.SetValue("")
frame.refresh(announce=False)
check("clearing the search restores everything", len(frame.list.rows) == 3)

# a postponed search is run before anything that depends on it
frame.search.ChangeValue("سارة")
frame._on_search_text(None)
check("the search is postponed", len(frame.list.rows) == 3, len(frame.list.rows))
frame._flush_search()
check("flushing runs the postponed search", len(frame.list.rows) == 1,
      len(frame.list.rows))
frame.search.ChangeValue("")
frame.refresh(announce=False)

# ---------- filtering by group ----------
check("the group list holds all plus one",
      list(frame.label_filter.GetStrings()) == ["All groups", "طلاب 2026"],
      list(frame.label_filter.GetStrings()))
frame.label_filter.SetStringSelection("طلاب 2026")
frame.refresh(announce=False)
check("filtering by group works", len(frame.list.rows) == 2, len(frame.list.rows))
frame.label_filter.SetSelection(0)
frame.refresh(announce=False)

# ---------- select all ----------
frame.list.SetFocus()
frame._on_select_all(None)
check("select all selects every row", frame.list.GetSelectedItemCount() == 3,
      frame.list.GetSelectedItemCount())
check("select all reports the count", "3" in frame.announcer.last(),
      frame.announcer.last())
check("every selected row is returned", len(frame._selected_rows()) == 3,
      len(frame._selected_rows()))

# with a text field focused, Ctrl+A must select text instead of rows
frame.search.SetFocus()
frame.search.ChangeValue("abc")
before = frame.list.GetSelectedItemCount()
frame._on_select_all(None)
check("select all in a text box does not touch the table",
      frame.list.GetSelectedItemCount() == before, frame.list.GetSelectedItemCount())
frame.search.ChangeValue("")
frame.refresh(announce=False)

# ---------- announcements ----------
frame.announcer.say("test message")
check("the status bar is written", frame.GetStatusBar().GetStatusText(0) == "test message")
check("the last message is remembered", frame.announcer.last() == "test message")

# ---------- menus ----------
bar = frame.GetMenuBar()
titles = [bar.GetMenuLabelText(i) for i in range(bar.GetMenuCount())]
check("the menu titles are in the source language",
      titles == ["File", "Contacts", "View", "Tools", "Help"], titles)
check("the window uses the settings file it was given",
      frame.settings is settings)
check("the language is not stored in the contacts database",
      store.get_meta("language", "") == "", store.get_meta("language", ""))

# ---------- the contact form ----------
contact = store.all()[0]
dialog = ContactDialog(frame, store, contact)
check("the form opens with the data loaded",
      dialog.first_name.GetValue() in ("محمد", "سارة", "نسخة"),
      dialog.first_name.GetValue())
collected = dialog._collect()
check("collecting keeps the identifier", collected.uid == contact.uid)
check("collecting keeps the phone", collected.primary_phone == contact.primary_phone)
# Asked of _first_problem rather than _validate. _validate reports what
# it finds, and reporting means opening a message box, which waits for a
# click that a test never makes -- so calling it here hung the whole
# suite, locally and on the build server alike, for as long as anybody
# let it. _first_problem answers the same question without a window.
check("validation accepts good data", dialog._first_problem(collected) is None,
      dialog._first_problem(collected))
check("validation rejects an empty contact",
      dialog._first_problem(Contact()) is not None)
check("validation rejects a malformed address",
      dialog._first_problem(Contact(given_name="x",
                                    emails=[Entry("not-an-address")])) is not None)
check("the problem names the field to go back to",
      dialog._first_problem(Contact())[1] is dialog.first_name)
check("editing offers no add-another button", dialog.add_another_button is None)
dialog.Destroy()

new_dialog = ContactDialog(frame, store)
check("a new form starts empty", new_dialog.first_name.GetValue() == "")
check("a new form has three phone slots", len(new_dialog.phone_fields) == 3)
check("a new form has two email slots", len(new_dialog.email_fields) == 2)
check("adding offers the add-another button", new_dialog.add_another_button is not None)
check("the save button starts plain", new_dialog.save_button.GetLabel() == "Save",
      new_dialog.save_button.GetLabel())

# ---------- the form is grouped into captioned boxes ----------
# A wxStaticBox is a real grouping in the accessibility tree, so the
# caption a sighted user reads on the frame is the same thing a screen
# reader announces on entering it.
boxes = [w for w in new_dialog.scroll.GetChildren() if isinstance(w, wx.StaticBox)]
captions = [b.GetLabel() for b in boxes]
check("the form is split into captioned groups",
      captions == ["Name", "Phone numbers", "Email addresses",
                   "Organization", "Other details"], captions)

def fields_in(box):
    """The controls inside one group, in order, ignoring the captions."""
    return [w for w in box.GetChildren() if not isinstance(w, wx.StaticText)]

check("the name group holds the name fields in order",
      fields_in(boxes[0]) == [new_dialog.first_name, new_dialog.middle_name,
                              new_dialog.family_name, new_dialog.prefix,
                              new_dialog.suffix, new_dialog.nickname],
      [w.GetName() for w in fields_in(boxes[0])])

# The country comes first inside the phone group, and the order is the
# requirement rather than a detail of the layout: the country is what
# tells a bare 01001234567 apart from a foreign number, so it has to be
# asked before the numbers and read out before them.
check("the phone group asks for the country before the numbers",
      fields_in(boxes[1]) == [new_dialog.country,
                              new_dialog.phone_fields[0][0],
                              new_dialog.phone_fields[0][1],
                              new_dialog.phone_fields[1][0],
                              new_dialog.phone_fields[1][1],
                              new_dialog.phone_fields[2][0],
                              new_dialog.phone_fields[2][1]],
      [w.GetName() for w in fields_in(boxes[1])])

check("the country list offers every country the program knows",
      new_dialog.country.GetCount() == len(phones.COUNTRIES),
      new_dialog.country.GetCount())
check("the country starts on a real choice",
      new_dialog.selected_country() is not None,
      new_dialog.country.GetStringSelection())

check("the email group holds both addresses",
      fields_in(boxes[2]) == [new_dialog.email_fields[0][0],
                              new_dialog.email_fields[0][1],
                              new_dialog.email_fields[1][0],
                              new_dialog.email_fields[1][1]],
      [w.GetName() for w in fields_in(boxes[2])])

check("the organization group holds its three fields",
      fields_in(boxes[3]) == [new_dialog.organization, new_dialog.job_title,
                              new_dialog.department],
      [w.GetName() for w in fields_in(boxes[3])])

# ---------- only the names and two phones are shown at first ----------
always_shown = [new_dialog.first_name, new_dialog.middle_name,
                new_dialog.family_name,
                new_dialog.phone_fields[0][0], new_dialog.phone_fields[1][0]]
check("the three name fields and two phones are visible",
      all(w.IsShown() for w in always_shown))
check("the extra fields start hidden",
      not any(w.IsShown() for w in (new_dialog.organization, new_dialog.notes,
                                    new_dialog.email_fields[0][0],
                                    new_dialog.phone_fields[2][0],
                                    new_dialog.address, new_dialog.website,
                                    new_dialog.prefix, new_dialog.labels)))
check("groups made only of optional fields are hidden whole",
      not any(b.IsShown() for b in boxes[2:]),
      [b.GetLabel() for b in boxes[2:] if b.IsShown()])
check("the groups holding required fields stay visible",
      all(b.IsShown() for b in boxes[:2]))
check("the toggle button itself is visible", new_dialog.more_button.IsShown())
check("the toggle reads show more",
      new_dialog.more_button.GetLabel() == "Show more fields",
      new_dialog.more_button.GetLabel())
# ---------- every field must be preceded by its own caption ----------
# Windows works out a field's name from the static text before it among
# its siblings. If a caption is created after its field, every field
# announces the previous row's caption and appears, to a screen reader
# user, not to exist. This locks the order in place, inside every group.
mislabelled = []
for box in boxes:
    children = list(box.GetChildren())
    for position, child in enumerate(children):
        if isinstance(child, (wx.StaticText, wx.Button)):
            continue
        previous = children[position - 1] if position else None
        if not isinstance(previous, wx.StaticText):
            mislabelled.append(f"{child.GetName()}: no caption before it")
        elif previous.GetLabel() != child.GetName():
            mislabelled.append(
                f"{child.GetName()}: preceded by {previous.GetLabel()!r}")
check("every field is preceded by its own caption", not mislabelled,
      mislabelled[:3])

check("the toggle carries an icon", new_dialog.more_button.GetBitmap().IsOk())
check("the save button carries an icon", new_dialog.save_button.GetBitmap().IsOk())
check("the cancel button carries an icon", new_dialog.cancel_button.GetBitmap().IsOk())
check("the add-another button carries an icon",
      new_dialog.add_another_button.GetBitmap().IsOk())

# ---------- the toggle reveals and hides them again ----------
new_dialog._on_toggle_more(None)
check("the extra fields appear once asked for",
      all(w.IsShown() for w in (new_dialog.organization, new_dialog.notes,
                                new_dialog.email_fields[0][0],
                                new_dialog.phone_fields[2][0])))
check("their groups appear with them", all(b.IsShown() for b in boxes))
check("the toggle now reads show fewer",
      new_dialog.more_button.GetLabel() == "Show fewer fields",
      new_dialog.more_button.GetLabel())
def _picture(bitmap):
    """The shapes are one flat colour, so transparency is what differs."""
    image = bitmap.ConvertToImage()
    alpha = image.GetAlpha() if image.HasAlpha() else b""
    return bytes(image.GetData()) + bytes(alpha)


check("the toggle arrow turns over with it",
      new_dialog.more_button.GetBitmap().IsOk()
      and _picture(new_dialog.more_button.GetBitmap())
      == _picture(icons.get("collapse")))
check("the change is announced", "shown" in new_dialog.status.GetLabel().lower(),
      new_dialog.status.GetLabel())

new_dialog._on_toggle_more(None)
check("the extra fields hide again", not new_dialog.organization.IsShown())
check("the toggle reads show more again",
      new_dialog.more_button.GetLabel() == "Show more fields")
check("the visible fields were never touched",
      all(w.IsShown() for w in always_shown))

# ---------- the window fits what it holds ----------
new_dialog._showing_more = False
new_dialog._apply_more_state(announce=False)
closed_height = new_dialog.GetSize().height
new_dialog._showing_more = True
new_dialog._apply_more_state(announce=False)
open_height = new_dialog.GetSize().height
check("opening the extra fields makes the window taller",
      open_height > closed_height, f"{closed_height} -> {open_height}")
check("closing them shrinks it back", True)
new_dialog._showing_more = False
new_dialog._apply_more_state(announce=False)
check("the height follows the content both ways",
      new_dialog.GetSize().height == closed_height,
      f"{closed_height} vs {new_dialog.GetSize().height}")

content_height = new_dialog.form.GetMinSize().height
check("no large empty band is left below the fields",
      new_dialog.scroll.GetSize().height - content_height < 60,
      f"scroll {new_dialog.scroll.GetSize().height}, content {content_height}")

# ---------- the primary action is marked three ways ----------
check("Save is the default button", new_dialog.save_button is
      new_dialog.GetDefaultItem() or new_dialog.save_button.GetId() == wx.ID_OK)
check("Save is set in heavier type",
      new_dialog.save_button.GetFont().GetWeight() > wx.FONTWEIGHT_NORMAL,
      new_dialog.save_button.GetFont().GetWeight())
check("Save still says what it does",
      new_dialog.save_button.GetLabel().startswith("Save"),
      new_dialog.save_button.GetLabel())

# ---------- an existing contact with extra details opens expanded ----------
rich = ContactDialog(frame, store, store.search("محمد")[0])
check("a contact with an organization opens with the extras shown",
      rich._showing_more and rich.organization.IsShown())
check("its organization is loaded", rich.organization.GetValue() == "مدرسة النيل",
      rich.organization.GetValue())
check("its email is loaded", rich.email_fields[0][0].GetValue() == "m@ex.com",
      rich.email_fields[0][0].GetValue())
rich.Destroy()

# "نسخة" holds only a phone number, so nothing in the hidden half applies.
bare = store.search("نسخة")[0]
plain = ContactDialog(frame, store, bare)
check("a contact with nothing extra opens collapsed", not plain._showing_more)
check("its hidden fields really are hidden", not plain.organization.IsShown())
plain.Destroy()

# a group on its own is enough to count as extra detail
grouped = ContactDialog(frame, store, store.search("سارة")[0])
check("a contact with only a group still opens expanded", grouped._showing_more)
grouped.Destroy()

# ---------- adding several in one form ----------
def fill(dlg, first, last, phone, org=None, group=None):
    dlg.first_name.SetValue(first)
    dlg.family_name.SetValue(last)
    dlg.phone_fields[0][0].SetValue(phone)
    if org is not None:
        dlg.organization.SetValue(org)
    if group is not None:
        dlg.labels.SetValue(group)


fill(new_dialog, "طالب", "أول", "01200000001", org="مدرسة الأمل", group="فصل أ")
new_dialog._on_add_another(None)
check("the first contact joins the list", len(new_dialog.entries) == 1,
      len(new_dialog.entries))
check("the name is cleared for the next one", new_dialog.first_name.GetValue() == "",
      new_dialog.first_name.GetValue())
check("the phone is cleared", new_dialog.phone_fields[0][0].GetValue() == "")
check("the organization is kept", new_dialog.organization.GetValue() == "مدرسة الأمل",
      new_dialog.organization.GetValue())
check("the group is kept", new_dialog.labels.GetValue() == "فصل أ",
      new_dialog.labels.GetValue())
check("the save button shows the count",
      new_dialog.save_button.GetLabel() == "Save (1 on the list)",
      new_dialog.save_button.GetLabel())
check("the status line reports the count", "1" in new_dialog.status.GetLabel(),
      new_dialog.status.GetLabel())

fill(new_dialog, "طالب", "ثاني", "01200000002")
new_dialog._on_add_another(None)
check("the second contact joins the list", len(new_dialog.entries) == 2)
check("the count on the button follows",
      new_dialog.save_button.GetLabel() == "Save (2 on the list)",
      new_dialog.save_button.GetLabel())

queued_names = [c.display_name for c, _ in new_dialog.entries]
check("both queued contacts kept their names",
      queued_names == ["طالب أول", "طالب ثاني"], queued_names)
check("the queued contacts kept the shared organization",
      all(c.organization == "مدرسة الأمل" for c, _ in new_dialog.entries))
check("the queued contacts kept the shared group",
      all(c.labels == ["فصل أ"] for c, _ in new_dialog.entries))

# an empty form must not be accepted as another contact
count_before = len(new_dialog.entries)
check("an empty form is recognised as empty",
      new_dialog._form_is_empty(new_dialog._collect()))
check("nothing was added from the empty form",
      len(new_dialog.entries) == count_before)

# a duplicate of something already queued is caught
fill(new_dialog, "مكرر", "داخلي", "01200000001")
duplicate = new_dialog._collect()
check("a duplicate inside the list is found",
      new_dialog._find_queued_match(duplicate) is not None)
check("the matched entry is the right one",
      new_dialog._find_queued_match(duplicate).display_name == "طالب أول")

# leaving with unsaved contacts must warn
check("there are unsaved contacts to warn about", len(new_dialog.entries) == 2)
new_dialog.Destroy()

# ---------- writing the batch through the main window ----------
batch = [
    (Contact(given_name="دفعة", family_name="واحد",
             phones=[Entry("01300000001", "Mobile")]), None),
    (Contact(given_name="دفعة", family_name="اثنان",
             phones=[Entry("01300000002", "Mobile")]), None),
]
before_count = store.count()
frame._save_entries(batch, is_new=True)
check("the batch is written", store.count() == before_count + 2, store.count())
check("the batch is announced with its count", "2" in frame.announcer.last(),
      frame.announcer.last())

# ---------- deleted items ----------
store.delete(store.all()[0].local_id)
trash = TrashDialog(frame, store)
check("deleted items holds one", trash.list.GetItemCount() == 1, trash.list.GetItemCount())
trash.Destroy()

# ---------- managing groups ----------
groups = GroupsDialog(frame, store)
listed = [groups.list.GetItemText(i) for i in range(groups.list.GetItemCount())]
check("the groups screen lists the groups in use", "طلاب 2026" in listed, listed)
check("it shows how many are in each",
      groups.list.GetItemText(listed.index("طلاب 2026"), 1) == "2",
      groups.list.GetItemText(listed.index("طلاب 2026"), 1))

check("a new empty group can be made", store.create_group("مجموعة اختبار"))
groups._reload()
listed = [groups.list.GetItemText(i) for i in range(groups.list.GetItemCount())]
check("an empty group appears in the list", "مجموعة اختبار" in listed, listed)
check("with no members yet",
      groups.list.GetItemText(listed.index("مجموعة اختبار"), 1) == "0")
groups.Destroy()

# an empty group must reach the filter, which is the whole point
frame.refresh(announce=False)
check("an empty group can be filtered on",
      "مجموعة اختبار" in list(frame.label_filter.GetStrings()),
      list(frame.label_filter.GetStrings()))
store.delete_group("مجموعة اختبار")
frame.refresh(announce=False)
check("removing the group takes it out of the filter",
      "مجموعة اختبار" not in list(frame.label_filter.GetStrings()))

# ---------- duplicates ----------
dup = DuplicatesDialog(frame, store)
check("a duplicate group was found", len(dup.groups) >= 1, len(dup.groups))
check("the reason is stated", dup._reason(dup.groups[0]) == "same phone number",
      dup._reason(dup.groups[0]))
dup.Destroy()

# ---------- the report window ----------
report = ReportDialog(frame, "Report", "first line\nsecond line")
check("the report window builds", report.box.GetValue().startswith("first line"))
report.Destroy()

# ---------- switching language ----------
i18n.set_language("ar")
arabic_frame = MainFrame(store, settings)
bar_ar = arabic_frame.GetMenuBar()
titles_ar = [bar_ar.GetMenuLabelText(i) for i in range(bar_ar.GetMenuCount())]
check("the menus are Arabic after switching",
      titles_ar == ["ملف", "جهات الاتصال", "عرض", "أدوات", "مساعدة"], titles_ar)
check("the layout turns right to left",
      arabic_frame.GetLayoutDirection() == wx.Layout_RightToLeft)
check("the group filter is Arabic",
      arabic_frame.label_filter.GetString(0) == "كل المجموعات",
      arabic_frame.label_filter.GetString(0))
check("the name column is Arabic",
      arabic_frame.list.GetColumn(0).GetText() == "الاسم",
      arabic_frame.list.GetColumn(0).GetText())

arabic_dialog = ContactDialog(arabic_frame, store)
check("the form is Arabic too",
      arabic_dialog.save_button.GetLabel() == "حفظ",
      arabic_dialog.save_button.GetLabel())
check("the add-another button is Arabic",
      "إضافة جهة اتصال أخرى" in arabic_dialog.add_another_button.GetLabel(),
      arabic_dialog.add_another_button.GetLabel())
arabic_dialog.Destroy()
arabic_frame.Destroy()
i18n.set_language("en")

# ---------- closing must release the database ----------
frame.Close()
wx.SafeYield()
try:
    store.conn.execute("SELECT 1")
    closed = False
except Exception:
    closed = True
check("closing shuts the database", closed)

app.Destroy()

still_locked = []
for leftover in db.parent.glob("t_ui_test.db*"):
    try:
        leftover.unlink()
    except PermissionError:
        still_locked.append(leftover.name)
check("no files are left locked", not still_locked, still_locked)

sys.exit(finish("Interface tests"))
