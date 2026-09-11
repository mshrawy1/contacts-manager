# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Choosing what a spreadsheet's columns mean.

A CSV exported from Google needs no screen like this, because its
columns are named things the program already knows. A spreadsheet from a
school or a company needs one badly: its columns are named whatever
somebody typed, its headings may be on the fourth row under a letterhead,
and its contacts may be on the third of five tabs.

The program guesses all of that and shows the guesses here for the user
to correct. That is the whole design. A guess the user can see and
change is a small annoyance; the same guess made silently produces a
database of wrong data that nobody notices for months.

The screen is built as captioned rows rather than a grid, because a grid
of dropdowns is something a screen reader user has to explore cell by
cell, while a ladder of "Column B, student name, for example Ahmed
Mahmoud Sayed" followed by a dropdown is read in one pass by simply
pressing Tab.
"""

from __future__ import annotations

import wx

from .. import i18n, phones, xlsx_import
from ..i18n import t
from . import icons, theme

# How much of a sample value to show beside a column's heading. Long
# enough to recognise the column, short enough that a screen reader is
# not reading a paragraph before reaching the dropdown.
SAMPLE_LENGTH = 30


class SheetImportDialog(wx.Dialog):
    """Pick the sheet, the header row, the country, and the columns."""

    def __init__(self, parent: wx.Window, plans: list[xlsx_import.SheetPlan],
                 country_code: str = "") -> None:
        super().__init__(
            parent, title=t("Import from a spreadsheet"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            size=(700, 640),
        )
        if i18n.is_rtl():
            self.SetLayoutDirection(wx.Layout_RightToLeft)

        self.plans = plans
        self.current = xlsx_import.best_sheet(plans) if plans else 0
        self._countries = list(phones.COUNTRIES)
        self._column_choices: list[wx.Choice] = []

        arabic = i18n.get_language() == "ar"
        self._field_labels = [t(label) for _, label in xlsx_import.FIELD_CHOICES]
        self._field_keys = [key for key, _ in xlsx_import.FIELD_CHOICES]
        self._country_labels = [
            phones.display_name(c, arabic) for c in self._countries
        ]

        self._build()
        self._select_country(country_code or phones.DEFAULT_CODE)
        self._load_sheet()

        self.SetMinSize(wx.Size(560, 420))
        self.CentreOnParent()
        self.sheet_choice.SetFocus()

    # ------------------------------------------------------------ building

    def _build(self) -> None:
        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)

        # ---- what to read ----
        top_box = wx.StaticBox(panel, label=t("What to read"))
        top_box.SetFont(theme.heading_font(top_box.GetFont()))
        top = wx.StaticBoxSizer(top_box, wx.VERTICAL)
        grid = wx.FlexGridSizer(cols=2, vgap=theme.GAP_TIGHT, hgap=theme.GAP_WIDE)
        grid.AddGrowableCol(1, 1)

        def row(caption: str, build):
            """Caption first, then the field, so the field is named by it."""
            label = wx.StaticText(top_box, label=caption)
            control = build(top_box)
            grid.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, theme.GAP_TIGHT)
            grid.Add(control, 0, wx.EXPAND | wx.ALL, theme.GAP_TIGHT)
            control.SetName(caption)
            return control

        self.sheet_choice = row(
            t("Sheet:"),
            lambda p: wx.Choice(p, choices=[plan.name for plan in self.plans]),
        )
        self.sheet_choice.SetSelection(self.current)

        self.header_spin = row(
            t("Row holding the column titles:"),
            lambda p: wx.SpinCtrl(p, min=0, max=1000, initial=1),
        )

        self.country_choice = row(
            t("Phone numbers in this file are from:"),
            lambda p: wx.Choice(p, choices=self._country_labels),
        )

        top.Add(grid, 1, wx.EXPAND | wx.ALL, theme.GAP)
        outer.Add(top, 0, wx.EXPAND | wx.ALL, theme.GAP)

        # ---- the state of the sheet, in words ----
        self.summary = wx.StaticText(panel, label="")
        self.summary.SetName(t("Summary"))
        outer.Add(self.summary, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.MARGIN)

        # ---- one row per column ----
        columns_box = wx.StaticBox(panel, label=t("What each column holds"))
        columns_box.SetFont(theme.heading_font(columns_box.GetFont()))
        self.columns_sizer = wx.StaticBoxSizer(columns_box, wx.VERTICAL)
        self.columns_box = columns_box

        self.scroll = wx.ScrolledWindow(columns_box, style=wx.VSCROLL)
        self.scroll.SetScrollRate(0, 12)
        self.scroll_sizer = wx.BoxSizer(wx.VERTICAL)
        self.scroll.SetSizer(self.scroll_sizer)
        self.columns_sizer.Add(self.scroll, 1, wx.EXPAND | wx.ALL, theme.GAP)
        outer.Add(self.columns_sizer, 1, wx.EXPAND | wx.ALL, theme.GAP)

        # ---- buttons ----
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.ok_button = wx.Button(panel, wx.ID_OK, t("Import"))
        cancel = wx.Button(panel, wx.ID_CANCEL, t("Cancel"))
        icons.apply_to_button(self.ok_button, "import")
        icons.apply_to_button(cancel, "cancel")
        self.ok_button.SetDefault()
        buttons.AddStretchSpacer()
        buttons.Add(self.ok_button, 0, wx.ALL, theme.GAP_TIGHT)
        buttons.Add(cancel, 0, wx.ALL, theme.GAP_TIGHT)
        outer.Add(buttons, 0, wx.EXPAND | wx.ALL, theme.GAP_TIGHT)

        panel.SetSizer(outer)
        theme.apply_window(self)

        self.sheet_choice.Bind(wx.EVT_CHOICE, self._on_sheet)
        self.header_spin.Bind(wx.EVT_SPINCTRL, self._on_header_row)

    # ------------------------------------------------------------ filling

    def _select_country(self, code: str) -> None:
        for index, country in enumerate(self._countries):
            if country.code == code:
                self.country_choice.SetSelection(index)
                return
        self.country_choice.SetSelection(0)

    def selected_country(self):
        index = self.country_choice.GetSelection()
        if 0 <= index < len(self._countries):
            return self._countries[index]
        return phones.default()

    @property
    def plan(self) -> xlsx_import.SheetPlan:
        return self.plans[self.current]

    def _sample_for(self, column: int) -> str:
        """The first real value in a column, for recognising it by eye."""
        for row in self.plan.preview(6):
            if column < len(row) and row[column].strip():
                text = " ".join(row[column].split())
                if len(text) > SAMPLE_LENGTH:
                    return text[:SAMPLE_LENGTH] + "…"
                return text
        return ""

    def _load_sheet(self) -> None:
        """Rebuild the column rows for whichever sheet is now chosen."""
        plan = self.plan

        # The spin control counts rows the way a person does, from one,
        # and zero means the sheet has no titles at all.
        self.header_spin.SetValue(plan.header_row + 1 if plan.header_row >= 0 else 0)
        self.header_spin.SetMax(max(1, len(plan.rows)))

        self._rebuild_columns()

    def _rebuild_columns(self) -> None:
        """Draw one captioned dropdown for every column in the sheet."""
        self.scroll_sizer.Clear(delete_windows=True)
        self._column_choices = []
        plan = self.plan
        headings = plan.headers

        for index, heading in enumerate(headings):
            sample = self._sample_for(index)
            shown = heading.strip() or t("(no title)")
            letter = xlsx_import.column_letter(index)
            if sample:
                caption = t("Column {letter}: {title} — for example {sample}",
                            letter=letter, title=shown, sample=sample)
            else:
                caption = t("Column {letter}: {title} — empty",
                            letter=letter, title=shown)

            label = wx.StaticText(self.scroll, label=caption)
            choice = wx.Choice(self.scroll, choices=self._field_labels)
            choice.SetName(caption)

            key = plan.mapping.get(index, xlsx_import.IGNORE)
            choice.SetSelection(
                self._field_keys.index(key) if key in self._field_keys else 0
            )

            # An identity number is never importable, by any mapping, so
            # the dropdown is fixed rather than merely defaulted: leaving
            # it changeable would invite the one mistake that matters.
            if xlsx_import.is_sensitive_header(heading):
                choice.SetSelection(0)
                choice.Enable(False)
                label.SetLabel(caption + " — " + t("identity number, not imported"))

            choice.Bind(wx.EVT_CHOICE, self._on_column_changed)
            self.scroll_sizer.Add(label, 0, wx.EXPAND | wx.LEFT | wx.TOP, theme.GAP)
            self.scroll_sizer.Add(choice, 0, wx.EXPAND | wx.ALL, theme.GAP_TIGHT)
            self._column_choices.append(choice)

        self.scroll.Layout()
        self.scroll.FitInside()
        self._update_summary()

    # ------------------------------------------------------------ events

    def _on_sheet(self, event: wx.CommandEvent) -> None:
        self.current = self.sheet_choice.GetSelection()
        self._load_sheet()

    def _on_header_row(self, event: wx.CommandEvent) -> None:
        """Move the header and guess the columns again from the new one."""
        plan = self.plan
        plan.header_row = self.header_spin.GetValue() - 1
        plan.mapping = xlsx_import.guess_mapping(plan.headers)
        self._rebuild_columns()

    def _on_column_changed(self, event: wx.CommandEvent) -> None:
        self._collect_mapping()
        self._update_summary()

    def _collect_mapping(self) -> None:
        """Copy the dropdowns back into the plan."""
        mapping: dict[int, str] = {}
        for index, choice in enumerate(self._column_choices):
            selection = choice.GetSelection()
            if 0 <= selection < len(self._field_keys):
                mapping[index] = self._field_keys[selection]
        self.plan.mapping = mapping

    def _update_summary(self) -> None:
        """Say in plain words what will happen if Import is pressed now."""
        plan = self.plan
        mapped = sum(1 for key in plan.mapping.values() if key)
        rows = len(plan.preview(100000))
        if not rows:
            text = t("This sheet has no rows to import.")
        elif not mapped:
            text = t("No column is being imported yet. Choose what at least "
                     "one column holds.")
        else:
            text = t("{rows} rows, {columns} columns being imported.",
                     rows=rows, columns=mapped)
        self.summary.SetLabel(text)
        self.ok_button.Enable(bool(rows and mapped))

    # ------------------------------------------------------------ result

    def result(self) -> tuple[xlsx_import.SheetPlan, object]:
        """The chosen plan and country, read after the dialog closes."""
        self._collect_mapping()
        return self.plan, self.selected_country()
