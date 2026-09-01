# -*- coding: utf-8 -*-
"""חילוץ טקסט עברי מ-PDF ששמור בסדר ויזואלי (RTL הפוך).

ה-PDF של משרד השיכון לא נוצר עם אלגוריתם bidi תקני (אומת מול python-bidi:
UBA תקני משאיר "4X50" שלם, בעוד שבקובץ הוא מופיע כ-"X504"). שתי בעיות נפרדות:

1. סדר המילים בשורה הפוך, וכל מילה עברית שמורה עם אותיות הפוכות.
   פתרון: חילוץ ברמת מילה, מיון לפי x יורד, היפוך אותיות בכל מילה עברית.
   היפוך פשוט מתקן גם סוגריים וגרשיים — ")גניפוק(" -> "(קופינג)".

2. בטוקן אלפאנומרי מעורב, רצת הספרות הפותחת הועברה לסוף:
       4X50 -> X504        40X40    -> X4040
       3X70+35 -> X70+353  10X100X20 -> X100X2010
   פתרון: unscramble_token().
"""
import re

HEB = re.compile(r'[\u0590-\u05FF]')
_TRAIL_DIGITS = re.compile(r'(\d+)$')


def unscramble_token(tok):
    """מחזיר את רצת הספרות שהועברה לסוף חזרה לתחילת הטוקן.

    מוחל רק על טוקן שמתחיל ב-X/x ומסתיים בספרה. ההגבלה הזו היא ההגנה
    המרכזית: הטוקן המקורי היה <ספרות>X<ספרות>, וכשרצת הפתיחה עזבה נחשף
    ה-X בתחילת הטוקן. סימוני תקן לגיטימיים (PE100, D400, B125, C250,
    N2XY) מתחילים באות אחרת ולכן לא נגעים בהם כלל.

    מבין הפיצולים האפשריים נבחר זה שממזער את אורך קבוצת הספרות הארוכה
    ביותר בתוצאה — מידות אמיתיות מאוזנות (150X150 ולא 50X1501).
    שובר שוויון: הקבוצה המוזזת הקצרה ביותר.

    מחזיר (טוקן, שונה?).
    """
    if not tok or tok[0] not in 'Xx':
        return tok, False
    m = _TRAIL_DIGITS.search(tok)
    if not m:
        return tok, False

    run, head_end = m.group(1), m.start(1)
    best = None
    for n in range(1, len(run) + 1):
        moved = run[-n:]
        if moved[0] == '0':                 # מספר לא מתחיל באפס
            continue
        rest = tok[:head_end] + run[:len(run) - n]
        if not re.search(r'\d', rest):      # לא נשאר מספר -> לא מידה
            continue
        cand = moved + rest
        longest = max(len(g) for g in re.findall(r'\d+', cand))
        key = (longest, n)
        if best is None or key < best[0]:
            best = (key, cand)
    return (best[1], True) if best else (tok, False)


_RUN_RE = re.compile(r'\d+(?:[.,]\d+)*|[A-Za-z]+|[^\dA-Za-z]+')


def fix_word(w):
    """מילה בודדת מהחילוץ -> סדר לוגי.

    בתוך מילה מעורבת רק רצף העברית/הפיסוק שמור הפוך; רצפי ספרות ולטינית
    נשמרים כמות שהם. לכן "30-ב" -> "ב-30" ולא "ב-03".
    """
    if not HEB.search(w):
        return unscramble_token(w)[0]
    out = []
    for run in reversed(_RUN_RE.findall(w)):
        keep = run[0].isdigit() or (run[0].isascii() and run[0].isalpha())
        out.append(run if keep else run[::-1])
    return ''.join(out)


def line_from_words(words):
    """רשימת word-dicts של pdfplumber מאותה שורה -> מחרוזת בסדר לוגי."""
    ordered = sorted(words, key=lambda w: -w['x0'])
    return ' '.join(fix_word(w['text']) for w in ordered)


def group_lines(words, tol=3.0):
    """מקבץ words לשורות לפי קואורדינטת top, ומחזיר [(top, [words]), ...]."""
    rows = {}
    for w in words:
        rows.setdefault(round(w['top'] / tol), []).append(w)
    return [(k * tol, v) for k, v in sorted(rows.items())]


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    CASES = [
        ('X504', '4X50'), ('X954', '4X95'), ('X1204', '4X120'),
        ('X70+353', '3X70+35'), ('X95+503', '3X95+50'), ('X120+703', '3X120+70'),
        ('X4040', '40X40'), ('X150150', '150X150'), ('X100X2010', '10X100X20'),
        ('X30X1540', '40X30X15'), ('X150150', '150X150'),
        ('X100X15100', '100X100X15'), ('X50X1523', '23X50X15'),
        # סימוני תקן לגיטימיים — חייבים להישאר ללא שינוי
        ('PE100', 'PE100'), ('D400', 'D400'), ('B125', 'B125'),
        ('C250', 'C250'), ('N2XY', 'N2XY'),
    ]
    bad = 0
    for src, want in CASES:
        got, _ = unscramble_token(src)
        ok = got == want
        bad += not ok
        print(f"  {'ok ' if ok else 'FAIL'} {src:12} -> {got:12} (expected {want})")
    print(f"\n{len(CASES) - bad}/{len(CASES)} passed")
    sys.exit(1 if bad else 0)
