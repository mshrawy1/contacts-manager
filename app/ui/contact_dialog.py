# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""The form for adding and editing a contact.

The fields follow the order Google Contacts uses for its own columns —
first, middle and last name, then the name prefix and suffix, nickname,
organization, job title, department, birthday, notes, groups, email
addresses, phone numbers, address and website — so importing, editing
and exporting all present the same information in the same sequence.

Only the three name fields and the first two phone numbers are shown to
begin with. Everything else sits behind "Show more fields", because a
run of ordinary entries needs a name and a number and nothing else, and
a short form is far quicker to move through with a screen reader.
Opening a contact that already has any of the extra fields filled in
reveals them automatically, so nothing is ever hidden from its owner.

Every field has its caption written immediately before it, so a screen
reader announces the field's name when the user tabs onto it.

When adding, the form doubles as a batch entry screen. The "Add another
contact" button puts the current entry on a list and clears the form,
keeping the organization, class and group so a run of students from one
classroom does not have to be retyped. Saving then writes the whole list
at once, after a confirmation that states how many are about to be saved.
"""

from __future__ import annotations

import wx

from .. import config, i18n, textutil
# Imported under another name: "phones" is also the natural name for the
# local list of Entry objects being gathered in _collect, and a module
# shadowed halfway through a method is a bug waiting to be written.
from .. import phones as phone_rules
from ..i18n import t
from ..models import Contact, Entry, display_label
from ..store import Store
from . import a11y, icons, theme

# How many values the form shows. Anything beyond this is preserved
# untouched rather than being dropped on save.
VISIBLE_PHONES = 3
VISIBLE_EMAILS = 2

# Phone slots shown before the user asks for more.
PHONES_ALWAYS_SHOWN = 2

# Fields kept when the form is cleared for the next contact, because a
# batch of entries usually shares them.
CARRIED_OVER = ("organization", "job_title", "department", "labels")


class ContactDialog(wx.Dialog):
    """Collects one contact, or a list of them when adding."""

    def __init__(self, parent: wx.Window, store: Store,
                 contact: Contact | None = None, settings=None) -> None:
        self.store = store
        self.settings = settings
        self.original = contact
        self.is_new = contact is None
        title = (
            t("New contact") if self.is_new
            else t("Edit: {name}", name=display_label(contact.display_name))
        )

        super().__init__(
            parent, title=title,
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            size=(600, 640),
        )
        if i18n.is_rtl():
            self.SetLayoutDirection(wx.Layout_RightToLeft)

        # Everything the main window saves once this dialog closes. Each
        # item is the contact plus, when the user chose to merge, the
        # existing contact it should be folded into.
        self.entries: list[tuple[Contact, Contact | None]] = []

        # Widgets belonging to the hidden section, and whether it is open.
        self._extra_widgets: list[wx.Window] = []
        self._showing_more = False

        self._build()
        self._fill(contact or Contact())

        # An existing contact with extra details opens with them visible.
        if contact is not None and self._has_extra_data(contact):
            self._showing_more = True
        self._apply_more_state(announce=False)

        self.SetMinSize(wx.Size(520, 320))
        self.CentreOnParent()
        self.first_name.SetFocus()

    # ------------------------------------------------------------ building

    def _build(self) -> None:
        outer = wx.BoxSizer(wx.VERTICAL)

        self.scroll = wx.ScrolledWindow(self, style=wx.VSCROLL)
        self.scroll.SetScrollRate(0, 12)
        self.form = wx.BoxSizer(wx.VERTICAL)

        # Boxes that hold nothing but optional fields, hidden as a whole.
        self._extra_groups: list[wx.Sizer] = []

        def group(caption: str, whole_group_is_extra: bool = False):
            """A captioned box holding one set of related fields.

            The caption is not decoration. A wxStaticBox is a real
            grouping in the accessibility tree, so a screen reader
            announces "Phone numbers" on entering the box and the fields
            inside gain a context they did not have when the form was one
            long ladder. The rounded, titled frame a sighted user sees and
            the spoken group name are the same thing, said two ways.
            """
            box = wx.StaticBox(self.scroll, label=caption)
            box.SetFont(theme.heading_font(box.GetFont()))
            box_sizer = wx.StaticBoxSizer(box, wx.VERTICAL)

            grid = wx.FlexGridSizer(cols=2, vgap=theme.GAP_TIGHT,
                                    hgap=theme.GAP_WIDE)
            grid.AddGrowableCol(1, 1)
            box_sizer.Add(grid, 1, wx.EXPAND | wx.ALL, theme.GAP)

            self.form.Add(box_sizer, 0, wx.EXPAND | wx.ALL, theme.GAP_TIGHT)
            if whole_group_is_extra:
                self._extra_groups.append(box_sizer)
            return box, grid

        def row(box, grid, caption: str, build, extra: bool = False) -> wx.Window:
            """Add a row: caption on one side, field on the other.

            The caption is created *before* the field, and this is not a
            matter of taste. Windows works out a field's name from the
            static text that comes before it among its siblings, so a
            caption created afterwards leaves every field announcing the
            previous row's caption — the field itself then seems, to a
            screen reader user, not to exist at all. The field is
            therefore built by the callback passed in here rather than
            handed over ready-made, because an argument would be
            evaluated first and put back in the wrong order.
            """
            label = wx.StaticText(box, label=caption)
            control = build(box)
            grid.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, theme.GAP_TIGHT)
            grid.Add(control, 0, wx.EXPAND | wx.ALL, theme.GAP_TIGHT)
            control.SetName(caption)
            if extra:
                self._extra_widgets.extend([label, control])
            return control

        phone_types = [t(label) for label in config.PHONE_LABELS]
        email_types = [t(label) for label in config.EMAIL_LABELS]

        def text_row(box, grid, caption, extra=False, **kwargs) -> wx.TextCtrl:
            return row(box, grid, caption,
                       lambda parent: wx.TextCtrl(parent, **kwargs), extra)

        def typed_row(box, grid, caption, choices, extra=False):
            """A value and the dropdown saying what kind of value it is."""
            field = text_row(box, grid, caption, extra)
            kind = row(box, grid, t("Type of {field}", field=caption.rstrip(":")),
                       lambda parent: wx.Choice(parent, choices=choices), extra)
            kind.SetSelection(0)
            return field, kind

        # ---- names ----
        box, grid = group(t("Name"))
        self.first_name = text_row(box, grid, t("First name:"))
        self.middle_name = text_row(box, grid, t("Middle name:"))
        self.family_name = text_row(box, grid, t("Last name:"))
        self.prefix = text_row(box, grid, t("Name prefix:"), extra=True)
        self.suffix = text_row(box, grid, t("Name suffix:"), extra=True)
        self.nickname = text_row(box, grid, t("Nickname:"), extra=True)

        # ---- phone numbers ----
        box, grid = group(t("Phone numbers"))

        # The country comes before the numbers, and not only because the
        # user asked for it there. A number typed as 01001234567 means
        # nothing on its own: the program needs to know where it is from
        # before it can tell a mistyped number from a foreign one, put
        # back a leading zero a spreadsheet ate, or write the +20 form
        # that Google and a travelling phone both want. Asking first, in
        # the reading order, is also how a screen reader user meets it.
        self._countries = list(phone_rules.COUNTRIES)
        arabic = i18n.get_language() == "ar"
        self.country = row(
            box, grid, t("Country:"),
            lambda parent: wx.Choice(
                parent,
                choices=[phone_rules.display_name(c, arabic) for c in self._countries],
            ),
        )
        self.country.SetSelection(self._country_index(self._remembered_country()))

        self.phone_fields = [
            typed_row(box, grid, t("Phone 1:"), phone_types),
            typed_row(box, grid, t("Phone 2:"), phone_types),
            typed_row(box, grid, t("Phone 3:"), phone_types, extra=True),
        ]

        # ---- the toggle, between what is always shown and the rest ----
        self.more_button = wx.Button(self.scroll, wx.ID_ANY, t("Show more fields"))
        icons.apply_to_button(self.more_button, "expand")
        self.form.Add(self.more_button, 0,
                      wx.ALIGN_LEFT | wx.ALL, theme.GAP)
        self.more_button.Bind(wx.EVT_BUTTON, self._on_toggle_more)

        # ---- everything below appears only when asked for ----
        box, grid = group(t("Email addresses"), whole_group_is_extra=True)
        self.email_fields = [
            typed_row(box, grid, t("Email 1:"), email_types, extra=True),
            typed_row(box, grid, t("Email 2:"), email_types, extra=True),
        ]

        box, grid = group(t("Organization"), whole_group_is_extra=True)
        self.organization = text_row(box, grid, t("Organization or school:"),
                                     extra=True)
        self.job_title = text_row(box, grid, t("Job title or class:"), extra=True)
        self.department = text_row(box, grid, t("Department or section:"),
                                   extra=True)

        box, grid = group(t("Other details"), whole_group_is_extra=True)
        self.labels = row(
            box, grid, t("Groups (separate with commas):"),
            lambda parent: wx.ComboBox(parent, choices=self.store.all_labels(),
                                       style=wx.CB_DROPDOWN),
            extra=True,
        )
        self.birthday = text_row(box, grid, t("Date of birth (year-month-day):"),
                                 extra=True)
        self.address = text_row(box, grid, t("Address:"), extra=True)
        self.website = text_row(box, grid, t("Website:"), extra=True)
        self.notes = text_row(box, grid, t("Notes:"), extra=True,
                              style=wx.TE_MULTILINE, size=(-1, 70))

        self.scroll.SetSizer(self.form)
        outer.Add(self.scroll, 1, wx.EXPAND | wx.ALL, theme.GAP)

        # A line reporting what just happened, for anyone who wants to
        # check the running total without leaving the form.
        # Hidden until it has something to report, so an empty line does
        # not reserve a band of grey across the bottom of the form.
        self.status = wx.StaticText(self, label="")
        self.status.SetName(t("Status"))
        self.status.Hide()
        outer.Add(self.status, 0,
                  wx.LEFT | wx.RIGHT | wx.BOTTOM, theme.MARGIN)

        outer.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.BOTTOM, theme.GAP)

        buttons = wx.BoxSizer(wx.HORIZONTAL)

        # Only offered when adding: editing works on one record.
        self.add_another_button = None
        if self.is_new:
            self.add_another_button = wx.Button(
                self, wx.ID_ANY, t("Add another contact")
            )
            icons.apply_to_button(self.add_another_button, "add")
            self.add_another_button.SetToolTip(
                t("Put this contact on the list and clear the form for the next one")
            )
            buttons.Add(self.add_another_button, 0, wx.LEFT, theme.MARGIN)
            self.add_another_button.Bind(wx.EVT_BUTTON, self._on_add_another)

        buttons.AddStretchSpacer()

        self.save_button = wx.Button(self, wx.ID_OK, t("Save"))
        self.cancel_button = wx.Button(self, wx.ID_CANCEL, t("Cancel"))
        icons.apply_to_button(self.save_button, "save")
        icons.apply_to_button(self.cancel_button, "cancel")
        buttons.Add(self.save_button, 0, wx.RIGHT, theme.GAP)
        buttons.Add(self.cancel_button, 0, wx.RIGHT, theme.MARGIN)

        outer.Add(buttons, 0, wx.EXPAND | wx.BOTTOM, theme.MARGIN)

        self.SetSizer(outer)

        # Paint everything first, then mark the primary button, so its
        # accent colour is not painted over a moment later.
        theme.apply_window(self)
        self._make_primary(self.save_button)

        self.SetAffirmativeId(wx.ID_OK)
        self.SetEscapeId(wx.ID_CANCEL)
        self.save_button.Bind(wx.EVT_BUTTON, self._on_save)
        self.cancel_button.Bind(wx.EVT_BUTTON, self._on_cancel)
        self.Bind(wx.EVT_CLOSE, self._on_close)

    def _make_primary(self, button: wx.Button) -> None:
        """Mark the one button that carries the screen's purpose.

        Three signals at once, because no single one reaches everybody:
        the accent colour and heavier text for the eye, and being the
        dialog's default button both for the keyboard — Enter runs it —
        and for a screen reader, which says so when reading the button.
        """
        button.SetDefault()
        button.SetFont(theme.heading_font(button.GetFont()))
        if not theme.is_high_contrast():
            accent = theme.accent_colour()
            button.SetBackgroundColour(accent)
            button.SetForegroundColour(
                wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHTTEXT)
            )

    # ------------------------------------------------------------ show more

    @staticmethod
    def _has_extra_data(contact: Contact) -> bool:
        """Whether any field in the optional half actually holds something."""
        return any([
            contact.prefix.strip(),
            contact.suffix.strip(),
            contact.nickname.strip(),
            contact.organization.strip(),
            contact.job_title.strip(),
            contact.department.strip(),
            contact.birthday.strip(),
            contact.notes.strip(),
            contact.labels,
            contact.emails,
            contact.address.strip(),
            contact.website.strip(),
            len(contact.phones) > PHONES_ALWAYS_SHOWN,
        ])

    def _apply_more_state(self, announce: bool = True) -> None:
        """Show or hide the optional half and relabel the toggle.

        The widgets are genuinely hidden rather than merely greyed out,
        so the tab order skips them entirely while the section is closed
        and a sighted user sees no trace of them either.
        """
        for widget in self._extra_widgets:
            widget.Show(self._showing_more)
        for box_sizer in self._extra_groups:
            self.form.Show(box_sizer, self._showing_more, recursive=True)

        self.more_button.SetLabel(
            t("Show fewer fields") if self._showing_more else t("Show more fields")
        )
        # The arrow turns over with the section, so the button says which
        # way it goes at a glance as well as in words.
        icons.apply_to_button(self.more_button,
                              "collapse" if self._showing_more else "expand")

        self._fit_to_content()

        if announce:
            self._announce(
                t("The extra fields are shown.") if self._showing_more
                else t("The extra fields are hidden.")
            )

    def _fit_to_content(self) -> None:
        """Size the window to what it actually holds.

        A fixed height leaves a slab of empty grey below the fields when
        the optional half is closed, and hides fields behind a scrollbar
        when it is open. So the scrolling area is told to ask for exactly
        the height of its contents, and the window is then fitted around
        the whole sizer — fields, status line, separator and buttons
        together. Past a fraction of the screen the request is capped and
        the scrollbar returns, which is the right answer rather than a
        window taller than the desktop.
        """
        self.form.Layout()
        content = self.form.GetMinSize()

        ceiling = int(wx.GetDisplaySize().height * 0.80)
        self.scroll.SetMinSize(wx.Size(-1, min(content.height + theme.GAP, ceiling)))

        sizer = self.GetSizer()
        sizer.Layout()
        fitting = sizer.ComputeFittingWindowSize(self)

        self.SetSize(wx.Size(
            max(fitting.width, self.GetSize().width, 560),
            min(fitting.height, int(wx.GetDisplaySize().height * 0.92)),
        ))

        self.scroll.FitInside()
        self.Layout()

    def _on_toggle_more(self, event: wx.CommandEvent) -> None:
        self._showing_more = not self._showing_more
        self._apply_more_state()

    # ------------------------------------------------------------ filling in

    def _fill(self, contact: Contact) -> None:
        """Put the contact's values into the fields."""
        self.first_name.SetValue(contact.given_name)
        self.middle_name.SetValue(contact.middle_name)
        self.family_name.SetValue(contact.family_name)
        self.prefix.SetValue(contact.prefix)
        self.suffix.SetValue(contact.suffix)
        self.nickname.SetValue(contact.nickname)
        self.organization.SetValue(contact.organization)
        self.job_title.SetValue(contact.job_title)
        self.department.SetValue(contact.department)
        self.birthday.SetValue(contact.birthday)
        self.notes.SetValue(contact.notes)
        self.labels.SetValue(i18n.list_separator().join(contact.labels))
        self.address.SetValue(contact.address)
        self.website.SetValue(contact.website)

        for index, (text, choice) in enumerate(self.phone_fields):
            if index < len(contact.phones):
                entry = contact.phones[index]
                text.SetValue(entry.value)
                self._select_label(choice, config.PHONE_LABELS, entry.label)

        for index, (text, choice) in enumerate(self.email_fields):
            if index < len(contact.emails):
                entry = contact.emails[index]
                text.SetValue(entry.value)
                self._select_label(choice, config.EMAIL_LABELS, entry.label)

        # A number that already carries a country code names its own
        # country, so the form opens on that one instead of the
        # remembered default. Editing a Saudi colleague should not start
        # by claiming they are in Egypt.
        for entry in contact.phones:
            found = phone_rules.guess_country(entry.value)
            if found is not None:
                self.country.SetSelection(self._country_index(found.code))
                break

    # -------------------------------------------------------------- country

    def _remembered_country(self) -> str:
        """Where to start: the country used last, or Egypt on a fresh copy."""
        if self.settings is not None:
            code = str(self.settings.get("country", phone_rules.DEFAULT_CODE))
            if phone_rules.get(code):
                return code
        return phone_rules.DEFAULT_CODE

    def _country_index(self, code: str) -> int:
        for index, country in enumerate(self._countries):
            if country.code == code:
                return index
        return 0

    def selected_country(self):
        """The country chosen in the form right now."""
        index = self.country.GetSelection()
        if 0 <= index < len(self._countries):
            return self._countries[index]
        return phone_rules.default()

    def _remember_country(self) -> None:
        """Make this contact's country the next contact's starting point.

        Somebody entering a class of thirty students picks Egypt once,
        not thirty times; somebody with one Saudi colleague changes it
        for that contact and it stays changed until they change it back,
        which is what a person would expect of a setting they can see.
        """
        if self.settings is not None:
            self.settings.set("country", self.selected_country().code)

    @staticmethod
    def _select_label(choice: wx.Choice, options: list[str], label: str) -> None:
        """Pick the right type, falling back to the first for unknown ones."""
        if label in options:
            choice.SetSelection(options.index(label))
        else:
            choice.SetSelection(0)

    def _clear_form(self) -> None:
        """Empty the form for the next contact, keeping the shared fields."""
        for control in (self.first_name, self.middle_name, self.family_name,
                        self.prefix, self.suffix, self.nickname,
                        self.birthday, self.notes, self.address, self.website):
            control.SetValue("")
        for text, choice in self.phone_fields:
            text.SetValue("")
            choice.SetSelection(0)
        for text, choice in self.email_fields:
            text.SetValue("")
            choice.SetSelection(0)

    # ------------------------------------------------------------ collecting

    def _collect(self) -> Contact:
        """Build the contact from the fields, keeping hidden values intact."""
        base = self.original.copy() if self.original else Contact()

        base.given_name = self.first_name.GetValue().strip()
        base.middle_name = self.middle_name.GetValue().strip()
        base.family_name = self.family_name.GetValue().strip()
        base.prefix = self.prefix.GetValue().strip()
        base.suffix = self.suffix.GetValue().strip()
        base.nickname = self.nickname.GetValue().strip()
        base.organization = self.organization.GetValue().strip()
        base.job_title = self.job_title.GetValue().strip()
        base.department = self.department.GetValue().strip()
        base.birthday = self.birthday.GetValue().strip()
        base.notes = self.notes.GetValue().strip()
        base.address = self.address.GetValue().strip()
        base.website = self.website.GetValue().strip()

        # Accept either comma, so users typing Arabic are not caught out.
        raw_labels = self.labels.GetValue().replace("،", ",")
        base.labels = [x.strip() for x in raw_labels.split(",") if x.strip()]

        # Visible values come from the form; anything past them is kept.
        # Each number goes through the repair first, so a number pasted
        # out of a spreadsheet with its leading zero eaten is put right
        # here rather than being stored wrong and dialled wrong later.
        country = self.selected_country()
        phones: list[Entry] = []
        for text, choice in self.phone_fields:
            value, _ = phone_rules.repair(text.GetValue(), country)
            if value:
                phones.append(
                    Entry(value=value, label=config.PHONE_LABELS[choice.GetSelection()])
                )
        old_phones = self.original.phones if self.original else []
        phones.extend(old_phones[VISIBLE_PHONES:])
        base.phones = phones

        emails: list[Entry] = []
        for text, choice in self.email_fields:
            value = textutil.clean_email(text.GetValue())
            if value:
                emails.append(
                    Entry(value=value, label=config.EMAIL_LABELS[choice.GetSelection()])
                )
        old_emails = self.original.emails if self.original else []
        emails.extend(old_emails[VISIBLE_EMAILS:])
        base.emails = emails

        return base

    def _form_is_empty(self, contact: Contact) -> bool:
        """Whether the identifying fields were left blank.

        The carried-over fields are ignored on purpose: an organization
        left in place from the previous entry does not by itself mean the
        user has started typing a new contact.
        """
        return not any([
            contact.full_name.strip(),
            contact.nickname.strip(),
            contact.phones,
            contact.emails,
            contact.notes.strip(),
        ])

    def _take_current(self) -> tuple[bool, tuple[Contact, Contact | None] | None]:
        """Validate and claim whatever is in the form right now.

        Returns (carry on, entry). The entry is None when the form was
        left blank, or when the contact was folded into one already on
        the list. Carry on is False when the user must fix something.
        """
        contact = self._collect()

        if self.is_new and self._form_is_empty(contact):
            return True, None

        if not self._validate(contact):
            return False, None

        # A duplicate of something already on this dialog's list.
        queued = self._find_queued_match(contact)
        if queued is not None:
            proceed, merge_target = self._resolve_duplicate(contact, queued,
                                                            in_batch=True)
            if not proceed:
                return False, None
            if merge_target is not None:
                merge_target.merge_from(contact)
                return True, None

        # A duplicate of something already saved in the database.
        ignore = self.original.local_id if self.original else None
        matches = self.store.find_strong_matches(contact, ignore_id=ignore)
        if matches:
            proceed, merge_target = self._resolve_duplicate(contact, matches[0])
            if not proceed:
                return False, None
            return True, (contact, merge_target)

        return True, (contact, None)

    def _find_queued_match(self, contact: Contact) -> Contact | None:
        """Find a contact already on the list sharing a number or address."""
        phones = contact.phone_keys()
        emails = contact.email_keys()
        if not phones and not emails:
            return None
        for queued, _ in self.entries:
            if (queued.phone_keys() & phones) or (queued.email_keys() & emails):
                return queued
        return None

    # ------------------------------------------------------------ actions

    def _announce(self, message: str) -> None:
        """Show a message on the form and speak it, since focus moves away.

        The line appears only when there is something on it, and the
        window grows by exactly its height rather than keeping an empty
        band in reserve.
        """
        self.status.SetLabel(message)
        self.status.Show(bool(message))
        a11y.speak(message)
        self._fit_to_content()

    def _update_save_label(self) -> None:
        count = len(self.entries)
        self.save_button.SetLabel(
            t("Save") if count == 0 else t("Save ({count} on the list)", count=count)
        )
        self.Layout()

    def _on_add_another(self, event: wx.CommandEvent) -> None:
        """Put the current entry on the list and clear the form."""
        contact = self._collect()
        if self._form_is_empty(contact):
            self._error(
                t("Fill in this contact before adding another one."),
                self.first_name,
            )
            return

        proceed, entry = self._take_current()
        if not proceed:
            return

        if entry is not None:
            self.entries.append(entry)

        self._clear_form()
        self._update_save_label()
        self.first_name.SetFocus()
        self._announce(
            t("{count} contacts on the list. The form is clear; the "
              "organization and group were kept.", count=len(self.entries))
        )

    def _on_save(self, event: wx.CommandEvent) -> None:
        proceed, entry = self._take_current()
        if not proceed:
            return

        self._remember_country()

        if entry is not None:
            self.entries.append(entry)
            if self.is_new:
                self._clear_form()
                self._update_save_label()

        if not self.entries:
            self._error(
                t("Enter at least a name, a phone number, or an email address."),
                self.first_name,
            )
            return

        # One contact is the ordinary case and saves without ceremony.
        if len(self.entries) == 1:
            self.EndModal(wx.ID_OK)
            return

        answer = self._confirm_batch()
        if answer == wx.ID_YES:
            self.EndModal(wx.ID_OK)
        elif answer == wx.ID_NO:
            self.first_name.SetFocus()
            self._announce(
                t("{count} contacts are waiting. Carry on adding.",
                  count=len(self.entries))
            )

    def _confirm_batch(self) -> int:
        """Ask before writing several contacts at once."""
        names = "\n".join(
            "  - " + display_label(contact.display_name)
            for contact, _ in self.entries[:20]
        )
        if len(self.entries) > 20:
            names += "\n  " + t("... and {count} more.",
                                count=len(self.entries) - 20)

        message = "\n\n".join([
            t("{count} contacts are about to be saved:", count=len(self.entries)),
            names,
            t("Save them all, or add another one first?"),
        ])
        dialog = wx.MessageDialog(
            self, message, t("Confirm saving"),
            wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION,
        )
        dialog.SetYesNoCancelLabels(
            t("Save them all"), t("Add another"), t("Cancel")
        )
        answer = dialog.ShowModal()
        dialog.Destroy()
        return answer

    def _on_cancel(self, event: wx.CommandEvent) -> None:
        if self._confirm_discard():
            self.EndModal(wx.ID_CANCEL)

    def _on_close(self, event: wx.CloseEvent) -> None:
        if self._confirm_discard():
            event.Skip()

    def _confirm_discard(self) -> bool:
        """Warn before throwing away contacts waiting on the list."""
        if not self.entries:
            return True
        answer = wx.MessageBox(
            t("{count} contacts on the list have not been saved yet and will "
              "be lost.\n\nDiscard them?", count=len(self.entries)),
            t("Unsaved contacts"), wx.YES_NO | wx.ICON_WARNING, self,
        )
        return answer == wx.YES

    # ------------------------------------------------------------ checking

    def _first_problem(self, contact: Contact):
        """The first thing wrong with the entry, or None if nothing is.

        Returns the message to show, the field to put the cursor back in,
        and whether the hidden half has to be opened first so that focus
        does not land somewhere invisible.

        This is kept apart from `_validate` because the two do different
        jobs: deciding whether an entry is acceptable is a question with
        an answer, while telling the user about it opens a message box.
        Mixed together, the decision could not be checked without a
        window appearing — and a message box waits for a click, which in
        a test never comes, so the test hangs for as long as anyone is
        willing to wait.
        """
        if not contact.full_name and not contact.phones and not contact.emails:
            return (
                t("Enter at least a name, a phone number, or an email address."),
                self.first_name,
                False,
            )

        for entry in contact.emails:
            if not textutil.is_valid_email(entry.value):
                return (
                    t("The address '{value}' does not look right. It should "
                      "look like name@example.com", value=entry.value),
                    self.email_fields[0][0],
                    True,
                )

        return None

    def _validate(self, contact: Contact) -> bool:
        """Check the entry before saving, telling the user what is wrong."""
        problem = self._first_problem(contact)
        if problem is not None:
            message, focus, reveal = problem
            if reveal:
                self._reveal_extras()
            self._error(message, focus)
            return False

        for entry in contact.phones:
            if not textutil.is_valid_phone(entry.value):
                answer = wx.MessageBox(
                    t("The number '{value}' looks unusual — it has an "
                      "unexpected number of digits.\n\nSave it as it is?",
                      value=entry.value),
                    t("Unusual number"), wx.YES_NO | wx.ICON_QUESTION, self,
                )
                if answer != wx.YES:
                    self.phone_fields[0][0].SetFocus()
                    return False
                break

        return True

    def _reveal_extras(self) -> None:
        """Open the hidden half, so focus never lands on an unseen field."""
        if not self._showing_more:
            self._showing_more = True
            self._apply_more_state(announce=False)

    def _resolve_duplicate(self, contact: Contact, existing: Contact,
                           in_batch: bool = False) -> tuple[bool, Contact | None]:
        """Ask what to do when the number or address already exists.

        Returns (carry on, contact to merge into). Carrying on with no
        merge target means saving this as a separate contact.
        """
        shared = contact.phone_keys() & existing.phone_keys()
        reason = t("the same phone number") if shared else t("the same email address")

        heading = (
            t("A contact with {reason} is already on this list:", reason=reason)
            if in_batch
            else t("A contact with {reason} already exists:", reason=reason)
        )

        message = "\n\n".join([
            heading,
            "\n".join([
                t("Name: {value}", value=display_label(existing.display_name)),
                t("Phone: {value}", value=existing.primary_phone or t("none")),
                t("Email: {value}", value=existing.primary_email or t("none")),
            ]),
            t("What would you like to do?"),
        ])
        dialog = wx.MessageDialog(
            self, message, t("Duplicate contact"),
            wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION,
        )
        dialog.SetYesNoCancelLabels(
            t("Merge with the existing one"),
            t("Save as a separate contact"),
            t("Go back and edit"),
        )
        answer = dialog.ShowModal()
        dialog.Destroy()

        if answer == wx.ID_YES:
            return True, existing
        if answer == wx.ID_NO:
            return True, None

        self.first_name.SetFocus()
        return False, None

    def _error(self, message: str, focus: wx.Window | None = None) -> None:
        """Show an error. Screen readers read a dialog box in full."""
        wx.MessageBox(message, t("Incomplete entry"), wx.OK | wx.ICON_ERROR, self)
        if focus is not None:
            focus.SetFocus()
