# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""The main window.

Decisions that matter for screen reader users:

* The table is a native Windows control (SysListView32), so NVDA reads
  each row and its columns with no extra work from us.
* Every command lives in the menu bar with its shortcut written beside
  it, because moving through menus is faster and clearer than hunting
  for buttons.
* Delete is handled inside the table rather than as a global shortcut,
  so it keeps working normally while typing in the search box.
* Ctrl+A is shared: it selects text when a text field has focus, and
  selects every row when the table has focus.
* Every result is written to the status bar and spoken, and the last
  message can be replayed at any time with Ctrl+J.
"""

from __future__ import annotations

from pathlib import Path

import wx

from .. import config, i18n, importer
from ..i18n import t
from ..models import Contact, display_label
from ..settings import Settings
from ..store import ContactRow, Store
from . import a11y, icons, theme
from .contact_dialog import ContactDialog
from .dialogs import (DuplicatesDialog, GroupsDialog, ReportDialog,
                      TrashDialog)

ID_DUPLICATES = wx.ID_HIGHEST + 2
ID_TRASH = wx.ID_HIGHEST + 3
ID_LAST_ACTION = wx.ID_HIGHEST + 4
ID_SHORTCUTS = wx.ID_HIGHEST + 5
ID_BACKUP = wx.ID_HIGHEST + 6
ID_FOCUS_LIST = wx.ID_HIGHEST + 7
ID_SEARCH_TIMER = wx.ID_HIGHEST + 8
ID_ANNOUNCE_TIMER = wx.ID_HIGHEST + 9
ID_GROUPS = wx.ID_HIGHEST + 10
ID_LANGUAGE_BASE = wx.ID_HIGHEST + 100
ID_APPEARANCE_BASE = wx.ID_HIGHEST + 200

# How long after the last keystroke before searching. Short enough not to
# be noticed, long enough that fast typing does not run a query per letter.
SEARCH_DELAY_MS = 150

# A longer wait before speaking the result count, so we do not interrupt
# the user mid-word.
ANNOUNCE_DELAY_MS = 600


# Read when the message is spoken, so the words follow the language.
APPEARANCE_NAMES = {
    "system": lambda: t("Follow Windows"),
    "light": lambda: t("Light"),
    "dark": lambda: t("Dark"),
}


def _shortcuts_text() -> str:
    """The help screen text, built fresh so it follows the language."""
    rows = [
        ("Ctrl+N", t("New contact")),
        ("Ctrl+E", t("Edit the selected contact")),
        (t("Delete"), t("Delete the selected contacts (while in the table)")),
        (t("Enter"), t("Edit the selected contact (while in the table)")),
        ("Ctrl+A", t("Select every contact (while in the table)")),
        ("", ""),
        ("Ctrl+F", t("Go to the search box")),
        ("Ctrl+L", t("Go to the contacts table")),
        ("F5", t("Refresh the list")),
        ("", ""),
        ("Ctrl+I", t("Import from a file")),
        ("Ctrl+S", t("Export to a file")),
        ("Ctrl+G", t("Manage groups")),
        ("Ctrl+D", t("Find duplicates")),
        ("Ctrl+T", t("Deleted items")),
        ("", ""),
        ("Ctrl+J", t("Repeat the last message")),
        ("F1", t("Show this screen")),
    ]
    lines = [t("Keyboard shortcuts:"), ""]
    for key, meaning in rows:
        lines.append(f"{key:<10}  {meaning}" if key else "")

    lines += [
        "",
        t("Notes:"),
        "",
        t("* To add several contacts in one go, open a new contact and use "
          "the plus button, Add another contact. The form clears for the "
          "next one but keeps the organization, class and group."),
        "",
        t("* Search finds a name however its hamza or diacritics are written, "
          "and finds a number whether you type it in Arabic or Latin digits, "
          "with a leading zero or a country code."),
        "",
        t("* In the table, type the first letter of a name to jump to it."),
        "",
        t("* To select a few: Shift with the arrow keys, or Ctrl with the "
          "space bar."),
    ]
    return "\n".join(lines)


class ContactListCtrl(wx.ListCtrl):
    """The contacts table.

    Runs in virtual mode, meaning it asks for a cell's text only when
    that cell is drawn instead of building every row up front. That keeps
    it fast even with tens of thousands of contacts.
    """

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, style=wx.LC_REPORT | wx.LC_VIRTUAL)
        self.SetName(t("Contacts table"))
        self.rows: list[ContactRow] = []

        # A list control takes its row height from the image list it was
        # given, so an empty list of the height wanted is the way to ask
        # for roomier rows. Nothing is ever drawn from it.
        self._spacer_images = wx.ImageList(1, theme.ROW_HEIGHT)
        self.AssignImageList(self._spacer_images, wx.IMAGE_LIST_SMALL)

        # Every other row is tinted, which makes a long line easier to
        # follow across the screen. Under a high contrast theme the tint
        # is dropped: those themes promise a fixed set of colours, and
        # decoration that breaks the promise does real harm.
        attr_class = getattr(wx, "ItemAttr", None) or wx.ListItemAttr
        self._plain_row = attr_class()
        self._banded_row = attr_class()
        stripe = theme.stripe_colour()
        self._banding = stripe is not None
        if stripe is not None:
            self._banded_row.SetBackgroundColour(stripe)
        if theme.is_dark():
            # A row that states its own colours cannot be left behind when
            # the rest of the window turns dark.
            for attr in (self._plain_row, self._banded_row):
                attr.SetTextColour(theme.text_colour())
            self._plain_row.SetBackgroundColour(theme.window_colour())
        # The same column order Google Contacts uses for its own list:
        # name, email, phone, then job title and company, then labels.
        columns = [
            (t("Name"), 200),
            (t("Email"), 200),
            (t("Phone"), 140),
            (t("Class or job title"), 130),
            (t("Organization"), 150),
            (t("Groups"), 140),
        ]
        for index, (title, width) in enumerate(columns):
            self.InsertColumn(index, title, width=width)

    def set_rows(self, rows: list[ContactRow]) -> None:
        # Reset the count first so wx cannot read rows that just went away.
        self.SetItemCount(0)
        self.rows = rows
        self.SetItemCount(len(rows))
        self.Refresh()

    def OnGetItemAttr(self, item: int):  # noqa: N802 (wx name)
        """The colours for one row: plain, or tinted on alternate lines."""
        if not self._banding:
            return None
        return self._banded_row if item % 2 else self._plain_row

    def OnGetItemImage(self, item: int) -> int:  # noqa: N802 (wx name)
        """No picture per row; the image list only sets the row height."""
        return -1

    def OnGetItemText(self, item: int, column: int) -> str:  # noqa: N802 (wx name)
        if item >= len(self.rows):
            return ""
        row = self.rows[item]
        return [
            display_label(row.display_name),
            row.primary_email,
            row.primary_phone,
            row.job_title,
            row.organization,
            row.labels_text,
        ][column]

    def select_all(self) -> int:
        """Select every row and return how many were selected."""
        count = self.GetItemCount()
        if not count:
            return 0
        self.Freeze()
        try:
            for index in range(count):
                self.SetItemState(index, wx.LIST_STATE_SELECTED,
                                  wx.LIST_STATE_SELECTED)
        finally:
            self.Thaw()
        return count


class MainFrame(wx.Frame):
    """The main window."""

    def __init__(self, store: Store, settings: Settings | None = None) -> None:
        super().__init__(None, title=t(config.APP_NAME), size=(1000, 660))
        if i18n.is_rtl():
            self.SetLayoutDirection(wx.Layout_RightToLeft)
        self.store = store
        # Settings live in their own file, never in the contacts database.
        self.settings = settings if settings is not None else Settings()

        self.CreateStatusBar(2)
        self.SetStatusWidths([-3, -1])
        self.announcer = a11y.Announcer(self)

        self._language_ids: dict[int, str] = {}
        self._build_menu()
        self._build_ui()

        # Two timers: one delays the search itself, one delays speaking
        # the result count.
        self.search_timer = wx.Timer(self, ID_SEARCH_TIMER)
        self.announce_timer = wx.Timer(self, ID_ANNOUNCE_TIMER)
        self.Bind(wx.EVT_TIMER, self._on_search_timer, id=ID_SEARCH_TIMER)
        self.Bind(wx.EVT_TIMER, self._on_announce_timer, id=ID_ANNOUNCE_TIMER)
        self.Bind(wx.EVT_CLOSE, self._on_close)

        theme.apply_window(self)

        self.refresh(announce=False)
        self.Centre()
        self.search.SetFocus()

    # ------------------------------------------------------------ building

    def _build_menu(self) -> None:
        bar = wx.MenuBar()

        file_menu = wx.Menu()
        icons.make_menu_item(file_menu, wx.ID_OPEN,
                             t("Import from a file...") + "\tCtrl+I",
                             t("Read contacts from a CSV or vCard file"), "import")
        icons.make_menu_item(file_menu, wx.ID_SAVEAS,
                             t("Export to a file...") + "\tCtrl+S",
                             t("Save contacts to a CSV or vCard file"), "export")
        file_menu.AppendSeparator()
        icons.make_menu_item(file_menu, ID_BACKUP, t("Back up now"),
                             t("Save a copy of the database"), "backup")
        file_menu.AppendSeparator()
        icons.make_menu_item(file_menu, wx.ID_EXIT, t("Exit") + "\tAlt+F4",
                             "", "quit")
        bar.Append(file_menu, t("File"))

        contacts_menu = wx.Menu()
        icons.make_menu_item(contacts_menu, wx.ID_NEW,
                             t("New contact") + "\tCtrl+N", "", "new")
        icons.make_menu_item(contacts_menu, wx.ID_EDIT,
                             t("Edit the selected contact") + "\tCtrl+E", "", "edit")
        icons.make_menu_item(contacts_menu, wx.ID_DELETE,
                             t("Delete the selected contacts"), "", "delete")
        contacts_menu.AppendSeparator()
        icons.make_menu_item(contacts_menu, wx.ID_SELECTALL,
                             t("Select every contact") + "\tCtrl+A",
                             t("Select every contact currently listed"), "select_all")
        contacts_menu.AppendSeparator()
        icons.make_menu_item(contacts_menu, ID_GROUPS,
                             t("Groups...") + "	Ctrl+G",
                             t("Create, rename and delete groups"), "label")
        icons.make_menu_item(contacts_menu, ID_DUPLICATES,
                             t("Find duplicates...") + "\tCtrl+D", "", "duplicates")
        bar.Append(contacts_menu, t("Contacts"))

        view_menu = wx.Menu()
        icons.make_menu_item(view_menu, wx.ID_FIND,
                             t("Go to the search box") + "\tCtrl+F", "", "search")
        icons.make_menu_item(view_menu, ID_FOCUS_LIST,
                             t("Go to the contacts table") + "\tCtrl+L", "", "list")
        icons.make_menu_item(view_menu, wx.ID_REFRESH,
                             t("Refresh the list") + "\tF5", "", "refresh")
        view_menu.AppendSeparator()
        icons.make_menu_item(view_menu, ID_LAST_ACTION,
                             t("Repeat the last message") + "\tCtrl+J", "", "speak")
        bar.Append(view_menu, t("View"))

        view_menu.AppendSeparator()
        view_menu.AppendSubMenu(self._build_appearance_menu(), t("Appearance"))

        tools_menu = wx.Menu()
        icons.make_menu_item(tools_menu, ID_TRASH,
                             t("Deleted items...") + "\tCtrl+T", "", "trash")
        tools_menu.AppendSeparator()
        tools_menu.AppendSubMenu(self._build_language_menu(), t("Language"))
        bar.Append(tools_menu, t("Tools"))

        help_menu = wx.Menu()
        icons.make_menu_item(help_menu, ID_SHORTCUTS,
                             t("Keyboard shortcuts") + "\tF1", "", "help")
        icons.make_menu_item(help_menu, wx.ID_ABOUT, t("About"), "", "about")
        bar.Append(help_menu, t("Help"))

        self.SetMenuBar(bar)

        for identifier, handler in [
            (wx.ID_OPEN, self._on_import),
            (wx.ID_SAVEAS, self._on_export),
            (ID_BACKUP, self._on_backup),
            (wx.ID_EXIT, lambda e: self.Close()),
            (wx.ID_NEW, self._on_new),
            (wx.ID_EDIT, self._on_edit),
            (wx.ID_DELETE, self._on_delete),
            (wx.ID_SELECTALL, self._on_select_all),
            (ID_GROUPS, self._on_groups),
            (ID_DUPLICATES, self._on_duplicates),
            (wx.ID_FIND, lambda e: self.search.SetFocus()),
            (ID_FOCUS_LIST, self._on_focus_list),
            (wx.ID_REFRESH, lambda e: self.refresh()),
            (ID_LAST_ACTION, self._on_last_action),
            (ID_TRASH, self._on_trash),
            (ID_SHORTCUTS, self._on_shortcuts),
            (wx.ID_ABOUT, self._on_about),
        ]:
            self.Bind(wx.EVT_MENU, handler, id=identifier)

    def _build_appearance_menu(self) -> wx.Menu:
        """Light, dark, or whatever Windows is set to."""
        menu = wx.Menu()
        current = theme.get_mode()
        self._appearance_ids: dict[int, str] = {}

        choices = [
            (theme.FOLLOW_SYSTEM, t("Follow Windows")),
            (theme.LIGHT, t("Light")),
            (theme.DARK, t("Dark")),
        ]
        for offset, (mode, label) in enumerate(choices):
            identifier = ID_APPEARANCE_BASE + offset
            self._appearance_ids[identifier] = mode
            item = menu.AppendRadioItem(identifier, label)
            if mode == current:
                item.Check(True)
            self.Bind(wx.EVT_MENU, self._on_appearance, id=identifier)

        if theme.is_high_contrast():
            # A high contrast theme decides the colours itself, and the
            # choice would do nothing but mislead.
            for identifier in self._appearance_ids:
                menu.Enable(identifier, False)

        return menu

    def _build_language_menu(self) -> wx.Menu:
        """One checkable entry per available language."""
        menu = wx.Menu()
        current = i18n.get_language()
        for offset, (code, name) in enumerate(i18n.available_languages().items()):
            identifier = ID_LANGUAGE_BASE + offset
            self._language_ids[identifier] = code
            item = menu.AppendRadioItem(identifier, name)
            if code == current:
                item.Check(True)
            self.Bind(wx.EVT_MENU, self._on_language, id=identifier)
        return menu

    def _build_toolbar(self) -> None:
        """The row of commands across the top of the window.

        A real wxToolBar rather than a row of buttons, because Windows
        draws it natively and screen readers already know what a toolbar
        is. Every tool keeps its words alongside its picture: the icon is
        what a sighted user reaches for, the text is what gets announced,
        and neither is asked to do the other's job.

        The tools carry the same command identifiers as the menu entries,
        so they run the same handlers with nothing bound twice.
        """
        bar = self.CreateToolBar(
            wx.TB_HORIZONTAL | wx.TB_TEXT | wx.TB_FLAT | wx.TB_NODIVIDER
        )
        bar.SetToolBitmapSize(wx.Size(*theme.TOOLBAR_ICON))

        self.toolbar_tools: dict[str, int] = {}

        def tool(identifier: int, label: str, icon: str, hint: str) -> None:
            bar.AddTool(identifier, label,
                        icons.get(icon, theme.TOOLBAR_ICON, wx.ART_TOOLBAR),
                        shortHelp=hint)
            self.toolbar_tools[icon] = identifier

        tool(wx.ID_NEW, t("New"), "new", t("New contact"))
        tool(wx.ID_EDIT, t("Edit"), "edit", t("Edit the selected contact"))
        tool(wx.ID_DELETE, t("Delete"), "delete",
             t("Delete the selected contacts"))
        bar.AddSeparator()
        tool(wx.ID_SELECTALL, t("Select all"), "select_all",
             t("Select every contact currently listed"))
        bar.AddSeparator()
        tool(wx.ID_OPEN, t("Import"), "import",
             t("Read contacts from a CSV or vCard file"))
        tool(wx.ID_SAVEAS, t("Export"), "export",
             t("Save contacts to a CSV or vCard file"))
        bar.AddSeparator()
        tool(ID_GROUPS, t("Groups"), "label",
             t("Create, rename and delete groups"))
        tool(ID_DUPLICATES, t("Duplicates"), "duplicates", t("Find duplicates"))

        bar.Realize()

    def _build_ui(self) -> None:
        self._build_toolbar()

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # ---- the search bar, given a band of its own ----
        search_panel = wx.Panel(panel)
        search_panel.SetBackgroundColour(theme.panel_colour())
        search_row = wx.BoxSizer(wx.HORIZONTAL)

        magnifier = wx.StaticBitmap(
            search_panel, bitmap=icons.get("search", theme.FIELD_ICON))
        search_row.Add(magnifier, 0,
                       wx.ALIGN_CENTER_VERTICAL | wx.LEFT, theme.MARGIN)

        search_caption = wx.StaticText(search_panel, label=t("Search:"))
        search_row.Add(search_caption, 0,
                       wx.ALIGN_CENTER_VERTICAL | wx.LEFT, theme.GAP)

        self.search = wx.TextCtrl(search_panel, style=wx.TE_PROCESS_ENTER)
        self.search.SetName(t("Search contacts"))
        self.search.SetFont(theme.enlarged_font(1))
        self.search.SetMinSize(wx.Size(-1, 28))
        search_row.Add(self.search, 1,
                       wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, theme.GAP)

        group_caption = wx.StaticText(search_panel, label=t("Group:"))
        search_row.Add(group_caption, 0, wx.ALIGN_CENTER_VERTICAL)

        self.all_labels_text = t("All groups")
        self.label_filter = wx.Choice(search_panel, choices=[self.all_labels_text])
        self.label_filter.SetName(t("Filter by group"))
        self.label_filter.SetSelection(0)
        search_row.Add(self.label_filter, 0,
                       wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, theme.GAP)

        wrapper = wx.BoxSizer(wx.VERTICAL)
        wrapper.Add(search_row, 1, wx.EXPAND | wx.TOP | wx.BOTTOM, theme.GAP)
        search_panel.SetSizer(wrapper)
        sizer.Add(search_panel, 0, wx.EXPAND)

        # ---- the table, taking every pixel that is left ----
        self.list = ContactListCtrl(panel)
        sizer.Add(self.list, 1, wx.EXPAND)

        panel.SetSizer(sizer)

        self.search.Bind(wx.EVT_TEXT, self._on_search_text)
        self.search.Bind(wx.EVT_TEXT_ENTER, self._on_focus_list)
        self.label_filter.Bind(wx.EVT_CHOICE, lambda e: self.refresh())
        self.list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_edit)
        self.list.Bind(wx.EVT_KEY_DOWN, self._on_list_key)

    # ------------------------------------------------------------ data

    def refresh(self, announce: bool = True, keep_selection: bool = True,
                reload_labels: bool = True) -> None:
        """Rebuild the list for the current search text and group filter.

        Reads lightweight rows straight from the database rather than
        building a full object per contact, so typing in the search box
        stays instant even with tens of thousands of records.
        """
        previous_uid = None
        if keep_selection:
            current = self._focused_row()
            previous_uid = current.uid if current else None

        query = self.search.GetValue().strip()
        selection = self.label_filter.GetStringSelection()
        label = "" if selection == self.all_labels_text else selection

        rows = self.store.list_rows(query, label)
        self.list.set_rows(rows)

        if reload_labels:
            self._reload_label_choices()

        total = self.store.count()
        shown = len(rows)
        self.SetStatusText(t("{shown} of {total}", shown=shown, total=total), 1)

        # Put the cursor back on the same contact if it is still listed.
        if previous_uid:
            for index, row in enumerate(rows):
                if row.uid == previous_uid:
                    self.list.Select(index)
                    self.list.Focus(index)
                    break

        if announce:
            if query or label:
                self.announcer.say(t("{count} results.", count=shown))
            else:
                self.announcer.say(t("{count} contacts.", count=shown))

    def _reload_label_choices(self) -> None:
        """Refresh the group list, keeping whatever the user picked."""
        current = self.label_filter.GetStringSelection()
        wanted = [self.all_labels_text] + self.store.all_labels()
        if list(self.label_filter.GetStrings()) == wanted:
            return
        self.label_filter.Set(wanted)
        if current in wanted:
            self.label_filter.SetStringSelection(current)
        else:
            self.label_filter.SetSelection(0)

    # ------------------------------------------------------------ selection

    def _focused_row(self) -> ContactRow | None:
        index = self.list.GetFocusedItem()
        if index < 0:
            index = self.list.GetFirstSelected()
        if 0 <= index < len(self.list.rows):
            return self.list.rows[index]
        return None

    def _selected_rows(self) -> list[ContactRow]:
        out: list[ContactRow] = []
        index = self.list.GetFirstSelected()
        while index != -1:
            if index < len(self.list.rows):
                out.append(self.list.rows[index])
            index = self.list.GetNextSelected(index)
        if not out:
            one = self._focused_row()
            if one:
                out.append(one)
        return out

    def _focused_contact(self) -> Contact | None:
        """Load the full object for the focused row, only when editing."""
        row = self._focused_row()
        return self.store.get(row.local_id) if row else None

    def _on_select_all(self, event: wx.CommandEvent) -> None:
        """Select every listed contact, or every character in a text field.

        Ctrl+A has to serve both, because a single accelerator fires
        wherever the focus happens to be. Taking the focus into account
        keeps the shortcut behaving as expected in the search box.
        """
        focused = wx.Window.FindFocus()
        if focused is not None and focused is not self.list \
                and hasattr(focused, "SelectAll"):
            focused.SelectAll()
            return

        self._flush_search()
        count = self.list.select_all()
        self.list.SetFocus()
        if count:
            self.announcer.say(t("Selected all {count} contacts.", count=count))
        else:
            self.announcer.say(t("There is nothing to select."))

    # ------------------------------------------------------------ search

    def _on_search_text(self, event: wx.CommandEvent) -> None:
        """Each keystroke postpones the search instead of running it."""
        self.search_timer.Start(SEARCH_DELAY_MS, oneShot=True)
        self.announce_timer.Start(ANNOUNCE_DELAY_MS, oneShot=True)

    def _on_search_timer(self, event: wx.TimerEvent) -> None:
        self._run_search()

    def _run_search(self) -> None:
        # Groups do not change while typing, so there is no need to
        # rebuild that list on every keystroke.
        self.refresh(announce=False, keep_selection=False, reload_labels=False)

    def _flush_search(self) -> None:
        """Run any postponed search immediately.

        Called before anything that depends on what the table holds, so a
        user who types and hits Enter straight away acts on the new
        results rather than the old ones.
        """
        if self.search_timer.IsRunning():
            self.search_timer.Stop()
            self._run_search()

    def _on_announce_timer(self, event: wx.TimerEvent) -> None:
        self._flush_search()
        count = len(self.list.rows)
        query = self.search.GetValue().strip()
        if query:
            self.announcer.say(t("{count} results for {query}.",
                                 count=count, query=query))
        else:
            self.announcer.say(t("{count} contacts.", count=count))

    def _on_focus_list(self, event: wx.CommandEvent) -> None:
        self._flush_search()
        self.list.SetFocus()
        if self.list.rows and self.list.GetFirstSelected() == -1:
            self.list.Select(0)
            self.list.Focus(0)

    def _on_list_key(self, event: wx.KeyEvent) -> None:
        """Delete removes; everything else carries on as normal."""
        if event.GetKeyCode() == wx.WXK_DELETE:
            self._on_delete(event)
            return
        event.Skip()

    # ------------------------------------------------------------ editing

    def _on_new(self, event: wx.CommandEvent) -> None:
        dialog = ContactDialog(self, self.store)
        if dialog.ShowModal() == wx.ID_OK and dialog.entries:
            self._save_entries(dialog.entries, is_new=True)
        dialog.Destroy()

    def _on_edit(self, event: wx.CommandEvent) -> None:
        self._flush_search()
        contact = self._focused_contact()
        if contact is None:
            self.announcer.say(t("Select a contact first."))
            return
        dialog = ContactDialog(self, self.store, contact)
        if dialog.ShowModal() == wx.ID_OK and dialog.entries:
            self._save_entries(dialog.entries, is_new=False)
        dialog.Destroy()

    def _save_entries(self, entries: list[tuple[Contact, Contact | None]],
                      is_new: bool) -> None:
        """Write everything the form collected, merging where asked."""
        added = 0
        merged = 0
        last_name = ""

        for contact, target in entries:
            if target is not None:
                target.merge_from(contact)
                # Editing an existing record into another one leaves the
                # original behind, so retire it.
                if not is_new and contact.local_id is not None:
                    self.store.delete(contact.local_id, commit=False)
                self.store.update(target)
                merged += 1
                last_name = display_label(target.display_name)
            else:
                self.store.save(contact)
                added += 1
                last_name = display_label(contact.display_name)

        self.refresh(announce=False)

        if added + merged == 1:
            if merged:
                self.announcer.say(t("Merged into '{name}'.", name=last_name))
            elif is_new:
                self.announcer.say(t("Added '{name}'.", name=last_name))
            else:
                self.announcer.say(t("Saved '{name}'.", name=last_name))
        else:
            self.announcer.say(
                t("Saved {added} contacts, merged {merged}.",
                  added=added, merged=merged)
            )

    def _on_delete(self, event: wx.CommandEvent) -> None:
        self._flush_search()
        rows = self._selected_rows()
        if not rows:
            self.announcer.say(t("Select a contact first."))
            return

        if len(rows) == 1:
            message = t(
                "'{name}' will be deleted.\n\nYou will find it in deleted "
                "items and can bring it back.",
                name=display_label(rows[0].display_name),
            )
        else:
            message = t(
                "{count} contacts will be deleted.\n\nYou will find them in "
                "deleted items and can bring them back.",
                count=len(rows),
            )

        if wx.MessageBox(message + "\n\n" + t("Go ahead?"), t("Confirm deletion"),
                         wx.YES_NO | wx.ICON_WARNING, self) != wx.YES:
            self.announcer.say(t("Deletion cancelled."))
            return

        name = display_label(rows[0].display_name)
        self.store.delete_many([r.local_id for r in rows])
        self.refresh(announce=False, keep_selection=False)
        if len(rows) == 1:
            self.announcer.say(
                t("Deleted '{name}'. You can restore it from deleted items.",
                  name=name)
            )
        else:
            self.announcer.say(t("Deleted {count} contacts.", count=len(rows)))

    # ------------------------------------------------------------ files

    def _on_import(self, event: wx.CommandEvent) -> None:
        wildcard = "|".join([
            t("All supported files") + " (*.csv;*.vcf)|*.csv;*.vcf",
            t("CSV files") + " (*.csv)|*.csv",
            t("vCard files") + " (*.vcf)|*.vcf",
        ])
        with wx.FileDialog(
            self, t("Choose a contacts file"), wildcard=wildcard,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = Path(dialog.GetPath())

        try:
            contacts, unmapped = importer.read_file(path)
        except (OSError, ValueError) as error:
            wx.MessageBox(t("The file could not be read:") + f"\n\n{error}",
                          t("Read error"), wx.OK | wx.ICON_ERROR, self)
            return

        if not contacts:
            wx.MessageBox(t("The file holds no contacts."), t("Empty file"),
                          wx.OK | wx.ICON_INFORMATION, self)
            return

        mode = self._ask_import_mode(len(contacts))
        if mode is None:
            self.announcer.say(t("Import cancelled."))
            return

        busy = wx.BusyCursor()
        try:
            report = importer.import_into(self.store, contacts, mode=mode,
                                          unmapped=unmapped)
        except Exception as error:  # noqa: BLE001 (any failure is shown to the user)
            del busy
            wx.MessageBox(
                t("Something went wrong during the import and nothing was "
                  "changed:") + f"\n\n{error}",
                t("Error"), wx.OK | wx.ICON_ERROR, self,
            )
            return
        del busy

        self.refresh(announce=False)
        self.announcer.say(
            t("Import finished. Added {added}, merged {merged}, skipped {skipped}.",
              added=report.added, merged=report.merged, skipped=report.skipped)
        )
        ReportDialog(self, t("Import result"), report.summary()).ShowModal()

    def _ask_import_mode(self, count: int) -> str | None:
        """Ask what should happen to contacts that already exist."""
        choices = [
            t("Merge: fill in what is missing (best)"),
            t("Skip: leave existing contacts alone"),
            t("Add everything: keep duplicates too"),
        ]
        modes = [importer.MODE_MERGE, importer.MODE_SKIP, importer.MODE_ADD_ALL]

        dialog = wx.SingleChoiceDialog(
            self,
            t("The file holds {count} contacts.", count=count) + "\n\n"
            + t("If one of them has the same number or address as a contact "
                "you already have, what should happen?"),
            t("Import method"), choices,
        )
        dialog.SetSelection(0)
        answer = dialog.ShowModal()
        index = dialog.GetSelection()
        dialog.Destroy()

        return modes[index] if answer == wx.ID_OK else None

    def _on_export(self, event: wx.CommandEvent) -> None:
        self._flush_search()
        total = self.store.count()
        shown = self.list.rows
        selected = self._selected_rows()

        # Offer the choices by count alone and fetch the full records only
        # after the user picks, so nothing large is loaded needlessly.
        options = [t("All contacts ({count})", count=total)]
        scopes: list[list[int] | None] = [None]
        if len(shown) != total:
            options.append(t("Only what is listed now ({count})", count=len(shown)))
            scopes.append([r.local_id for r in shown])
        if selected and len(selected) != len(shown):
            options.append(t("Only the selected ({count})", count=len(selected)))
            scopes.append([r.local_id for r in selected])

        dialog = wx.SingleChoiceDialog(self, t("What should be exported?"),
                                       t("Export range"), options)
        dialog.SetSelection(0)
        answer = dialog.ShowModal()
        index = dialog.GetSelection()
        dialog.Destroy()
        if answer != wx.ID_OK:
            self.announcer.say(t("Export cancelled."))
            return

        chosen = scopes[index]
        contacts = self.store.all() if chosen is None else self.store.get_many(chosen)
        if not contacts:
            wx.MessageBox(t("There is nothing to export."), t("Empty"),
                          wx.OK | wx.ICON_INFORMATION, self)
            return

        wildcard = "|".join([
            t("CSV file for Google and Excel") + " (*.csv)|*.csv",
            t("vCard file for phones") + " (*.vcf)|*.vcf",
        ])
        with wx.FileDialog(
            self, t("Save the file as"), defaultFile="contacts.csv",
            wildcard=wildcard, style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as file_dialog:
            if file_dialog.ShowModal() != wx.ID_OK:
                self.announcer.say(t("Export cancelled."))
                return
            path = Path(file_dialog.GetPath())
            filter_index = file_dialog.GetFilterIndex()

        # If no extension was typed, take it from the chosen file type.
        if not path.suffix:
            path = path.with_suffix(".vcf" if filter_index == 1 else ".csv")

        try:
            count = importer.export_file(path, contacts)
        except (OSError, ValueError) as error:
            wx.MessageBox(t("The file could not be written:") + f"\n\n{error}",
                          t("Save error"), wx.OK | wx.ICON_ERROR, self)
            return

        self.announcer.say(
            t("Exported {count} contacts to {name}.", count=count, name=path.name)
        )
        follow_up = (
            t("You can upload this file to Google Contacts from its import page.")
            if path.suffix.lower() == ".csv"
            else t("You can open this file on any phone to add the contacts.")
        )
        wx.MessageBox(
            t("{count} contacts saved to:", count=count) + f"\n\n{path}\n\n"
            + follow_up,
            t("Exported"), wx.OK | wx.ICON_INFORMATION, self,
        )

    def _on_backup(self, event: wx.CommandEvent) -> None:
        path = self.store.backup()
        if path is None:
            self.announcer.say(t("There is no data to back up."))
            return
        self.announcer.say(t("Backup saved."))
        wx.MessageBox(t("A copy was saved to:") + f"\n\n{path}", t("Backup"),
                      wx.OK | wx.ICON_INFORMATION, self)

    # ------------------------------------------------------------ tools

    def _on_groups(self, event: wx.CommandEvent) -> None:
        dialog = GroupsDialog(self, self.store)
        dialog.ShowModal()
        changed = dialog.changed
        dialog.Destroy()
        if changed:
            # The filter list and the group column both follow from this.
            self.refresh(announce=False)
            self.announcer.say(t("{count} groups.",
                                 count=len(self.store.all_labels())))

    def _on_duplicates(self, event: wx.CommandEvent) -> None:
        dialog = DuplicatesDialog(self, self.store)
        dialog.ShowModal()
        merged = dialog.merged
        dialog.Destroy()
        if merged:
            self.refresh(announce=False)
            self.announcer.say(t("Merged {count} groups.", count=merged))

    def _on_trash(self, event: wx.CommandEvent) -> None:
        dialog = TrashDialog(self, self.store)
        dialog.ShowModal()
        restored = dialog.restored
        dialog.Destroy()
        if restored:
            self.refresh(announce=False)
            self.announcer.say(t("Restored {count} contacts.", count=restored))

    def _on_last_action(self, event: wx.CommandEvent) -> None:
        message = self.announcer.last()
        a11y.speak(message, interrupt=True)
        self.SetStatusText(message, 0)

    def _rebuild(self, message: str) -> None:
        """Build the window again and hand the old one's work to it.

        Used whenever something changes that reaches every widget at
        once — the language, which flips the layout direction and every
        caption, or the appearance, which repaints the lot. Relabelling
        in place would mean touching each control by hand and getting one
        of them wrong. The database and the settings pass across
        untouched, so nothing is reopened or reloaded.
        """
        replacement = MainFrame(self.store, self.settings)
        replacement.Show()
        application = wx.GetApp()
        if application:
            application.SetTopWindow(replacement)

        self.search_timer.Stop()
        self.announce_timer.Stop()
        # Destroy skips the close handler, so the database is not closed.
        self.Destroy()

        replacement.announcer.say(message)

    def _on_language(self, event: wx.CommandEvent) -> None:
        """Switch language and rebuild the window in the new one."""
        code = self._language_ids.get(event.GetId())
        if not code or code == i18n.get_language():
            return

        self.settings.set("language", code)
        i18n.set_language(code)
        self._rebuild(
            t("Language changed to {name}.", name=i18n.language_name(code))
        )

    def _on_appearance(self, event: wx.CommandEvent) -> None:
        """Switch between light and dark, and repaint everything."""
        mode = self._appearance_ids.get(event.GetId())
        if not mode or mode == theme.get_mode():
            return

        self.settings.set("appearance", mode)
        theme.set_mode(mode)
        # Every icon is drawn in the text colour, which has just changed.
        icons.forget_drawings()
        self._rebuild(t("Appearance changed to {name}.",
                        name=APPEARANCE_NAMES.get(mode, mode)()))

    def _on_shortcuts(self, event: wx.CommandEvent) -> None:
        ReportDialog(self, t("Keyboard shortcuts"), _shortcuts_text(),
                     size=(680, 600)).ShowModal()

    def _on_about(self, event: wx.CommandEvent) -> None:
        reader = (t("connected") if a11y.is_screen_reader_connected()
                  else t("not connected"))
        lines = [
            t(config.APP_NAME),
            t("Version {version}", version=config.APP_VERSION),
            "",
            t("A program for managing contacts locally on your computer, "
              "with CSV and vCard import and export."),
            "",
            t("Number of contacts: {count}", count=self.store.count()),
            t("Database: {path}", path=self.store.path),
            t("Settings: {path}", path=self.settings.path),
            t("Backups: {path}", path=config.backup_dir()),
            "",
            t("Direct NVDA connection: {state}", state=reader),
            "",
            t("License: {name}", name=config.LICENSE_NAME),
        ]
        # The notice the GPL asks a program to show about itself. The
        # copyright line only appears once a holder has been set.
        if config.copyright_line():
            lines.append(config.copyright_line())
        lines += [
            "",
            t("This program is free software: you may pass it on and change "
              "it under the terms of the GNU General Public License. It comes "
              "with no warranty whatsoever, to the extent the law allows."),
            "",
            t("The full license is in the file LICENSE, distributed with the "
              "program, and at https://www.gnu.org/licenses/gpl-3.0.html"),
        ]
        text = "\n".join(lines)
        ReportDialog(self, t("About"), text, size=(680, 520)).ShowModal()

    def _on_close(self, event: wx.CloseEvent) -> None:
        self.search_timer.Stop()
        self.announce_timer.Stop()
        self.store.close()
        event.Skip()
