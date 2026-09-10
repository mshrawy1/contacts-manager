# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Supporting screens: reports, the deleted items bin, and merging duplicates.

Long reports are shown in a read-only text box rather than a message
box, so the user can move through them with the arrow keys and have a
screen reader re-read any line — instead of hearing it once and losing it.
"""

from __future__ import annotations

import time

import wx

from .. import i18n
from ..i18n import t
from ..models import Contact, display_label
from ..store import Store
from . import a11y, icons, theme


class ReportDialog(wx.Dialog):
    """Shows a long piece of text for reading, with a copy button."""

    def __init__(self, parent: wx.Window, title: str, text: str,
                 size: tuple[int, int] = (640, 470)) -> None:
        super().__init__(parent, title=title,
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER, size=size)
        if i18n.is_rtl():
            self.SetLayoutDirection(wx.Layout_RightToLeft)
        self.text = text

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(wx.StaticText(panel, label=title), 0, wx.ALL, 8)

        self.box = wx.TextCtrl(
            panel, value=text,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP,
        )
        self.box.SetName(title)
        sizer.Add(self.box, 1, wx.EXPAND | wx.ALL, 8)

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        copy_button = wx.Button(panel, wx.ID_ANY, t("Copy text"))
        close_button = wx.Button(panel, wx.ID_OK, t("Close"))
        icons.apply_to_button(copy_button, "copy")
        icons.apply_to_button(close_button, "close")
        close_button.SetDefault()
        buttons.AddStretchSpacer()
        buttons.Add(copy_button, 0, wx.ALL, 6)
        buttons.Add(close_button, 0, wx.ALL, 6)
        sizer.Add(buttons, 0, wx.EXPAND)

        panel.SetSizer(sizer)
        theme.apply_window(self)
        self.SetEscapeId(wx.ID_OK)
        copy_button.Bind(wx.EVT_BUTTON, self._on_copy)

        self.CentreOnParent()
        self.box.SetFocus()
        self.box.SetInsertionPoint(0)

    def _on_copy(self, event: wx.CommandEvent) -> None:
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(self.text))
            wx.TheClipboard.Close()
            wx.MessageBox(t("Copied."), t("Copy"), wx.OK | wx.ICON_INFORMATION, self)


class TrashDialog(wx.Dialog):
    """Deleted items: view, restore, or clear permanently."""

    def __init__(self, parent: wx.Window, store: Store) -> None:
        super().__init__(parent, title=t("Deleted items"),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
                         size=(660, 470))
        if i18n.is_rtl():
            self.SetLayoutDirection(wx.Layout_RightToLeft)
        self.store = store
        self.restored = 0
        self.items: list[tuple[int, Contact, float]] = []

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.info = wx.StaticText(panel, label="")
        sizer.Add(self.info, 0, wx.ALL, 8)

        self.list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.list.SetName(t("Deleted contacts"))
        self.list.InsertColumn(0, t("Name"), width=230)
        self.list.InsertColumn(1, t("Phone"), width=150)
        self.list.InsertColumn(2, t("Deleted on"), width=170)
        sizer.Add(self.list, 1, wx.EXPAND | wx.ALL, 8)

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.restore_button = wx.Button(panel, wx.ID_ANY, t("Restore selected"))
        self.empty_button = wx.Button(panel, wx.ID_ANY, t("Empty permanently"))
        close_button = wx.Button(panel, wx.ID_OK, t("Close"))
        icons.apply_to_button(self.restore_button, "restore")
        icons.apply_to_button(self.empty_button, "empty")
        icons.apply_to_button(close_button, "close")
        close_button.SetDefault()
        buttons.Add(self.restore_button, 0, wx.ALL, 6)
        buttons.Add(self.empty_button, 0, wx.ALL, 6)
        buttons.AddStretchSpacer()
        buttons.Add(close_button, 0, wx.ALL, 6)
        sizer.Add(buttons, 0, wx.EXPAND)

        panel.SetSizer(sizer)
        theme.apply_window(self)
        self.SetEscapeId(wx.ID_OK)

        self.restore_button.Bind(wx.EVT_BUTTON, self._on_restore)
        self.empty_button.Bind(wx.EVT_BUTTON, self._on_empty)
        self.list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_restore)

        self._reload()
        self.CentreOnParent()
        self.list.SetFocus()

    def _reload(self) -> None:
        self.items = self.store.trash_items()
        self.list.DeleteAllItems()
        for row, (_, contact, when) in enumerate(self.items):
            self.list.InsertItem(row, display_label(contact.display_name))
            self.list.SetItem(row, 1, contact.primary_phone)
            self.list.SetItem(row, 2,
                              time.strftime("%Y-%m-%d %H:%M", time.localtime(when)))

        count = len(self.items)
        self.info.SetLabel(
            t("{count} deleted contacts.", count=count) if count
            else t("Nothing has been deleted.")
        )
        self.restore_button.Enable(count > 0)
        self.empty_button.Enable(count > 0)
        if count:
            self.list.Select(0)
            self.list.Focus(0)

    def _on_restore(self, event: wx.CommandEvent) -> None:
        index = self.list.GetFirstSelected()
        if index < 0:
            wx.MessageBox(t("Select a contact first."), t("Nothing selected"),
                          wx.OK | wx.ICON_INFORMATION, self)
            return
        trash_id, contact, _ = self.items[index]
        self.store.restore(trash_id)
        self.restored += 1
        wx.MessageBox(
            t("'{name}' is back.", name=display_label(contact.display_name)),
            t("Restored"), wx.OK | wx.ICON_INFORMATION, self,
        )
        self._reload()

    def _on_empty(self, event: wx.CommandEvent) -> None:
        count = len(self.items)
        answer = wx.MessageBox(
            t("{count} contacts will be erased permanently and cannot be "
              "brought back.\n\nAre you sure?", count=count),
            t("Empty deleted items"), wx.YES_NO | wx.ICON_WARNING, self,
        )
        if answer == wx.YES:
            self.store.empty_trash()
            self._reload()


class DuplicatesDialog(wx.Dialog):
    """Finding and merging duplicate contacts."""

    def __init__(self, parent: wx.Window, store: Store) -> None:
        super().__init__(parent, title=t("Duplicate contacts"),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
                         size=(720, 530))
        if i18n.is_rtl():
            self.SetLayoutDirection(wx.Layout_RightToLeft)
        self.store = store
        self.merged = 0
        self.groups: list[list[Contact]] = []

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.info = wx.StaticText(panel, label="")
        sizer.Add(self.info, 0, wx.ALL, 8)

        self.include_names = wx.CheckBox(
            panel,
            label=t("Also treat people with exactly the same name as duplicates "
                    "(check these carefully)"),
        )
        sizer.Add(self.include_names, 0, wx.RIGHT | wx.LEFT | wx.BOTTOM, 8)

        sizer.Add(wx.StaticText(panel, label=t("Duplicate groups:")), 0,
                  wx.RIGHT | wx.LEFT, 8)

        self.list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.list.SetName(t("Duplicate groups"))
        self.list.InsertColumn(0, t("Names"), width=310)
        self.list.InsertColumn(1, t("Count"), width=70)
        self.list.InsertColumn(2, t("Why they match"), width=250)
        sizer.Add(self.list, 1, wx.EXPAND | wx.ALL, 8)

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.merge_button = wx.Button(panel, wx.ID_ANY, t("Merge selected group"))
        self.merge_all_button = wx.Button(panel, wx.ID_ANY, t("Merge every group"))
        close_button = wx.Button(panel, wx.ID_OK, t("Close"))
        icons.apply_to_button(self.merge_button, "merge")
        icons.apply_to_button(self.merge_all_button, "merge_all")
        icons.apply_to_button(close_button, "close")
        close_button.SetDefault()
        buttons.Add(self.merge_button, 0, wx.ALL, 6)
        buttons.Add(self.merge_all_button, 0, wx.ALL, 6)
        buttons.AddStretchSpacer()
        buttons.Add(close_button, 0, wx.ALL, 6)
        sizer.Add(buttons, 0, wx.EXPAND)

        panel.SetSizer(sizer)
        theme.apply_window(self)
        self.SetEscapeId(wx.ID_OK)

        self.include_names.Bind(wx.EVT_CHECKBOX, lambda e: self._reload())
        self.merge_button.Bind(wx.EVT_BUTTON, self._on_merge_one)
        self.merge_all_button.Bind(wx.EVT_BUTTON, self._on_merge_all)
        self.list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_merge_one)

        self._reload()
        self.CentreOnParent()
        self.list.SetFocus()

    def _reason(self, group: list[Contact]) -> str:
        """Explain why the program considers these the same person."""
        shared_phones: set[str] = set()
        shared_emails: set[str] = set()
        for index, first in enumerate(group):
            for second in group[index + 1:]:
                shared_phones |= first.phone_keys() & second.phone_keys()
                shared_emails |= first.email_keys() & second.email_keys()

        parts = []
        if shared_phones:
            parts.append(t("same phone number"))
        if shared_emails:
            parts.append(t("same email address"))
        if not parts:
            parts.append(t("exactly the same name"))
        return ", ".join(parts)

    def _reload(self) -> None:
        self.groups = self.store.duplicate_groups(
            include_names=self.include_names.GetValue()
        )
        self.list.DeleteAllItems()
        for row, group in enumerate(self.groups):
            names = " + ".join(display_label(c.display_name) for c in group[:3])
            if len(group) > 3:
                names += " + " + t("{count} more", count=len(group) - 3)
            self.list.InsertItem(row, names)
            self.list.SetItem(row, 1, str(len(group)))
            self.list.SetItem(row, 2, self._reason(group))

        count = len(self.groups)
        self.info.SetLabel(
            t("Found {count} duplicate groups.", count=count) if count
            else t("No duplicate contacts found.")
        )
        self.merge_button.Enable(count > 0)
        self.merge_all_button.Enable(count > 0)
        if count:
            self.list.Select(0)
            self.list.Focus(0)

    def _merge_group(self, group: list[Contact]) -> None:
        """Merge a whole group into its oldest member."""
        target = group[0]
        for other in group[1:]:
            target.merge_from(other)
            self.store.delete(other.local_id, commit=False)
        self.store.update(target, commit=False)
        self.store.conn.commit()
        self.merged += 1

    def _on_merge_one(self, event: wx.CommandEvent) -> None:
        index = self.list.GetFirstSelected()
        if index < 0:
            wx.MessageBox(t("Select a group first."), t("Nothing selected"),
                          wx.OK | wx.ICON_INFORMATION, self)
            return

        group = self.groups[index]
        details = "\n".join(
            "  - {name} | {phone} | {email}".format(
                name=display_label(c.display_name),
                phone=c.primary_phone or t("no phone"),
                email=c.primary_email or t("no email"),
            )
            for c in group
        )
        answer = wx.MessageBox(
            t("These will all be merged into '{name}':",
              name=display_label(group[0].display_name))
            + "\n\n" + details + "\n\n"
            + t("Missing details are carried over, and nothing is lost. All right?"),
            t("Confirm merge"), wx.YES_NO | wx.ICON_QUESTION, self,
        )
        if answer != wx.YES:
            return

        self._merge_group(group)
        wx.MessageBox(t("Merged."), t("Done"), wx.OK | wx.ICON_INFORMATION, self)
        self._reload()

    def _on_merge_all(self, event: wx.CommandEvent) -> None:
        count = len(self.groups)
        answer = wx.MessageBox(
            t("{count} groups will be merged, each into its first member.",
              count=count)
            + "\n\n"
            + t("A backup was taken beforehand, and anything removed goes to "
                "deleted items.")
            + "\n\n" + t("Carry on?"),
            t("Merge every group"), wx.YES_NO | wx.ICON_WARNING, self,
        )
        if answer != wx.YES:
            return

        self.store.backup()
        for group in list(self.groups):
            self._merge_group(group)
        wx.MessageBox(t("Merged {count} groups.", count=count), t("Done"),
                      wx.OK | wx.ICON_INFORMATION, self)
        self._reload()


class GroupsDialog(wx.Dialog):
    """Creating, renaming and deleting groups.

    Groups used to exist only as text typed into a contact, which meant
    one could not be made in advance and vanished the moment its last
    contact was deleted. Here they are things in their own right: an
    empty group is a perfectly good group, ready to be filled.

    Renaming changes the name on every contact carrying it. Deleting
    removes the group from those contacts but never the contacts
    themselves — that is what the message says, because it is the
    question anyone would ask before pressing the button.
    """

    def __init__(self, parent: wx.Window, store: Store) -> None:
        super().__init__(parent, title=t("Manage groups"),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
                         size=(560, 470))
        if i18n.is_rtl():
            self.SetLayoutDirection(wx.Layout_RightToLeft)
        self.store = store
        self.changed = False
        self.names: list[str] = []

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.info = wx.StaticText(panel, label="")
        sizer.Add(self.info, 0, wx.ALL, 8)

        caption = wx.StaticText(panel, label=t("Groups:"))
        sizer.Add(caption, 0, wx.RIGHT | wx.LEFT, 8)

        self.list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.list.SetName(t("Groups:"))
        self.list.InsertColumn(0, t("Group"), width=330)
        self.list.InsertColumn(1, t("Members"), width=110)
        sizer.Add(self.list, 1, wx.EXPAND | wx.ALL, 8)

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.new_button = wx.Button(panel, wx.ID_ANY, t("New group"))
        self.rename_button = wx.Button(panel, wx.ID_ANY, t("Rename"))
        self.delete_button = wx.Button(panel, wx.ID_ANY, t("Delete"))
        close_button = wx.Button(panel, wx.ID_OK, t("Close"))
        icons.apply_to_button(self.new_button, "add")
        icons.apply_to_button(self.rename_button, "edit")
        icons.apply_to_button(self.delete_button, "trash")
        icons.apply_to_button(close_button, "close")
        close_button.SetDefault()
        buttons.Add(self.new_button, 0, wx.ALL, 6)
        buttons.Add(self.rename_button, 0, wx.ALL, 6)
        buttons.Add(self.delete_button, 0, wx.ALL, 6)
        buttons.AddStretchSpacer()
        buttons.Add(close_button, 0, wx.ALL, 6)
        sizer.Add(buttons, 0, wx.EXPAND)

        panel.SetSizer(sizer)
        theme.apply_window(self)
        self.SetEscapeId(wx.ID_OK)

        self.new_button.Bind(wx.EVT_BUTTON, self._on_new)
        self.rename_button.Bind(wx.EVT_BUTTON, self._on_rename)
        self.delete_button.Bind(wx.EVT_BUTTON, self._on_delete)
        self.list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_rename)

        self._reload()
        self.CentreOnParent()
        self.list.SetFocus()

    def _reload(self, keep: str = "") -> None:
        counts = self.store.label_counts()
        self.names = self.store.all_labels()

        self.list.DeleteAllItems()
        for row, name in enumerate(self.names):
            self.list.InsertItem(row, name)
            self.list.SetItem(row, 1, str(counts.get(name, 0)))

        count = len(self.names)
        self.info.SetLabel(
            t("{count} groups.", count=count) if count
            else t("There are no groups yet. Make one here, or type one into "
                   "a contact.")
        )
        for button in (self.rename_button, self.delete_button):
            button.Enable(count > 0)

        if count:
            index = self.names.index(keep) if keep in self.names else 0
            self.list.Select(index)
            self.list.Focus(index)

    def _selected(self) -> str:
        index = self.list.GetFirstSelected()
        return self.names[index] if 0 <= index < len(self.names) else ""

    def _ask_for_name(self, title: str, message: str, initial: str = "") -> str:
        dialog = wx.TextEntryDialog(self, message, title, initial)
        answer = dialog.ShowModal()
        value = dialog.GetValue().strip()
        dialog.Destroy()
        return value if answer == wx.ID_OK else ""

    def _on_new(self, event: wx.CommandEvent) -> None:
        name = self._ask_for_name(t("New group"), t("Name for the new group:"))
        if not name:
            return
        if not self.store.create_group(name):
            wx.MessageBox(t("There is already a group called '{name}'.", name=name),
                          t("Name already used"), wx.OK | wx.ICON_ERROR, self)
            return
        self.changed = True
        self._reload(keep=name)
        a11y.speak(t("Added the group '{name}'.", name=name))

    def _on_rename(self, event: wx.CommandEvent) -> None:
        old = self._selected()
        if not old:
            wx.MessageBox(t("Select a group first."), t("Nothing selected"),
                          wx.OK | wx.ICON_INFORMATION, self)
            return

        new = self._ask_for_name(t("Rename group"),
                                 t("New name for '{name}':", name=old), old)
        if not new or new == old:
            return
        if new in self.store.all_labels():
            wx.MessageBox(t("There is already a group called '{name}'.", name=new),
                          t("Name already used"), wx.OK | wx.ICON_ERROR, self)
            return

        moved = self.store.rename_group(old, new)
        self.changed = True
        self._reload(keep=new)
        a11y.speak(t("Renamed to '{name}'. {count} contacts were updated.",
                     name=new, count=moved))

    def _on_delete(self, event: wx.CommandEvent) -> None:
        name = self._selected()
        if not name:
            wx.MessageBox(t("Select a group first."), t("Nothing selected"),
                          wx.OK | wx.ICON_INFORMATION, self)
            return

        members = self.store.label_counts().get(name, 0)
        answer = wx.MessageBox(
            t("The group '{name}' will be removed from {count} contacts.\n\n"
              "The contacts themselves are not deleted — only the group is.\n\n"
              "Go ahead?", name=name, count=members),
            t("Delete group"), wx.YES_NO | wx.ICON_WARNING, self,
        )
        if answer != wx.YES:
            return

        self.store.delete_group(name)
        self.changed = True
        self._reload()
        a11y.speak(t("Deleted the group '{name}'.", name=name))
