# -*- coding: utf-8 -*-
"""עזרים משותפים לכל ה-parsers: סכמה אחידה, ניקוי טקסט ופענוח מחיר."""
import re
import html as _html

CODE_RE = re.compile(r'^([A-Za-z]?)(\d{2})\.(\d{2,3})\.(\d{3,4})$')
_TAG_RE = re.compile(r'<[^>]*>')
_OPEN_TAG_RE = re.compile(r'<[^>]*$')   # תגית שנקטעה בסוף המחרוזת


def clean(s):
    """נירמול טקסט: הסרת תגיות HTML (12.8% מתיאורי דקל מכילים <br>/<p>/<span>),
    פענוח ישויות HTML, הסרת סימני כיווניות וכיווץ רווחים."""
    if s is None:
        return ''
    s = str(s).replace('\u200f', '').replace('\u200e', '')
    if '<' in s:
        s = _OPEN_TAG_RE.sub(' ', _TAG_RE.sub(' ', s))
    if '&' in s:
        s = _html.unescape(s)
    return re.sub(r'\s+', ' ', s).strip()


def parse_price(v):
    """מחזיר float, או None כשאין מחיר ('-', ריק, טקסט לא מספרי)."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(',', '').strip()
    if not s or s in {'-', '--', '.'}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def make_item(src, code, desc, unit, price, ch_name='', sub_name=''):
    """בונה פריט בסכמה האחידה. מחזיר None אם הקוד לא תקין."""
    code = clean(code)
    m = CODE_RE.match(code)
    if not m:
        return None
    _, ch, sub, _ = m.groups()
    unit = normalize_unit(unit)
    is_note = unit == 'הערה'
    # מחיר 0 בסעיף אמיתי אינו מחיר אלא היעדר מחיר ("המשך תכולת סעיף קודם",
    # סעיפים שטרם תומחרו). בכתב כמויות "0 ₪" מטעה, ולכן נרשם כהיעדר מחיר.
    # מחיר שלילי דווקא נשמר — אלה סעיפי הפחתה לגיטימיים.
    if price == 0 and not is_note:
        price = None
    return {
        'id': f'{src}:{code}',
        'src': src,
        'code': code,
        'ch': ch,
        'sub': sub,
        'chName': clean(ch_name),
        'subName': clean(sub_name),
        'desc': clean(desc),
        'unit': unit,
        'price': price,
        'note': is_note,
    }


# מיפוי יחידות לצורה קנונית. המפתחות הם ללא גרשיים, כי בקבצים קיימות
# שתי צורות לאותה יחידה (ס"מ מול ס''מ, מ"מ מול מ''מ).
_UNIT_MAP = {
    'מ': "מ'", 'מטר': "מ'", 'מר': 'מ"ר', 'מק': 'מ"ק', 'ממר': 'ממ"ר',
    'יח': "יח'", 'יחידה': "יח'", 'קומפ': "קומפ'", 'קומפלט': "קומפ'",
    'טון': 'טון', 'קג': 'ק"ג', 'דונם': 'דונם', 'זוג': 'זוג', 'נק': "נק'",
    'חודש': 'חודש', 'יום': 'יום', 'שבוע': 'שבוע', 'מכלול': 'מכלול',
    'אינצ': "אינצ'", 'שע': 'ש"ע', 'יע': 'י"ע', 'קמ': 'ק"מ',
    'סמ': 'ס"מ', 'ממ': 'מ"מ', 'הערה': 'הערה', 'אטמ': "אטמ'",
}
_QUOTES_RE = re.compile(r'["\'\u05f3\u05f4]')


def normalize_unit(u):
    """מחזיר יחידת מידה בצורה קנונית.

    תאי יחידה ב-PDF נגועים לעיתים בטקסט שדלף מעמודת התיאור
    ('("כפפות"). מטר'); במקרה כזה נלקח הטוקן המוכר האחרון בתא.
    יחידות מורכבות (יח'/חודש) נשמרות כפי שהן.
    """
    u = clean(u)
    if not u:
        return ''
    key = _QUOTES_RE.sub('', u)
    if key in _UNIT_MAP:
        return _UNIT_MAP[key]
    for tok in reversed(u.split()):
        k = _QUOTES_RE.sub('', tok).strip('.,')
        if k in _UNIT_MAP:
            return _UNIT_MAP[k]
    return u
