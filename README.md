# Contacts Manager

A Windows program for managing contacts locally on your own machine,
built from the start to work properly with screen readers — **NVDA** in
particular.

It reads and writes **CSV**, **vCard** and **Excel** files — the same
formats Google Contacts, Outlook and a phone export and import. You
export the file yourself and you import it yourself. The program has no
networking code in it at all: it asks for no account, signs in to
nothing, and sends nothing anywhere.

Available in **English** and **Arabic**, switchable from inside the
program.

*[اقرأ هذا الملف بالعربية](README.ar.md)*

---

## Why files instead of connecting to a Google account

* **No password ever passes through the program.** You export the file
  yourself, from your own browser, already signed in.
* **Nothing breaks unexpectedly.** A direct connection stops working the
  moment Google asks for two-step verification or changes a permission.
* **You see everything before it happens.** You review the file before
  uploading it, so no change reaches your account unnoticed.
* **It works offline.** All the data is on your machine.

---

## Getting started

### The portable program (recommended)

Take the `ContactsManagerV1.1.exe` file and put it wherever you like — including a
USB stick. Nothing needs installing, and Python is not required.

On first run it creates a `ContactsManagerData` folder beside itself
holding the database and the backups, so the whole thing travels
together. If the program sits somewhere it cannot write to, it falls
back to `%APPDATA%\ContactsManager` instead.

### Running from source

Install Python 3.10 or newer from <https://www.python.org/downloads/>,
ticking **Add python.exe to PATH** during setup. Then:

```bash
python -m pip install -r requirements.txt
```

```bash
python main.py
```

or double-click `run.bat`.

### Building the .exe yourself

```bash
python -m pip install pyinstaller
```

```bash
python -m PyInstaller ContactsManager.spec --noconfirm --clean
```

or double-click `build_exe.bat`. The result is a single self-contained
file in `dist`, named with its version, about 17 MB.

To confirm a build is sound — that both languages are packed in and the
database can be created — run it once with a flag:

```bash
ContactsManagerV1.1.exe --selftest
```

It writes `selftest.txt` into the program's data folder and exits.

---

## The first time you run it

Windows shows **"Windows protected your PC"** the first time. This is not
a fault and not a virus warning: Windows says it about *any* program that
has not been signed with a paid certificate, whatever is inside it.

To run it: click **More info**, then **Run anyway**. Windows remembers,
and will not ask again.

To stop it happening at all on this machine, clear the mark Windows put
on the file when it was downloaded: right-click the `.exe` →
**Properties** → tick **Unblock** → **OK**. Or from PowerShell:

```bash
Unblock-File -Path .\ContactsManagerV1.1.exe
```

Nothing else removes the warning for everybody. That takes a code signing
certificate — around $300 to $600 a year for the EV kind that SmartScreen
trusts straight away — bought against a registered identity. The program
does carry its name, version and description in the file itself, so
**More info** shows what it is rather than a blank.

---

## Working with Google Contacts

### Bringing your contacts in

1. Open <https://contacts.google.com> signed in to your account.
2. Choose **Export** from the side menu.
3. Pick **Google CSV** — or **vCard** if you also want it on a phone.
4. In the program: **File → Import from a file**, or `Ctrl+I`.
5. You will be asked what to do about contacts you already have. Choose
   **Merge** to fill in missing details without erasing anything.

### Sending your changes back

1. **File → Export to a file**, or `Ctrl+S`.
2. Choose what to export: everything, only what is listed, or only what
   is selected.
3. Save it as a **`.csv`** file.
4. At <https://contacts.google.com>, choose **Import** and upload it.

> **Worth knowing:** Google adds what is in the file and never removes
> what is missing from it. So deleting someone here does not delete them
> at Google — do that yourself. And re-uploading people who are already
> there can create duplicates; Google's own **Merge & fix** page cleans
> those up.

### Phones

Export as **`.vcf`**, send the file to yourself or copy it across, and
open it on the phone.

---

## What the program reads

File shapes are recognized without being told which is which:

