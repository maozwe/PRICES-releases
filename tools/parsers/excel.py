# -*- coding: utf-8 -*-
"""פרסר יחיד לכל מחירון בפורמט אקסל.

שלושת המחירונים שנתקלנו בהם נבדלים רק בפרטים שהקוד מגלה בעצמו:
  • דקל (.xlsx)            — כותרת בשורה 1, בלי כותרות פרק
  • העירוני / נת"צ (.xlsx)  — כותרת בשורה 2, קוד עם קידומת U, כותרות פרק
  • האחוד נתיבי ישראל (.xls BIFF8) — כותרת בשורה 79, קוד ללא קידומת

לכן אין כאן ענפים לפי מקור: שורת הכותרת מאותרת לפי תוכן ולא לפי מספר שורה,
וכותרות פרק מזוהות לפי צורתן. מחירון חדש בפורמט דומה ייקרא בלי שינוי קוד.

שורת כותרת פרק = "פרק N - שם" או "תת פרק N.N - שם" בעמודה A.
שורת פריט = קוד תקין בעמודה A + תיאור/יחידה/מחיר.
"""
import re
from .common import make_item, parse_price, clean

# הקו המפריד ושם הפרק שניהם אופציונליים: יש ווריאנטים שבהם השם יושב
# בעמודה B ("תת פרק 06.01 -" | "מוצרי נגרות אומן") ואף "פרק 54" בלי קו כלל.
CH_RE = re.compile(r'^פרק\s+(\S+)\s*[-–]?\s*(.*)$')
SUB_RE = re.compile(r'^תת\s*פרק\s+(\S+)\s*[-–]?\s*(.*)$')
# תוכן עמודה A בשורת הכותרת. מגוון הניסוחים הוא בדיוק מה שמונע לקבע
# מספר שורה: דקל פותח בשורה 1, העירוני בשורה 2 והאחוד בשורה 79.
HEADER_HINTS = ('מק"ט', 'מס קטלוגי', 'מספר קטלוגי', 'סעיף', 'מספר סעיף')


def _rows_xlsx(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    for row in ws.iter_rows(values_only=True):
        yield [(list(row) + [None] * 4)[i] for i in range(4)]
    wb.close()


def _rows_xls(path):
    import xlrd
    sh = xlrd.open_workbook(path).sheet_by_index(0)
    for r in range(sh.nrows):
        yield [sh.cell_value(r, c) if c < sh.ncols else None for c in range(4)]


def parse(path, src):
    rows = _rows_xls(path) if path.lower().endswith('.xls') else _rows_xlsx(path)
    items, skipped, started = [], 0, False
    ch_name = sub_name = ''
    for a, b, c, d in rows:
        a_s = clean(a)
        if not started:                          # לדלג על כל מה שלפני שורת הכותרת
            started = any(h in a_s for h in HEADER_HINTS)
            continue
        if not a_s:
            continue
        m = SUB_RE.match(a_s)                    # שורת כותרת תת פרק
        if m:
            sub_name = clean(m.group(2)) or clean(b)
            continue
        m = CH_RE.match(a_s)                     # שורת כותרת פרק
        if m:
            ch_name, sub_name = clean(m.group(2)) or clean(b), ''
            continue
        it = make_item(src, a, b, c, parse_price(d), ch_name, sub_name)
        if it:
            items.append(it)
        else:
            skipped += 1
    return items, {'skipped_bad_code': skipped}
