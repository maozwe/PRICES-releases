"""מייצר מחדש את index.json מכל מה שנמצא תחת files/.

האפליקציה קוראת את הקובץ האחד הזה במקום ללכת על Contents API של GitHub,
שמגביל קורא לא מזוהה ל-60 בקשות בשעה לפי כתובת IP. מי שפתח ארבע תיקיות
ברשת סלולרית משותפת הוא בדיוק הקורא שיגיע לתקרה — ובלי שום דרך להבחין
בין זה לבין קבצים שנעלמו. בקשה אחת, במטמון CDN, בלי הגבלה.

בכוונה בלי חותמת זמן ובלי sha: הפלט הוא פונקציה של העץ בלבד, ולכן הרצה
שלא שינתה דבר אינה מייצרת diff וה-workflow מדלג על הקומיט.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "files"
OUT = ROOT / "index.json"

RAW_BASE = "https://raw.githubusercontent.com/maozwe/PRICES-releases/main"

# לא תוכן. README בתיקייה מסביר אותה למי שמדפדף ב-GitHub; הצגתו כקובץ
# באפליקציה רק שמה README מול המשתמש בכל תיקייה.
HIDDEN_NAMES = {"README.md", ".gitkeep", ".DS_Store", "Thumbs.db"}


def _url(rel_posix: str) -> str:
    """כתובת raw לנתיב יחסי בריפו.

    הקידוד קריטי: התיקיות כאן בעברית, ונתיב לא מקודד עובד בדפדפן (שמקודד
    בשבילך) ונכשל מלקוחות HTTP שאינם מקודדים.
    """
    return f"{RAW_BASE}/{quote(rel_posix)}"


def _node(path: Path) -> dict | None:
    rel = path.relative_to(ROOT).as_posix()

    if path.is_dir():
        children = []
        # תיקיות קודם ואז קבצים, כל קבוצה לפי א-ב — הסדר שהאפליקציה מציגה,
        # נקבע כאן ולא בלקוח כדי ששני לקוחות יציגו אותו דבר.
        for child in sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            if child.name in HIDDEN_NAMES or child.name.startswith("."):
                continue
            node = _node(child)
            if node is not None:
                children.append(node)
        return {
            "name": path.name,
            "path": rel,
            "type": "dir",
            "children": children,
            "count": len(children),
        }

    return {
        "name": path.name,
        "path": rel,
        "type": "file",
        "size": path.stat().st_size,
        "url": _url(rel),
    }


def main() -> None:
    if not FILES.is_dir():
        raise SystemExit("files/ לא קיימת")

    tree = _node(FILES)
    OUT.write_text(
        json.dumps({"root": "files", "tree": tree}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    def count(node: dict) -> int:
        return 1 if node["type"] == "file" else sum(count(c) for c in node["children"])

    print(f"indexed {count(tree)} files")


if __name__ == "__main__":
    main()
