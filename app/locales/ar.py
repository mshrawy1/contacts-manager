# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""Arabic translation catalogue.

Keys are the English source strings exactly as written in the code.
Placeholders in braces must be kept, but may be reordered freely.

The wording is Modern Standard Arabic throughout. No colloquial forms
are used, so the text reads correctly for any Arabic speaker and is
pronounced properly by a screen reader.
"""

TRANSLATIONS = {
    # ---------- application ----------
    "Contacts Manager": "مدير جهات الاتصال",
    "Version {version}": "الإصدار {version}",
    "A program for managing contacts locally on your computer, "
    "with CSV and vCard import and export.":
        "برنامج لإدارة جهات الاتصال محلياً على جهازك، مع استيراد وتصدير "
        "ملفات CSV و vCard.",

    # ---------- value types ----------
    "Mobile": "المحمول",
    "Home": "المنزل",
    "Work": "العمل",
    "Main": "الرئيسي",
    "Work Fax": "فاكس العمل",
    "Home Fax": "فاكس المنزل",
    "Other": "أخرى",

    # ---------- menus ----------
    "File": "ملف",
    "Contacts": "جهات الاتصال",
    "View": "عرض",
    "Tools": "أدوات",
    "Help": "مساعدة",
    "Language": "اللغة",

    # ---------- appearance ----------
    "Appearance": "المظهر",
    "Follow Windows": "حسب إعداد ويندوز",
    "Light": "فاتح",
    "Dark": "داكن",
    "Appearance changed to {name}.": "تم تغيير المظهر إلى: {name}.",
    "About": "عن البرنامج",
    "Exit": "خروج",
    "Import from a file...": "استيراد من ملف...",
    "Export to a file...": "تصدير إلى ملف...",
    "Back up now": "إنشاء نسخة احتياطية الآن",
    "Save a copy of the database": "حفظ نسخة من قاعدة البيانات",
    "Read contacts from a CSV or vCard file":
        "قراءة جهات الاتصال من ملف CSV أو vCard",
    "Save contacts to a CSV or vCard file":
        "حفظ جهات الاتصال في ملف CSV أو vCard",
    "Find duplicates...": "البحث عن المكرر...",
    "Deleted items...": "سلة المحذوفات...",
    "Groups...": "المجموعات...",
    "Create, rename and delete groups": "إنشاء المجموعات وإعادة تسميتها وحذفها",

    # ---------- managing groups ----------
    "Manage groups": "إدارة المجموعات",
    "Groups:": "المجموعات:",
    "Group": "المجموعة",
    "Members": "عدد جهات الاتصال",
    "New group": "مجموعة جديدة",
    "Rename": "إعادة تسمية",
    "Rename group": "إعادة تسمية المجموعة",
    "Delete group": "حذف المجموعة",
    "Name already used": "الاسم مستخدم بالفعل",
    "{count} groups.": "{count} مجموعة.",
    "Name for the new group:": "اسم المجموعة الجديدة:",
    "New name for '{name}':": "الاسم الجديد لـ«{name}»:",
    "There is already a group called '{name}'.":
        "توجد مجموعة بهذا الاسم بالفعل: «{name}».",
    "There are no groups yet. Make one here, or type one into a contact.":
        "لا توجد مجموعات بعد. أنشئ واحدة من هنا، أو اكتب اسمها داخل جهة اتصال.",
    "Added the group '{name}'.": "تمت إضافة المجموعة «{name}».",
    "Renamed to '{name}'. {count} contacts were updated.":
        "أُعيدت التسمية إلى «{name}»، وتم تحديث {count} جهة اتصال.",
    "Deleted the group '{name}'.": "تم حذف المجموعة «{name}».",
    "The group '{name}' will be removed from {count} contacts.\n\n"
    "The contacts themselves are not deleted — only the group is.\n\n"
    "Go ahead?":
        "ستُزال المجموعة «{name}» من {count} جهة اتصال.\n\n"
        "لن تُحذف جهات الاتصال نفسها، بل المجموعة فقط.\n\n"
        "هل تريد المتابعة؟",
    "Keyboard shortcuts": "اختصارات لوحة المفاتيح",

    # ---------- main window ----------
    "Search:": "بحث:",
    "Search contacts": "البحث في جهات الاتصال",
    "Group:": "المجموعة:",
    "Filter by group": "التصفية حسب المجموعة",
    "All groups": "كل المجموعات",
    "Contacts table": "جدول جهات الاتصال",
    "Name": "الاسم",
    "Email": "البريد الإلكتروني",
    "Organization": "الجهة",
    "Class or job title": "الصف أو الوظيفة",
    "Groups": "المجموعات",
    "Phone": "الهاتف",
    "{shown} of {total}": "{shown} من {total}",

    # ---------- buttons ----------
    "New": "جديد",
    "Edit": "تعديل",
    "Delete": "حذف",
    "Select all": "تحديد الكل",
    "Duplicates": "المكرر",
    "Import": "استيراد",
    "Export": "تصدير",
    "Save": "حفظ",
    "Cancel": "إلغاء",
    "Close": "إغلاق",
    "Copy": "نسخ",
    "Copy text": "نسخ النص",
    "Done": "تم",
    "Enter": "Enter",

    # ---------- commands ----------
    "New contact": "جهة اتصال جديدة",
    "Edit the selected contact": "تعديل جهة الاتصال المحددة",
    "Delete the selected contacts": "حذف جهات الاتصال المحددة",
    "Delete the selected contacts (while in the table)":
        "حذف جهات الاتصال المحددة (أثناء وجودك في الجدول)",
    "Edit the selected contact (while in the table)":
        "تعديل جهة الاتصال المحددة (أثناء وجودك في الجدول)",
    "Select every contact": "تحديد كل جهات الاتصال",
    "Select every contact currently listed":
        "تحديد كل جهات الاتصال المعروضة حالياً",
    "Select every contact (while in the table)":
        "تحديد كل جهات الاتصال (أثناء وجودك في الجدول)",
    "Go to the search box": "الانتقال إلى حقل البحث",
    "Go to the contacts table": "الانتقال إلى جدول جهات الاتصال",
    "Refresh the list": "تحديث القائمة",
    "Import from a file": "استيراد من ملف",
    "Export to a file": "تصدير إلى ملف",
    "Find duplicates": "البحث عن المكرر",
    "Deleted items": "سلة المحذوفات",
    "Repeat the last message": "إعادة قراءة آخر رسالة",
    "Show this screen": "عرض هذه الشاشة",

    # ---------- selection ----------
    "Selected all {count} contacts.":
        "تم تحديد كل جهات الاتصال، وعددها {count}.",
    "There is nothing to select.": "لا يوجد ما يمكن تحديده.",

    # ---------- contact form ----------
    "Phone numbers": "أرقام الهاتف",
    "Email addresses": "عناوين البريد الإلكتروني",
    "Other details": "تفاصيل أخرى",
    "Edit: {name}": "تعديل: {name}",
    "First name:": "الاسم الأول:",
    "Last name:": "اسم العائلة:",
    "Middle name:": "الاسم الأوسط:",
    "Phone 1:": "الهاتف ١:",
    "Phone 2:": "الهاتف ٢:",
    "Phone 3:": "الهاتف ٣:",
    "Email 1:": "البريد الإلكتروني ١:",
    "Email 2:": "البريد الإلكتروني ٢:",
    "Type of {field}": "نوع {field}",
    "Name prefix:": "لقب الاسم:",
    "Name suffix:": "لاحقة الاسم:",
    "Organization or school:": "الجهة أو المدرسة:",
    "Job title or class:": "الوظيفة أو الصف:",
    "Department or section:": "القسم أو الشعبة:",
    "Groups (separate with commas):": "المجموعات (افصل بينها بفاصلة):",
    "Date of birth (year-month-day):": "تاريخ الميلاد (سنة-شهر-يوم):",
    "Address:": "العنوان:",
    "Website:": "الموقع الإلكتروني:",
    "Nickname:": "الاسم المستعار:",
    "Notes:": "ملاحظات:",
    "Status": "الحالة",
    "Show more fields": "عرض المزيد من الحقول",
    "Show fewer fields": "إخفاء الحقول الإضافية",
    "The extra fields are shown.": "تم عرض الحقول الإضافية.",
    "The extra fields are hidden.": "تم إخفاء الحقول الإضافية.",
    "(no name)": "(بدون اسم)",
    "none": "لا يوجد",

    # ---------- adding several ----------
    "Add another contact": "إضافة جهة اتصال أخرى",
    "Put this contact on the list and clear the form for the next one":
        "إضافة جهة الاتصال هذه إلى القائمة وإفراغ النموذج لإدخال التالية",
    "Save ({count} on the list)": "حفظ ({count} في القائمة)",
    "Fill in this contact before adding another one.":
        "أكمل بيانات جهة الاتصال الحالية قبل إضافة أخرى.",
    "{count} contacts on the list. The form is clear; the organization "
    "and group were kept.":
        "{count} جهة اتصال في القائمة. تم إفراغ النموذج مع الإبقاء على "
        "الجهة والمجموعة.",
    "{count} contacts are about to be saved:":
        "أنت على وشك حفظ {count} جهة اتصال:",
    "Save them all, or add another one first?":
        "هل تريد حفظها جميعاً، أم إضافة جهة اتصال أخرى أولاً؟",
    "Confirm saving": "تأكيد الحفظ",
    "Save them all": "حفظ الجميع",
    "Add another": "إضافة أخرى",
    "{count} contacts are waiting. Carry on adding.":
        "{count} جهة اتصال في الانتظار. تابع الإضافة.",
    "{count} contacts on the list have not been saved yet and will be "
    "lost.\n\nDiscard them?":
        "{count} جهة اتصال في القائمة لم تُحفظ بعد وسوف تُفقد.\n\n"
        "هل تريد تجاهلها؟",
    "Unsaved contacts": "جهات اتصال غير محفوظة",

    # ---------- validation ----------
    "Incomplete entry": "بيانات ناقصة",
    "Enter at least a name, a phone number, or an email address.":
        "أدخل على الأقل اسماً أو رقم هاتف أو بريداً إلكترونياً.",
    "The address '{value}' does not look right. It should look like "
    "name@example.com":
        "البريد الإلكتروني «{value}» غير صحيح. ينبغي أن يكون على هيئة "
        "name@example.com",
    "The number '{value}' looks unusual — it has an unexpected number of "
    "digits.\n\nSave it as it is?":
        "الرقم «{value}» غير معتاد؛ عدد خاناته غير متوقع.\n\n"
        "هل تريد حفظه كما هو؟",
    "Unusual number": "رقم غير معتاد",

    # ---------- duplicates ----------
    "Duplicate contact": "جهة اتصال مكررة",
    "Duplicate contacts": "جهات الاتصال المكررة",
    "A contact with {reason} already exists:":
        "توجد جهة اتصال مسجلة مسبقاً بـ{reason}:",
    "A contact with {reason} is already on this list:":
        "توجد جهة اتصال في هذه القائمة بـ{reason}:",
    "the same phone number": "نفس رقم الهاتف",
    "the same email address": "نفس البريد الإلكتروني",
    "Name: {value}": "الاسم: {value}",
    "Phone: {value}": "الهاتف: {value}",
    "Email: {value}": "البريد الإلكتروني: {value}",
    "What would you like to do?": "ماذا تريد أن تفعل؟",
    "Merge with the existing one": "الدمج مع الموجودة",
    "Save as a separate contact": "الحفظ كجهة اتصال منفصلة",
    "Go back and edit": "العودة إلى التعديل",
    "Duplicate groups": "المجموعات المكررة",
    "Duplicate groups:": "المجموعات المكررة:",
    "Names": "الأسماء",
    "Count": "العدد",
    "Why they match": "سبب التشابه",
    "same phone number": "نفس رقم الهاتف",
    "same email address": "نفس البريد الإلكتروني",
    "exactly the same name": "نفس الاسم تماماً",
    "Also treat people with exactly the same name as duplicates "
    "(check these carefully)":
        "اعتبار من يحملون نفس الاسم تماماً مكررين أيضاً (راجعهم بعناية)",
    "Found {count} duplicate groups.": "تم العثور على {count} مجموعة مكررة.",
    "No duplicate contacts found.": "لا توجد جهات اتصال مكررة.",
    "Merge selected group": "دمج المجموعة المحددة",
    "Merge every group": "دمج كل المجموعات",
    "Select a group first.": "اختر مجموعة أولاً.",
    "Nothing selected": "لم يتم تحديد شيء",
    "These will all be merged into '{name}':":
        "سيتم دمجها جميعاً في «{name}»:",
    "no phone": "بدون رقم",
    "no email": "بدون بريد إلكتروني",
    "Missing details are carried over, and nothing is lost. All right?":
        "سيتم نقل البيانات الناقصة، ولن يُفقد شيء. هل تريد المتابعة؟",
    "Confirm merge": "تأكيد الدمج",
    "Merged.": "تم الدمج.",
    "{count} groups will be merged, each into its first member.":
        "سيتم دمج {count} مجموعة، كل مجموعة في أول عنصر فيها.",
    "A backup was taken beforehand, and anything removed goes to "
    "deleted items.":
        "تم إنشاء نسخة احتياطية مسبقاً، وكل ما يُزال ينتقل إلى سلة المحذوفات.",
    "Merged {count} groups.": "تم دمج {count} مجموعة.",
    "Carry on?": "هل تريد المتابعة؟",
    "{count} more": "و{count} غيرهم",

    # ---------- deleted items ----------
    "Deleted contacts": "جهات الاتصال المحذوفة",
    "Deleted on": "تاريخ الحذف",
    "Restore selected": "استعادة المحدد",
    "Empty permanently": "إفراغ السلة نهائياً",
    "{count} deleted contacts.": "تحتوي السلة على {count} جهة اتصال.",
    "Nothing has been deleted.": "سلة المحذوفات فارغة.",
    "'{name}' is back.": "تمت استعادة «{name}».",
    "Restored": "تمت الاستعادة",
    "Restored {count} contacts.": "تمت استعادة {count} جهة اتصال.",
    "{count} contacts will be erased permanently and cannot be brought "
    "back.\n\nAre you sure?":
        "سيتم محو {count} جهة اتصال نهائياً دون إمكانية استعادتها.\n\n"
        "هل أنت متأكد؟",
    "Empty deleted items": "إفراغ سلة المحذوفات",

    # ---------- import and export ----------
    "Choose a contacts file": "اختر ملف جهات الاتصال",
    "All supported files": "كل الملفات المدعومة",
    "CSV files": "ملفات CSV",
    "vCard files": "ملفات vCard",
    "CSV file for Google and Excel": "ملف CSV لجوجل وإكسل",
    "vCard file for phones": "ملف vCard للهواتف",
    "Save the file as": "حفظ الملف باسم",
    "The file could not be read:": "تعذرت قراءة الملف:",
    "The file could not be written:": "تعذرت كتابة الملف:",
    "Read error": "خطأ في القراءة",
    "Save error": "خطأ في الحفظ",
    "The file holds no contacts.": "الملف لا يحتوي على أي جهات اتصال.",
    "Empty file": "ملف فارغ",
    "Empty": "فارغ",
    "The file holds {count} contacts.":
        "يحتوي الملف على {count} جهة اتصال.",
    "If one of them has the same number or address as a contact you "
    "already have, what should happen?":
        "إذا كان أحدها يحمل نفس الرقم أو البريد الإلكتروني لجهة اتصال موجودة "
        "لديك، فما الإجراء المطلوب؟",
    "Import method": "طريقة الاستيراد",
    "Merge: fill in what is missing (best)":
        "الدمج: إكمال البيانات الناقصة في الموجودة (الأفضل)",
    "Skip: leave existing contacts alone":
        "التخطي: ترك جهات الاتصال الموجودة كما هي",
    "Add everything: keep duplicates too":
        "إضافة الكل: إضافة المكرر أيضاً",
    "Import cancelled.": "تم إلغاء الاستيراد.",
    "Export cancelled.": "تم إلغاء التصدير.",
    "Import result": "نتيجة الاستيراد",
    "Something went wrong during the import and nothing was changed:":
        "حدث خطأ أثناء الاستيراد ولم يتم تغيير أي شيء:",
    "Import finished. Added {added}, merged {merged}, skipped {skipped}.":
        "انتهى الاستيراد. تمت إضافة {added}، ودمج {merged}، وتخطي {skipped}.",
    "What should be exported?": "ما الذي تريد تصديره؟",
    "Export range": "نطاق التصدير",
    "All contacts ({count})": "كل جهات الاتصال ({count})",
    "Only what is listed now ({count})": "المعروض حالياً فقط ({count})",
    "Only the selected ({count})": "المحدد فقط ({count})",
    "There is nothing to export.": "لا يوجد ما يمكن تصديره.",
    "Exported": "تم التصدير",
    "Exported {count} contacts to {name}.":
        "تم تصدير {count} جهة اتصال إلى {name}.",
    "{count} contacts saved to:": "تم حفظ {count} جهة اتصال في:",
    "You can upload this file to Google Contacts from its import page.":
        "يمكنك رفع هذا الملف إلى Google Contacts من صفحة الاستيراد.",
    "You can open this file on any phone to add the contacts.":
        "يمكنك فتح هذا الملف على أي هاتف لإضافة جهات الاتصال.",
    "File type '{suffix}' is not supported. The program reads .csv and "
    ".vcf files only.":
        "نوع الملف «{suffix}» غير مدعوم. يقرأ البرنامج ملفات ‎.csv‎ و‎.vcf‎ فقط.",
    "File type '{suffix}' is not supported for export. Choose .csv or "
    ".vcf.":
        "نوع الملف «{suffix}» غير مدعوم للتصدير. اختر ‎.csv‎ أو ‎.vcf‎.",
    "no extension": "بدون امتداد",

    # ---------- import report ----------
    "Read from the file: {count} contacts.":
        "تمت القراءة من الملف: {count} جهة اتصال.",
    "Added as new: {count}.": "أُضيفت كجديدة: {count}.",
    "Merged into existing: {count}.": "دُمجت مع موجودة: {count}.",
    "Skipped: {count}.": "تم تخطيها: {count}.",
    "Note: {count} of these names already existed with different phone "
    "numbers. They were added as separate contacts so that different "
    "people are not merged by mistake. The names are:":
        "تنبيه: {count} من هذه الأسماء كانت موجودة مسبقاً بأرقام مختلفة. "
        "أُضيفت كجهات اتصال منفصلة تفادياً لدمج أشخاص مختلفين عن طريق الخطأ. "
        "والأسماء هي:",
    "Columns in the file that were not recognized and ignored:":
        "أعمدة في الملف لم يتعرف عليها البرنامج فتم تجاهلها:",
    "A backup was saved before importing: {path}":
        "تم حفظ نسخة احتياطية قبل الاستيراد في: {path}",
    "... and {count} more.": "... و{count} غيرها.",

    # ---------- saving and deleting ----------
    "Select a contact first.": "اختر جهة اتصال أولاً.",
    "Added '{name}'.": "تمت إضافة «{name}».",
    "Saved '{name}'.": "تم حفظ «{name}».",
    "Merged into '{name}'.": "تم الدمج مع «{name}».",
    "Saved {added} contacts, merged {merged}.":
        "تم حفظ {added} جهة اتصال، ودمج {merged}.",
    "Confirm deletion": "تأكيد الحذف",
    "Go ahead?": "هل تريد المتابعة؟",
    "Deletion cancelled.": "تم إلغاء الحذف.",
    "'{name}' will be deleted.\n\nYou will find it in deleted items and "
    "can bring it back.":
        "سيتم حذف «{name}».\n\nستجدها في سلة المحذوفات ويمكنك استعادتها.",
    "{count} contacts will be deleted.\n\nYou will find them in deleted "
    "items and can bring them back.":
        "سيتم حذف {count} جهة اتصال.\n\nستجدها في سلة المحذوفات ويمكنك "
        "استعادتها.",
    "Deleted '{name}'. You can restore it from deleted items.":
        "تم حذف «{name}». يمكنك استعادتها من سلة المحذوفات.",
    "Deleted {count} contacts.": "تم حذف {count} جهة اتصال.",

    # ---------- backup ----------
    "Backup": "نسخة احتياطية",
    "Backup saved.": "تم حفظ نسخة احتياطية.",
    "There is no data to back up.": "لا توجد بيانات لحفظها.",
    "A copy was saved to:": "تم حفظ نسخة في:",

    # ---------- counts and status ----------
    "{count} contacts.": "{count} جهة اتصال.",
    "{count} results.": "{count} نتيجة.",
    "{count} results for {query}.": "{count} نتيجة للبحث عن {query}.",
    "Nothing has happened yet.": "لم تتم أي إجراءات بعد.",
    "Copied.": "تم النسخ.",
    "Language changed to {name}.": "تم تغيير اللغة إلى {name}.",

    # ---------- about ----------
    "License: {name}": "الترخيص: {name}",
    "This program is free software: you may pass it on and change it "
    "under the terms of the GNU General Public License. It comes with no "
    "warranty whatsoever, to the extent the law allows.":
        "هذا البرنامج حر: لك أن تنقله وأن تعدّله وفق شروط رخصة جنو "
        "العمومية العامة. ويأتي دون أي ضمان على الإطلاق، إلى المدى الذي "
        "يسمح به القانون.",
    "The full license is in the file LICENSE, distributed with the "
    "program, and at https://www.gnu.org/licenses/gpl-3.0.html":
        "نص الرخصة الكامل في ملف LICENSE المرفق بالبرنامج، وعلى "
        "https://www.gnu.org/licenses/gpl-3.0.html",
    "Number of contacts: {count}": "عدد جهات الاتصال: {count}",
    "Database: {path}": "قاعدة البيانات: {path}",
    "Settings: {path}": "الإعدادات: {path}",
    "Backups: {path}": "النسخ الاحتياطية: {path}",
    "Direct NVDA connection: {state}": "الاتصال المباشر بـ NVDA: {state}",
    "connected": "متصل",
    "not connected": "غير متصل",

    # ---------- help ----------
    "Keyboard shortcuts:": "اختصارات لوحة المفاتيح:",
    "Notes:": "ملاحظات:",
    "* To add several contacts in one go, open a new contact and use the "
    "plus button, Add another contact. The form clears for the next one "
    "but keeps the organization, class and group.":
        "* لإضافة عدة جهات اتصال دفعة واحدة، افتح جهة اتصال جديدة واستخدم زر "
        "علامة الزائد «إضافة جهة اتصال أخرى». يُفرَّغ النموذج لإدخال التالية "
        "مع الإبقاء على الجهة والصف والمجموعة.",
    "* Search finds a name however its hamza or diacritics are written, "
    "and finds a number whether you type it in Arabic or Latin digits, "
    "with a leading zero or a country code.":
        "* يعثر البحث على الاسم مهما كان شكل الهمزة أو التشكيل، ويعثر على "
        "الرقم سواء كتبته بالأرقام العربية أو اللاتينية، وبصفر في البداية أو "
        "برمز الدولة.",
    "* In the table, type the first letter of a name to jump to it.":
        "* في الجدول، اكتب الحرف الأول من الاسم للانتقال إليه مباشرة.",
    "* To select a few: Shift with the arrow keys, or Ctrl with the "
    "space bar.":
        "* لتحديد عدد قليل: Shift مع مفاتيح الأسهم، أو Ctrl مع مفتاح المسافة.",

    # ---------- errors ----------
    "Error": "خطأ",
    "Something unexpected went wrong.": "حدث خطأ غير متوقع في البرنامج.",
    "Unknown error": "خطأ غير معروف",
    "The full details were saved to:": "تم حفظ التفاصيل الكاملة في:",
}