| Format | Example columns |
|---|---|
| Newer Google CSV | `First Name`, `Phone 1 - Value`, `Labels` |
| Older Google CSV | `Given Name`, `Phone 1 - Type`, `Group Membership` |
| Outlook CSV | `Mobile Phone`, `Business Phone`, `E-mail Address` |
| A plain Arabic file you wrote | `الاسم`, `الموبايل`, `البريد`, `المجموعة` |
| vCard 2.1 / 3.0 / 4.0 | anything a phone exports |
| Excel `.xlsx` | whatever the institution happened to type |

### Excel workbooks

A spreadsheet from a school or a company is not an export format, so it
gets a screen of its own. The program reads the workbook, works out which
tab holds the contacts, finds the row of headings even when it sits under
two rows of letterhead, guesses what each column means, and then shows
you every guess to correct before anything is imported.

Three things it deals with that catch people out:

* **Leading zeros that Excel has eaten.** A cell holding `01001234567`
  in an ordinary number format is stored as the number `1001234567`, and
  the zero is gone from the file itself, not just from the display. Every
  number in such a column is wrong, and nobody finds out until somebody
  tries to place a call. Telling the program which country the numbers
  are from lets it put the zero back — and only where the arithmetic
  leaves no doubt, so a foreign number in the same column is left alone.
* **Identity numbers.** If a sheet carries a national ID column, it is
  never imported, under any mapping, and the import report says so. A
  national ID is not contact data, and contacts here are made to be
  uploaded to Google.
* **Dates, formulas and errors.** A birthday stored as Excel's day count
  is read as a date; a formula's result is read; an `#N/A` is read as an
  empty cell rather than as somebody's name.

The older binary `.xls` is not supported. Open it in Excel and save it
as `.xlsx`.

### Phone numbers and countries

The contact form asks which country a number belongs to, before the
number itself. It defaults to whatever you chose last, so a run of
entries costs no extra clicks.

Exported files get the international form, `+20 100 123 4567`, because
that is what Google Contacts prefers and what still dials when its owner
is abroad. The contacts kept in the program keep the local form you
typed.

Handled automatically:

* **`QUOTED-PRINTABLE` encoding**, which otherwise mangles Arabic in
  files exported from phones.
* **`windows-1256`**, the encoding older Arabic Excel writes.
* **Arabic-Indic digits** `٠١٠٠١٢٣٤٥٦٧`, converted to Latin ones.
* **Semicolons** used as the column separator instead of commas.

---

## Searching

Search is forgiving rather than literal:

* **Diacritics do not matter:** «محمّد» finds «محمد».
* **Hamza shape does not matter:** «احمد» finds «أحمد», «يحيي» finds
  «يحيى», «فاطمه» finds «فاطمة».
* **Number format does not matter:** `01001234567`, `+201001234567` and
  `٠١٠٠ ١٢٣ ٤٥٦٧` all find the same person.
* **Several words at once:** «محمد النيل» finds Mohamed at Nile School.

---

## Light and dark

The program is **dark out of the box**, because it is used for long
stretches of data entry and a dark ground is easier on the eyes over an
hour of it. **View → Appearance** offers Dark, Light, or Follow Windows,
and the choice is remembered.

The icons are drawn in the text colour rather than shipped as pictures,
so they turn light on a dark ground and dark on a light one by
themselves. There is no second set of artwork to fall out of step.

The colours were measured, not guessed: text sits at **13.5 to 1**
against the dark ground and **21 to 1** against the light one, both past
the strictest level the accessibility guidelines ask for. The banded
rows shift the ground by about a tenth, enough for the eye to follow a
line across and far too little to touch the contrast of the text on it.

**A high contrast theme overrules all of this.** If Windows is running
one, the program leaves every colour alone and greys out the Appearance
menu: those colours were chosen by someone who needs exactly them, and
painting over them takes away the reason they were turned on.

One honest limit: the drop-down *list* that opens from a combo box is
drawn by Windows itself and stays light. The closed control is dark; the
list that drops out of it is not.

---

## How it looks

The window is arranged for the eye as carefully as it is for the ear,
and neither was allowed to cost the other anything.

* **A toolbar across the top** carries New, Edit, Delete, Select all,
  Import, Export, Groups and Duplicates — each with its picture and its
  words. It is a real Windows toolbar, so a screen reader already knows
  what it is, and its tools run the same commands as the menus.
