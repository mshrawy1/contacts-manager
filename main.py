# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Entry point for Contacts Manager.

Run it directly:

    python main.py

or double-click ``run.bat``.
"""

from __future__ import annotations

import sys
import traceback
from datetime import datetime

import wx

from app import config, i18n, settings as settings_module
from app.ui import theme
from app.i18n import t
from app.settings import Settings
from app.store import Store
from app.ui.main_frame import MainFrame


def _log_error(text: str) -> None:
    """Write the details to a file so they can be looked at afterwards."""
    try:
        with open(config.LOG_FILE, "a", encoding="utf-8") as handle:
            handle.write(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} =====\n")
            handle.write(text)
    except OSError:
        pass


def _show_error(text: str) -> None:
    """Show the error in a window, where a screen reader will read it,
    rather than in a console the user never sees."""
    _log_error(text)
    lines = text.strip().splitlines()
    message = "\n\n".join([
        t("Something unexpected went wrong."),
        lines[-1] if lines else t("Unknown error"),
        t("The full details were saved to:") + f"\n{config.LOG_FILE}",
    ])
    try:
        wx.MessageBox(message, t("Error"), wx.OK | wx.ICON_ERROR)
    except Exception:  # noqa: BLE001 (wx itself may be unusable)
        print(message, file=sys.stderr)


def _excepthook(exc_type, exc_value, exc_tb) -> None:
    """Make sure no failure closes the program in silence."""
    _show_error("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))


class ContactsApp(wx.App):
    """The wx application."""

    def OnInit(self) -> bool:  # noqa: N802 (wx name)
        self.SetAppName(config.APP_ID)
        self.store = Store()
        self.settings = Settings()

        # Older versions kept the language inside the contacts database.
        # Lift it into the settings file once, then leave the database
        # holding nothing but contacts.
        settings_module.migrate_from_database(self.store, self.settings)

        # The saved preference wins over the system language.
        saved = str(self.settings.get("language", ""))
        if saved:
            i18n.set_language(saved)

        theme.set_mode(str(self.settings.get("appearance", "dark")))

        frame = MainFrame(self.store, self.settings)
        frame.Show()
        self.SetTopWindow(frame)
        return True


def _selftest() -> int:
    """Check a built copy really works, and write the findings to a file.

    A packaged program has no console, so problems that only appear once
    it is bundled — a translation catalogue left out, a database that
    cannot be created — would otherwise be invisible. Run:

        ContactsManager-1.1.exe --selftest

    then read selftest.txt in the program's data folder.
    """
    from app.store import Store

    results: list[tuple[str, bool, str]] = []

    def check(label: str, condition: bool, detail: object = "") -> None:
        results.append((label, bool(condition), str(detail)))

    check("data folder is writable", config.data_dir().exists(), config.data_dir())

    probe = Settings()
    check("settings file is separate from the database",
          probe.save() and probe.path.exists() and probe.path != config.DB_FILE,
          probe.path)

    languages = i18n.available_languages()
    check("both languages are offered", set(languages) == {"en", "ar"}, languages)

    i18n.set_language("en")
    check("English returns the source text", i18n.t("New contact") == "New contact")

    i18n.set_language("ar")
    arabic = i18n.t("New contact")
    check("Arabic catalogue is bundled and loaded",
          arabic == "جهة اتصال جديدة", arabic)
    check("Arabic is right to left", i18n.is_rtl())
    check("placeholders still work",
          i18n.t("{count} contacts.", count=5) == "5 جهة اتصال.",
          i18n.t("{count} contacts.", count=5))
    i18n.set_language("en")

    # Reading a workbook leans on zipfile and xml.etree, and on the two
    # spreadsheet modules being bundled at all. A workbook is built here
    # in memory rather than carried around as a file, so the check needs
    # nothing beside the program and still fails loudly if the bundle is
    # missing a piece.
    try:
        import io
        import zipfile

        from app import xlsx_io

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "xl/workbook.xml",
                '<?xml version="1.0"?><workbook xmlns="http://schemas.'
                'openxmlformats.org/spreadsheetml/2006/main"><sheets>'
                '<sheet name="probe" sheetId="1"/></sheets></workbook>',
            )
            archive.writestr(
                "xl/worksheets/sheet1.xml",
                '<?xml version="1.0"?><worksheet xmlns="http://schemas.'
                'openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                '<row r="1"><c r="A1" t="inlineStr"><is><t>مرحبا</t></is></c>'
                '<c r="B1"><v>1001234567</v></c></row>'
                "</sheetData></worksheet>",
            )
        buffer.seek(0)
        rows = xlsx_io.read_sheet(buffer).rows
        check("spreadsheet reading works", rows == [["مرحبا", "1001234567"]], rows)
    except Exception as error:  # noqa: BLE001
        check("spreadsheet reading works", False, error)

    try:
        from app import phones

        fixed, note = phones.repair("1001234567", phones.get("EG"))
        check("phone repair works", fixed == "01001234567" and bool(note), fixed)
        check("the country list is bundled", len(phones.COUNTRIES) > 20,
              len(phones.COUNTRIES))
    except Exception as error:  # noqa: BLE001
        check("phone repair works", False, error)

    try:
        store = Store()
        count = store.count()
        store.close()
        check("database opens", True, f"{count} contacts")
    except Exception as error:  # noqa: BLE001
        check("database opens", False, error)

    passed = all(ok for _, ok, _ in results)
    lines = [f"{config.APP_NAME} {config.APP_VERSION} self-test", ""]
    for label, ok, detail in results:
        lines.append(f"{'PASS' if ok else 'FAIL'}  {label}"
                     + (f"  -> {detail}" if detail else ""))
    lines += ["", "ALL PASSED" if passed else "SOMETHING FAILED"]
    report = "\n".join(lines)

    target = config.data_dir() / "selftest.txt"
    target.write_text(report, encoding="utf-8")
    print(report)
    return 0 if passed else 1


def main() -> int:
    sys.excepthook = _excepthook

    if "--selftest" in sys.argv:
        return _selftest()

    try:
        app = ContactsApp(redirect=False)
    except Exception:  # noqa: BLE001
        _show_error(traceback.format_exc())
        return 1
    app.MainLoop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
