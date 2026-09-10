# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mahmoud Shrawy
"""قياس سرعة البرنامج على أحجام بيانات مختلفة.

للتشغيل:

    python tests/benchmark.py

بيقيس العمليات اللي المستخدم بيحسّها فعلاً: فتح البرنامج، تحميل
القائمة، البحث وانت بتكتب، والاستيراد.
"""

from __future__ import annotations

import gc
import random
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

FIRST = ["محمد", "أحمد", "محمود", "مصطفى", "سارة", "منى", "ليلى", "عمر",
         "خالد", "يوسف", "إبراهيم", "علي", "حسن", "فاطمة", "نور", "مريم"]
LAST = ["أحمد", "سيد", "عبد الرحمن", "مصطفى", "إبراهيم", "حسن", "علي",
        "محمود", "سليمان", "الشريف", "زغلول", "فاروق"]
SCHOOLS = ["مدرسة النيل", "مدرسة المستقبل", "مدرسة النور", "مدرسة الأمل"]
GRADES = ["الصف الأول", "الصف الثاني", "الصف الثالث"]
GROUPS = ["طلاب 2026", "طلاب 2025", "أولياء أمور", "معلمين"]


def make_contacts(count: int, seed: int = 7):
    """يولّد جهات اتصال شبه حقيقية، بأرقام مختلفة عشان مايتدمجوش."""
    from app.models import Contact, Entry

    rng = random.Random(seed)
    out = []
    for index in range(count):
        phone = f"010{index:08d}"
        contact = Contact(
            given_name=rng.choice(FIRST),
            family_name=rng.choice(LAST),
            phones=[Entry(phone, "Mobile")],
            emails=[Entry(f"user{index}@example.com", "Home")],
            organization=rng.choice(SCHOOLS),
            job_title=rng.choice(GRADES),
            labels=[rng.choice(GROUPS)],
            notes="ملاحظة تجريبية عن الطالب",
        )
        out.append(contact)
    return out


def timed(label: str, function, repeat: int = 1) -> float:
    """يشغّل العملية ويرجّع أسرع زمن بالملي ثانية."""
    gc.collect()
    times = []
    for _ in range(repeat):
        start = time.perf_counter()
        function()
        times.append((time.perf_counter() - start) * 1000)
    best = min(times)
    median = statistics.median(times)
    flag = "  <-- بطيء" if best > 300 else ""
    print(f"  {label:<38} {best:8.1f} ms   (وسيط {median:7.1f}){flag}")
    return best


def bench_startup() -> None:
    """زمن تحميل المكتبات، وده أكبر جزء من زمن فتح البرنامج."""
    print("\n== زمن الاستيراد (مرة واحدة عند التشغيل) ==")

    code = (
        "import time;"
        "s=time.perf_counter();"
        "import wx;"
        "print(round((time.perf_counter()-s)*1000,1))"
    )
    import subprocess

    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    print(f"  {'استيراد wxPython':<38} {float(result.stdout.strip()):8.1f} ms")

    code2 = (
        "import sys,time;"
        f"sys.path.insert(0,r'{Path(__file__).resolve().parent.parent}');"
        "s=time.perf_counter();"
        "import app.ui.main_frame;"
        "print(round((time.perf_counter()-s)*1000,1))"
    )
    result2 = subprocess.run([sys.executable, "-c", code2], capture_output=True, text=True)
    print(f"  {'استيراد البرنامج كله':<38} {float(result2.stdout.strip()):8.1f} ms")


def bench_size(count: int) -> None:
    """يقيس العمليات الأساسية على حجم بيانات معيّن."""
    from app.store import Store

    print(f"\n== {count} جهة اتصال ==")

    db = Path(tempfile.gettempdir()) / f"bench_{count}.db"
    for leftover in db.parent.glob(f"bench_{count}.db*"):
        leftover.unlink(missing_ok=True)

    contacts = make_contacts(count)
    store = Store(db)

    timed("إضافة الكل دفعة واحدة", lambda: store.add_many(contacts))
    timed("تحميل كل القائمة  (store.all)", store.all, repeat=3)
    timed("صفوف العرض        (list_rows)", store.list_rows, repeat=3)
    timed("قائمة المجموعات   (all_labels)", store.all_labels, repeat=3)
    timed("بحث باسم", lambda: store.search("محمد"), repeat=3)
    timed("بحث برقم", lambda: store.search("01000005000"), repeat=3)
    timed("بحث بكلمتين", lambda: store.search("محمد النيل"), repeat=3)
    timed("كشف المكرر", store.duplicate_groups)
    timed("حفظ جهة اتصال واحدة", lambda: store.update(store.get(1)))

    store.close()
    for leftover in db.parent.glob(f"bench_{count}.db*"):
        leftover.unlink(missing_ok=True)


