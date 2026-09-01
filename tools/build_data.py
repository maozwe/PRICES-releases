"""הופך כל מחירון שנמצא תחת files/ ל-JSON שהאפליקציה יכולה לחפש בו.

מי שמעלה קובץ דרך ממשק הווב של GitHub לא מריץ שום סקריפט, ולכן אין כאן
רשימה קשיחה של מחירונים: הסקריפט סורק את files/, בוחר פרסר לפי סיומת,
ומייצר data/<id>.json לכל מחירון שהצליח לקרוא. מחירון חדש בפורמט מוכר
נכנס לאפליקציה בלי שינוי קוד.

tools/sources.json נותן שם תצוגה וגרסה למחירונים המוכרים בלבד. קובץ שאינו
רשום שם ייקרא בכל זאת ושמו יגזר משם הקובץ, וכך הכשל האפשרי הוא שם לא יפה
ולא מחירון חסר.

קובץ שנכשל או שלא הופק ממנו ולו סעיף אחד מדווח ב-data/sources.json תחת
failed, כדי שהאפליקציה תוכל להראות שמשהו לא נקרא במקום להשמיט אותו בשקט.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "files"
OUT = ROOT / "data"
sys.path.insert(0, str(ROOT))

from tools.parsers import excel, shikun_pdf  # noqa: E402

EXCEL_EXT = {".xlsx", ".xls", ".xlsm"}
PDF_EXT = {".pdf"}


def slug(name: str) -> str:
    """מזהה יציב ובטוח ל-URL משם קובץ, כולל שמות עבריים."""
    s = unicodedata.normalize("NFKC", name).strip().lower()
    s = re.sub(r"[^\w֐-׿]+", "-", s).strip("-")
    return s or "pricelist"


def dedupe(items):
    """מסיר שורות כפולות לפי קוד סעיף.

    מחירון דקל מכיל אלפי קודים שמופיעים פעמיים עם תוכן זהה לחלוטין.
    מסירים רק כפילות אמיתית; אותו קוד עם תוכן שונה הוא בעיה בנתונים
    ולכן נשמר עם מזהה ייחודי ומדווח.
    """
    seen, out, exact, conflicts = {}, [], 0, 0
    for i in items:
        sig = (i["desc"], i["unit"], i["price"])
        if i["code"] not in seen:
            seen[i["code"]] = sig
            out.append(i)
        elif seen[i["code"]] == sig:
            exact += 1
        else:
            conflicts += 1
            i["id"] = f"{i['id']}#{conflicts}"
            out.append(i)
    return out, exact, conflicts


def parse_one(path: Path, src_id: str):
    ext = path.suffix.lower()
    if ext in EXCEL_EXT:
        return excel.parse(str(path), src_id)
    if ext in PDF_EXT:
        return shikun_pdf.parse(str(path), src_id)
    return None, {"reason": f"סיומת לא נתמכת ({ext})"}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if not FILES.is_dir():
        raise SystemExit("files/ לא קיימת")

    cfg = json.loads((ROOT / "tools" / "sources.json").read_text(encoding="utf-8"))
    overrides = cfg.get("overrides", {})

    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()          # מחירון שנמחק מ-files/ צריך להיעלם גם מ-data/

    manifest, failed, used_ids, total = [], [], set(), 0

    candidates = sorted(
        (p for p in FILES.rglob("*") if p.is_file() and p.suffix.lower() in EXCEL_EXT | PDF_EXT),
        key=lambda p: p.as_posix().lower(),
    )

    for path in candidates:
        rel = path.relative_to(ROOT).as_posix()
        meta = overrides.get(path.name, {})
        src_id = meta.get("id") or slug(path.stem)
        while src_id in used_ids:                 # שני קבצים באותו שם בתיקיות שונות
            src_id += "-2"
        used_ids.add(src_id)

        try:
            items, stats = parse_one(path, src_id)
        except Exception as err:                  # קובץ פגום לא יפיל את כל הבנייה
            failed.append({"file": rel, "reason": f"{type(err).__name__}: {err}"})
            print(f"  כשל   {rel}\n         {type(err).__name__}: {err}")
            continue

        if not items:
            failed.append({"file": rel, "reason": (stats or {}).get("reason", "לא נמצאו סעיפים")})
            print(f"  ריק   {rel}  {stats}")
            continue

        items, exact_dups, conflicts = dedupe(items)
        (OUT / f"{src_id}.json").write_text(
            json.dumps(items, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        priced = sum(1 for i in items if i["price"] and not i["note"])
        total += len(items)
        manifest.append({
            "id": src_id,
            "name": meta.get("name") or path.stem,
            "version": meta.get("version", ""),
            "file": rel,
            "count": len(items),
            "priced": priced,
        })
        extra = f" כפילויות={exact_dups}" if exact_dups else ""
        extra += f" התנגשויות={conflicts}" if conflicts else ""
        print(f"  {src_id:10} {len(items):6,} סעיפים  {priced:6,} מתומחרים{extra}  <- {rel}")

    (OUT / "sources.json").write_text(
        json.dumps({"sources": manifest, "failed": failed}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\n  סה\"כ {total:,} סעיפים מ-{len(manifest)} מחירונים"
          + (f", {len(failed)} קבצים לא נקראו" if failed else ""))


if __name__ == "__main__":
    main()