* **The search box has a band of its own**, tinted a shade away from the
  list, set in slightly larger type, with a magnifier beside it.
* **Rows are taller and every other one is tinted**, which makes a long
  line easier to follow across to the far column. The tint is worked out
  from the system palette, so it follows a dark theme, and it is dropped
  entirely under a high contrast theme — those themes promise a fixed
  set of colours and decoration must not break the promise.
* **The contact form is grouped into captioned boxes** — Name, Phone
  numbers, Email addresses, Organization, Other details. The frames a
  sighted user sees are the same groupings a screen reader announces on
  entering them, so this is a gain for both at once.
* **The form is exactly as tall as its contents.** Opening the extra
  fields grows it, closing them shrinks it back, and the status line
  appears only when it has something to say. No band of empty grey.
* **Save is marked as the primary action** three ways over: the accent
  colour and heavier text for the eye, and being the default button both
  for the keyboard, where Enter runs it, and for a screen reader, which
  says so when reading it.

None of this costs anything measurable. Drawing a full screen of banded
rows takes a tenth of a millisecond, the icons are rasterised once and
kept, and the main window opens in the same time it did before any of it
was added. `python tests/benchmark.py` prints the figures.

---

## The list

The table shows the same columns Google Contacts does, in the same
order: **name, email, phone, job title, organization, groups**.

---

## Groups

A group is a thing in its own right, not just text typed into a contact.
**Contacts → Groups**, or `Ctrl+G`, lists every group with how many
people are in it, and lets you create, rename and delete them.

* A group can be **created empty** and filled later.
* Typing a new group name into a contact **creates it**, so it is there
  in the filter next time.
* A group **survives losing its last member** — it is not deleted just
  because nobody is in it any more.
* **Renaming** changes the name on every contact carrying it.
* **Deleting** takes the group off those contacts. The contacts
  themselves are never deleted; the warning says so before you confirm.

The **Group** box above the list filters by any of them, and works
alongside the search box: search text and group are applied together.

---

## The contact form

The fields follow the order Google Contacts uses for its own columns, so
importing, editing and exporting all present the same information in the
same sequence:

> first name, middle name, last name, name prefix, name suffix, nickname,
> organization, job title, department, birthday, notes, groups, email
> addresses, phone numbers, address, website.

Only the **three name fields and the first two phone numbers** are shown
to begin with. Everything else sits behind **Show more fields**, because
an ordinary entry needs a name and a number and nothing else, and a short
form is far quicker to move through with a screen reader.

Hidden fields are genuinely hidden, so `Tab` skips them entirely. Opening
a contact that already has any of them filled in reveals them
automatically — nothing is ever concealed from its owner.

---

## Adding many contacts quickly

Open a new contact (`Ctrl+N`) and fill it in. Then, instead of saving,
press **+ Add another contact**.

The entry joins a list, the form clears — but the **organization, class
and group stay filled in**, since a run of students from one classroom
shares them. Keep going for as many as you like.

The Save button carries a running count, so tabbing to it tells you
where you stand: *Save (7 on the list)*. Pressing it shows every name
about to be written and offers **Save them all**, **Add another**, or
**Cancel**. Saving a single contact skips the confirmation entirely.

Closing the form with contacts still waiting asks before discarding them.

---

## Keyboard shortcuts

| Key | Action |
|---|---|
| `Ctrl+N` | New contact |
| `Ctrl+E` or `Enter` | Edit the selected contact |
| `Delete` | Delete the selected contacts (while in the table) |
| `Ctrl+A` | Select every contact (while in the table) |
| `Ctrl+F` | Go to the search box |
| `Ctrl+L` | Go to the contacts table |
| `Ctrl+I` | Import from a file |
| `Ctrl+S` | Export to a file |
| `Ctrl+G` | Manage groups |
| `Ctrl+D` | Find duplicates |
| `Ctrl+T` | Deleted items |
| `Ctrl+J` | Repeat the last message |
| `F5` | Refresh the list |
| `F1` | Help |

`Ctrl+A` knows where you are: in the search box it selects the text, in
the table it selects every contact listed.

