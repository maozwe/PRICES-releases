# -*- coding: utf-8 -*-
"""מחירון משרד הבינוי והשיכון לעבודות פיתוח וסלילה — PDF בן 148 עמודים.

הטקסט שמור בסדר ויזואלי (ראה rtl.py). השיוך לעמודות נעשה לפי מיקום X
ולא לפי פיצול מחרוזת, כי התיאור מכיל רווחים ומספרים שמבלבלים כל heuristic
טקסטואלי. גבולות העמודות נגזרים משורת הכותרת בכל עמוד בנפרד.

מבנה: סעיף | תת פרק | פרק | תיאור | יחידה | מחיר  (מימין לשמאל).
תיאור נפרס על מספר שורות; השורה האחרונה בקבוצה נושאת קוד+יחידה+מחיר.
סעיף שמספרו מסתיים ב-0000 הוא כותרת תת פרק ולא פריט.
"""
import re
import pdfplumber
from .common import make_item, parse_price, clean
from .rtl import fix_word, group_lines

COLS = ('item', 'sub', 'ch', 'desc', 'unit', 'price')
H_ITEM, H_CHAP, H_DESC, H_UNIT, H_PRICE = 'ףיעס', 'קרפ', 'רואית', 'הדיחי', 'ריחמ'
NUM_RE = re.compile(r'^\d[\d,]*\.?\d*$')


def _centers(words):
    """גבולות העמודות משורת הכותרת, או None אם אין כותרת בעמוד."""
    by_x = sorted(words, key=lambda w: -w['x0'])
    txt = [w['text'] for w in by_x]
    if H_ITEM not in txt or H_PRICE not in txt or H_DESC not in txt:
        return None
    c = lambda w: (w['x0'] + w['x1']) / 2
    try:
        i_item = txt.index(H_ITEM)
        i_desc = txt.index(H_DESC)
        i_unit = txt.index(H_UNIT)
        i_price = txt.index(H_PRICE)
    except ValueError:
        return None
    # בין סעיף לתיאור יושבים "תת פרק" ו"פרק" — לוקחים את מרכזי הטוקנים שביניהם
    mid = by_x[i_item + 1:i_desc]
    if len(mid) < 2:
        return None
    sub_c = (c(mid[0]) + c(mid[1])) / 2 if len(mid) > 2 else c(mid[0])
    ch_c = c(mid[-1])
    cs = [c(by_x[i_item]), sub_c, ch_c, c(by_x[i_desc]), c(by_x[i_unit]), c(by_x[i_price])]
    return [(cs[i] + cs[i + 1]) / 2 for i in range(5)]   # 5 גבולות = 6 עמודות


def _bucket(words, bounds):
    """משייך מילים לעמודות לפי מרכז X ומחזיר dict של עמודה -> טקסט לוגי."""
    cells = {k: [] for k in COLS}
    for w in words:
        x = (w['x0'] + w['x1']) / 2
        idx = next((i for i, b in enumerate(bounds) if x > b), 5)
        cells[COLS[idx]].append(w)
    return {k: ' '.join(fix_word(w['text'])
                        for w in sorted(v, key=lambda w: -w['x0']))
            for k, v in cells.items()}


def parse(path, src):
    items, pages_used, buf = [], 0, []
    ch_name = sub_name = ''
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            words = pg.extract_words()
            lines = group_lines(words)
            hdr = next(((t, b) for t, ws in lines[:5] if (b := _centers(ws))), None)
            if not hdr:
                continue                      # עמוד הקדמה / תוכן עניינים
            hdr_top, bounds = hdr
            pages_used += 1
            foot = pg.height - 50             # כותרת רצה בתחתית כל עמוד
            for top, ws in lines:
                if top <= hdr_top or top >= foot:
                    continue
                cell = _bucket(ws, bounds)
                if cell['desc']:
                    buf.append(cell['desc'])
                if not (cell['item'].isdigit() and cell['ch'].isdigit()
                        and cell['sub'].isdigit()):
                    continue                  # שורת המשך תיאור / כותרת פרק
                desc = ' '.join(buf)
                buf = []
                code = f"{int(cell['ch']):02d}.{cell['sub']}.{cell['item']}"
                if cell['item'] == '0000':    # כותרת תת פרק, לא פריט
                    sub_name = desc
                    continue
                price = parse_price(cell['price']) if NUM_RE.match(cell['price']) else None
                it = make_item(src, code, desc, cell['unit'], price, ch_name, sub_name)
                if it:
                    items.append(it)
    return items, {'pages_used': pages_used}