def bench_ui(count: int) -> None:
    """يقيس اللي بيحصل في الواجهة، وأهمه البحث وانت بتكتب."""
    import wx

    from app.store import Store
    from app.ui.main_frame import MainFrame

    print(f"\n== الواجهة مع {count} جهة اتصال ==")

    db = Path(tempfile.gettempdir()) / f"bench_ui_{count}.db"
    for leftover in db.parent.glob(f"bench_ui_{count}.db*"):
        leftover.unlink(missing_ok=True)

    app = wx.App(False)
    store = Store(db)
    store.add_many(make_contacts(count))

    frame = None

    def build():
        nonlocal frame
        frame = MainFrame(store)

    timed("بناء النافذة الرئيسية", build)
    timed("تحديث القائمة (refresh)", lambda: frame.refresh(announce=False), repeat=3)

    # الكتابة الحقيقية: التأخير بيجمّع الحروف، فبحث واحد بيتنفّذ في الآخر.
    def type_normal():
        for length in range(1, 5):
            frame.search.ChangeValue("محمد"[:length])
            frame._on_search_text(None)
        frame._flush_search()

    # أسوأ حالة: كل حرف يعمل بحث كامل (لو المستخدم بيكتب ببطء).
    def type_worst():
        for length in range(1, 5):
            frame.search.ChangeValue("محمد"[:length])
            frame._on_search_text(None)
            frame._flush_search()

    timed("كتابة ٤ حروف (الحالة العادية)", type_normal, repeat=3)
    timed("كتابة ٤ حروف (أسوأ حالة)", type_worst, repeat=3)
    frame.search.ChangeValue("")

    frame.Close()
    app.Destroy()
    for leftover in db.parent.glob(f"bench_ui_{count}.db*"):
        leftover.unlink(missing_ok=True)


def bench_interface_extras(count: int) -> None:
    """The cost of the things added for the eye: icons, banded rows,
    grouped boxes, and the window fitting itself to its contents."""
    import wx

    from app.settings import Settings
    from app.store import Store
    from app.ui import icons
    from app.ui.contact_dialog import ContactDialog
    from app.ui.main_frame import MainFrame

    print(f"\n== the visual work, with {count} contacts ==")

    db = Path(tempfile.gettempdir()) / f"bench_x_{count}.db"
    for leftover in db.parent.glob(f"bench_x_{count}.db*"):
        leftover.unlink(missing_ok=True)

    app = wx.App(False)
    store = Store(db)
    settings = Settings(db.parent / f"bench_x_{count}.json")
    store.add_many(make_contacts(count))

    icons._cache.clear()
    timed("first draw of every icon",
          lambda: [icons.get(n) for n in icons.known_names()])
    timed("the same icons once cached",
          lambda: [icons.get(n) for n in icons.known_names()], repeat=5)

    frame = None

    def build_frame():
        nonlocal frame
        frame = MainFrame(store, settings)

    timed("main window, toolbar and all", build_frame)

    # The banding colour is asked for once per drawn row, so it has to be
    # cheap: this stands in for a full repaint of a screenful.
    def paint_rows():
        for index in range(40):
            frame.list.OnGetItemAttr(index)
            for column in range(6):
                frame.list.OnGetItemText(index, column)

    timed("drawing a screenful of rows", paint_rows, repeat=5)

    form = None

    def build_form():
        nonlocal form
        if form is not None:
            form.Destroy()
        form = ContactDialog(frame, store)

    timed("contact form, five grouped boxes", build_form, repeat=3)

    timed("opening and closing the extra fields",
          lambda: (form._on_toggle_more(None), form._on_toggle_more(None)),
          repeat=3)

    form.Destroy()
    frame.Close()
    app.Destroy()
    for leftover in db.parent.glob(f"bench_x_{count}.*"):
        leftover.unlink(missing_ok=True)


def main() -> int:
    print("=" * 62)
    print("  قياس سرعة مدير جهات الاتصال")
    print("=" * 62)

    bench_startup()
    for count in (1_000, 5_000, 20_000):
        bench_size(count)
    for count in (5_000, 20_000):
        bench_ui(count)
    bench_interface_extras(5_000)

    print("\nملاحظة: أي رقم فوق ٣٠٠ ملي ثانية المستخدم بيحسّه كتأخير.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