---

## Guarding against mistakes

* **Nothing is deleted outright.** Deletions go to **Deleted items**
  (`Ctrl+T`) and can be brought back.
* **Automatic backups** before every import or bulk merge. The last 20
  are kept.
* **Duplicate warnings while saving.** Entering a number that already
  exists tells you whose it is and offers to merge, keep both, or go
  back and edit. This works against contacts already saved *and* against
  ones still waiting on the list.
* **Identical names are never merged automatically.** Names like
  «محمد أحمد» belong to many different people, so merging happens only
  on a matching phone number or email address. Name matches are reported
  and left alone.

---

## Icons

Every button and menu entry carries a picture beside its words, so the
program is quick to use by eye as well as by ear. The icons come from two
places on purpose:

* **Material Symbols** — the set Google Contacts itself is drawn with —
  for everything to do with managing contacts: add a person, merge
  duplicates, import, export, labels, expand. Anyone who already uses
  Google Contacts recognises them at once, which is the point of
  borrowing them. Google publishes this set under the Apache License 2.0;
  the licence ships as `LICENSE-material-icons.txt` and the artwork is
  embedded unmodified in `app/ui/material_icons.py`, so the program needs
  no image files and no network.
* **Windows stock icons** for the plain verbs every dialog on the system
  shares — save, cancel, close, copy. A Save button should look like
  every other Save button on the machine.

An icon never replaces a label. Removing the words would hurt everyone:
a screen reader would have nothing to announce, and a sighted user would
be left guessing at a picture. The drawings are painted in the system's
button-text colour, so they stay legible in a dark or high-contrast theme.

---

## Screen readers

The program is written with **wxPython**, which draws real Windows
controls — the same toolkit **NVDA's own interface** is built with. The
table, buttons, fields and menus are therefore read like any ordinary
Windows program.

Every field has its caption written immediately before it, so tabbing
onto a field announces what it is.

### Spoken announcements (optional)

Results — *35 contacts added* — go to the status bar, and `Ctrl+J`
replays the last one at any time.

To have them spoken **the moment they happen**, put
`nvdaControllerClient64.dll` beside the program. It ships with NVDA, and
is also in NV Access's `nvdaControllerClient` package.

The program works fully without it; this is an improvement, not a
requirement. **Help → About** reports whether the direct connection is
live.

---

## Changing language

**Tools → Language**, then English or العربية. The window rebuilds
immediately, and right-to-left layout follows the Arabic setting. The
choice is remembered.

On first run the language is taken from Windows.

---

## Where the data lives

| Running as | Location |
|---|---|
| The portable `.exe` | `ContactsManagerData` beside the program |
| From source, or a read-only location | `%APPDATA%\ContactsManager` |

| File | What it is |
|---|---|
| `contacts.db` | the contacts, and nothing else |
| `settings.json` | program settings, such as the chosen language |
| `backups\` | automatic backups, the last 20 |
| `app.log` | error details, if anything goes wrong |

Contacts and settings are deliberately kept apart, so the contacts file
can be handed to someone else, restored from a backup, or replaced
outright without dragging one person's preferences along with it. The
only thing the database records about itself is its schema version, which
has to travel with it for upgrades to work.

To move to another machine, copy `contacts.db` — or export a CSV.

### Removing it

There is no installer, so there is nothing to uninstall. Delete the
`.exe`, and delete the `ContactsManagerData` folder beside it. If the
program had fallen back to the per-user location, that folder is
`%APPDATA%\ContactsManager`.

Nothing else is left behind: no registry entries, no Start menu items,
no services, no scheduled tasks, nothing written outside those two
places.

---

## Privacy

**The program collects nothing and sends nothing.**

This is not a promise about intent; it is a statement about what is in
the code. There is no networking code in the program at all — no HTTP
client, no sockets, no telemetry, no crash reporting, no update check.
Nothing is uploaded, and there is no server to upload it to.

Your contacts live in a file on your own machine. They leave it only when
you export them yourself, to a file you choose, in a place you choose.

The program asks for no account and no password, and signs in to nothing.
The reason it exchanges contacts with Google through files rather than by
connecting to the account is precisely this: nothing has to be trusted
with a credential that never exists.

The only file the program writes outside its own data folder is the one
you point it at when exporting.

---

## Code signing

Releases before this point were built on the maintainer's own computer
and were not signed, which is why Windows shows a SmartScreen warning the
first time one is run.

Builds are now produced by [GitHub
Actions](https://github.com/mshrawy1/contacts-manager/actions) on a
clean, GitHub-hosted machine, from a public checkout of this repository,
with the test suite run first and the resulting file's SHA-256 printed
into a public log. Anyone can compare what they downloaded against what
the build produced without taking anybody's word for it.

### Code signing policy

This project intends to have its Windows binaries signed through the free
code signing provided to open source projects by [SignPath
Foundation](https://signpath.org/), using the [SignPath.io](https://signpath.io/)
platform. Signing is carried out on SignPath's infrastructure; no signing
key is held by this project or by anyone working on it.

**Roles.** This is a single-maintainer project, so the roles defined by
SignPath are all held by the same person:

| Role | Who |
|---|---|
| Author | Mahmoud Shrawy |
| Reviewer | Mahmoud Shrawy |
| Approver | Mahmoud Shrawy |

**Privacy.** The program collects no data of any kind and has no
networking code; see the Privacy section above. Nothing about a user
reaches this project, SignPath, or anybody else.

**What gets signed.** Only files built by the workflow in this
repository, from the source in this repository, on GitHub-hosted
machines. Nothing built anywhere else is submitted for signing.

---

## Tests

```bash
python tests/run_all.py
```

or double-click `run_tests.bat`. 388 checks across nine files cover
Arabic text normalization, vCard and CSV reading and writing, the
database and merge logic, the settings file, the icons, translation
completeness, and the building of every window.

Translation coverage is enforced: `tests/test_i18n.py` reads the source,
collects every string passed to `t()`, and fails if any lacks a
translation or if a translation loses a placeholder.

To measure speed:

```bash
python tests/benchmark.py
```

---

## License

Contacts Manager is free software under the **GNU General Public License,
version 3 or later**. The full text is in [LICENSE](LICENSE).

In short: you may use it, read it, change it and pass it on. If you pass
on a changed version, it has to carry the same freedoms and its source
has to come with it. There is no warranty.

**Why version 3 and not version 2.** The icons are Google's Material
Symbols under Apache 2.0, and that licence is compatible with GPLv3 but
not with GPLv2 — its patent clause counts as an extra restriction under
the older licence. Version 3 is what makes shipping those icons lawful.

Everything the program uses that somebody else wrote, and why each piece
fits with the GPL, is set out in
[THIRD-PARTY-LICENSES.md](THIRD-PARTY-LICENSES.md).

---

## Project layout

```
main.py                entry point (--selftest checks a build)
ContactsManager.spec   build description for the single .exe
build_exe.bat          build with a double-click
run.bat                run from source with a double-click
requirements.txt       what to install
LICENSE-material-icons.txt   Apache 2.0, for the Material Symbols

app/
  config.py            paths and constants
  settings.py          the settings file, kept apart from the database
  i18n.py              translation layer; English is the source
  locales/ar.py        Arabic catalogue
  textutil.py          Arabic text and digit normalization
  models.py            the contact model and merge logic
  store.py             SQLite, searching, duplicate detection
  csv_io.py            CSV in Google's shape
  vcf_io.py            vCard reading and writing
  importer.py          unified import and export
  ui/
    a11y.py            screen reader helpers
    theme.py           colours, spacing and fonts, from the system
    icons.py           button and menu icons, from two sets
    material_icons.py  the embedded Material Symbols artwork
    main_frame.py      the main window
    contact_dialog.py  the add and edit form
    dialogs.py         reports, deleted items, duplicates

tests/                 the test suite and the benchmark
```

---

## Adding another language

1. Copy `app/locales/ar.py` to `app/locales/<code>.py` and translate the
   values, leaving the English keys untouched.
2. Add the code and the language's own name to `LANGUAGES` in
   `app/i18n.py`.
3. Add the code to `RTL_LANGUAGES` there if it reads right to left.
4. Run the tests — anything you missed will be listed by name.
