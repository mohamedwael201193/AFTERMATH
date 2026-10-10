"""Typed numeric normaliser (clean-room; mechanism idea from Loop `engine/numberlock.py` and Slipway slot masking,
deep audit A. No code copied). Turns free text into typed quantities and binds them to typed evidence facts.

normalize_claim(text) -> NormalizedClaim
    .quantities  every number found, each a Quantity(value, dimension, unit, tol, sign_explicit, ...)
    .rejects     quantities that could not be read unambiguously (status REJECT + reason)
check_text(text, facts) / validate_numbers(text, evidence_items) -> (verdict, details)

Rules (all tested in tests/test_numnorm.py):
  * NFKC first (full-width digits), Unicode minus U+2212 / en dash before a digit at a word start are a sign.
  * magnitude: k/K 1e3, M/mn/MM/m 1e6, B/bn 1e9, T/tn 1e12, words thousand/million/billion/trillion, CJK 千 万 萬 百万
    亿 億 兆; scientific notation 1e3 / 1.2E-5. Tolerance = half a unit of the LAST SHOWN digit at the final magnitude,
    capped at 5% of the value for suffix / exponent / word forms ("1e3" must be within 50 of a fact, not 500).
  * written numbers: English cardinals (two .. ninety-nine, hundred .. trillion, "point" decimals, a dozen) and CJK
    numerals (三万, 两千五百, 3.2万) are parsed to values. "one"/"a" alone are not quantities (too common in prose).
    Number words in other languages (sieben tausend, septante, cinco, тысяча ...) are never parsed: REJECT.
  * dimensions: currency ($, US$, USD, USDT, USDC, EUR/€, CNY/RMB/¥, JPY, GBP/£) | percent (%) | bp (bp, bps, basis
    points) | pp (pp, ppt, percentage points) | time (s, min, h, hr, d, day(s), w, week(s)) | multiple (x, ×) |
    count (shares, contracts, trades, precedents, filings, events, nights, sessions, cycles) | bare.
    Values are kept in canonical form: percent / bp / pp are stored as a RATIO (55 bp -> 0.0055, 2% -> 0.02).
  * separators: "1,234,567" and "1,234.5" are US thousands; "1.234.567" and "1.234,56" are EU thousands; "1\u202f234"
    (thin / no-break space or apostrophe groups) are grouped thousands; "7_000" (underscore groups) is 7000; plain-space
    groups "7 000" are AMBIGUOUS -> REJECT (never read as 7 and 000, never guessed as 7000). "1,5" or "3,25" (comma + 1-2 digits) is AMBIGUOUS -> REJECT;
    "1,2345" or "12,34,567" (malformed groups) -> REJECT.
  * not quantities: ISO dates and clock times, years 1990-2100 written bare (or FY2026, Q3), form names (8-K, 10-Q,
    20-F), item numbers ("item 2.02"), identifiers glued to letters (rNVDA2, 2a, ids like book:NVDA:ab12).
  * ranges "3-5%" give two quantities with the trailing unit applied to both; "-" between digits is never a sign.
Binding (bind / check_text): a quantity binds to a fact only when the dimensions are compatible:
  ratio-type facts (field *_ret, *_frac, *rate*, pct fields, *_bp) accept percent / bp / pp / bare-ratio forms after
  conversion; currency facts accept currency or bare; count / time facts accept their unit or bare; dimensionless
  facts (z, r2, beta, confidence) accept bare only. An explicit sign (+/-) must match the fact's sign. Bare numbers
  never get a percent / bp rescale (v1/v2 let a bare 55 bind to 0.0055 via x1e4; that is how '55%' vs '55 bp'
  confusions slipped). A unit that conflicts with the fact (e.g. '55%' against a *_bp field holding 55) is
  UNIT_MISMATCH."""
from __future__ import annotations
import math, re, unicodedata
from dataclasses import dataclass, field, asdict
from typing import Iterable, Optional

MAG = {"k": 1e3, "K": 1e3, "M": 1e6, "m": 1e6, "mn": 1e6, "MM": 1e6, "mm": 1e6, "B": 1e9, "bn": 1e9, "b": 1e9,
       "T": 1e12, "tn": 1e12, "千": 1e3, "万": 1e4, "萬": 1e4, "百万": 1e6, "千万": 1e7, "亿": 1e8, "億": 1e8, "兆": 1e12,
       "thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12}
CUR_PRE = {"$": "USD", "US$": "USD", "USD": "USD", "USDT": "USDT", "USDC": "USDC", "€": "EUR", "EUR": "EUR",
           "¥": "CNY", "CNY": "CNY", "RMB": "CNY", "JPY": "JPY", "£": "GBP", "GBP": "GBP"}
CUR_POST = {"usd": "USD", "usdt": "USDT", "usdc": "USDC", "dollars": "USD", "dollar": "USD", "eur": "EUR", "euros": "EUR",
            "cny": "CNY", "rmb": "CNY", "yuan": "CNY", "元": "CNY", "美元": "USD", "jpy": "JPY", "yen": "JPY", "gbp": "GBP"}
TIME = {"s": "s", "sec": "s", "secs": "s", "second": "s", "seconds": "s", "ms": "ms", "min": "min", "mins": "min",
        "minute": "min", "minutes": "min", "h": "h", "hr": "h", "hrs": "h", "hour": "h", "hours": "h", "d": "d",
        "day": "d", "days": "d", "w": "w", "wk": "w", "week": "w", "weeks": "w", "小时": "h", "天": "d"}
TIME_SEC = {"ms": 1e-3, "s": 1, "min": 60, "h": 3600, "d": 86400, "w": 604800}
COUNT = {"share", "shares", "contract", "contracts", "trade", "trades", "precedent", "precedents", "filing", "filings",
         "event", "events", "night", "nights", "session", "sessions", "cycle", "cycles", "order", "orders", "stocks",
         "names", "bars", "股", "笔", "份", "samples", "analogs", "customers", "suppliers", "tokens", "decisions", "fills", "votes", "passes"}
SMALL = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
         "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
         "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
         "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "dozen": 12}
CJK_D = {"〇": 0, "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CJK_U = {"十": 10, "百": 100, "千": 1000}
CJK_B = {"万": 1e4, "萬": 1e4, "亿": 1e8, "億": 1e8, "兆": 1e12}

@dataclass
class Quantity:
    raw: str
    start: int
    end: int
    value: Optional[float] = None       # canonical: percent/bp/pp as ratio, time in the stated unit, money in currency units
    dimension: str = "bare"              # bare|currency|percent|bp|pp|time|multiple|count
    unit: Optional[str] = None           # USD, %, bp, pp, h, x, shares ...
    tol: float = 0.0
    sign_explicit: bool = False
    form: str = "digits"                 # digits|suffix|sci|words|cjk
    comparator: Optional[str] = None     # '>' / '<' for 'over 1M', '>1M', 'sub-50%', 'below 3 bp'
    status: str = "OK"                   # OK | REJECT
    reason: Optional[str] = None
    def to_dict(self): return asdict(self)

@dataclass
class NormalizedClaim:
    text: str
    quantities: list = field(default_factory=list)
    skipped: list = field(default_factory=list)       # (token, why) for identifiers / dates / years / form names
    @property
    def rejects(self): return [q for q in self.quantities if q.status != "OK"]
    @property
    def ok(self): return [q for q in self.quantities if q.status == "OK"]
    def to_dict(self): return {"text": self.text, "quantities": [q.to_dict() for q in self.quantities], "skipped": self.skipped}

# ------------------------------------------------------------------------------------------------ preprocessing
_DASHES = "\u2212\u2012\u2013\u2014\ufe63\uff0d"
def _prep(text: str) -> str:
    t = re.sub(r"(?<=\d)[\u202f\u2009\u00a0'](?=\d{3}(?!\d))", "", text or "")   # 1\u202f234\u202f567 / 1'234 grouping
    t = unicodedata.normalize("NFKC", t)
    for d in _DASHES: t = t.replace(d, "-")
    return t.replace("\u202f", " ").replace("\u2009", " ").replace("\u00a0", " ")

SKIP_PATTERNS = [
    ("date", re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}(?::\d{2}){1,2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?")),
    ("date", re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")),
    ("clock", re.compile(r"(?<![\d.])\d{1,2}:\d{2}(?::\d{2})?(?:\s?(?:ET|UTC|Z|am|pm|AM|PM))?(?![\d])")),
    ("form", re.compile(r"(?<![A-Za-z\d.$€£¥])(?:8|10|20|6|40)-[KkQqFf](?:/A)?(?![A-Za-z\d])")),
    ("form", re.compile(r"(?<![A-Za-z\d.$€£¥])(?:8K|10K|10Q|20F)(?:/A)?(?![A-Za-z\d])(?!\s*(?:USD|USDT|notional|shares|contracts|volume|depth))")),
    ("form", re.compile(r"\b(?:Form|form)\s+\d+\b")),
    ("item", re.compile(r"\b[Ii]tems?\s+\d+(?:\.\d+)?(?:\s*(?:,|/|and|&)\s*\d+(?:\.\d+)?)*")),
    ("period", re.compile(r"\b(?:FY|Q[1-4]\s?|H[12]\s?|CY)\s?'?\d{2,4}\b")),
    ("period", re.compile(r"\bQ[1-4]\b")),
    ("id", re.compile(r"\b[A-Za-z_][\w.-]*:[\w.:-]+")),                 # evidence ids book:NVDAUSDT:ab12, shock:X:2026-..
    ("id", re.compile(r"\b0x[0-9a-fA-F]+\b")),
    ("hash", re.compile(r"\b(?=[0-9a-f]*[a-f])(?=[0-9a-f]*\d)[0-9a-f]{12,64}\b")),
]
_GLUED = re.compile(r"(?<![\w.])[A-Za-z_]\w*\d\w*|(?<![\w.])\d+[A-Za-z_]{2,}\d\w*")     # rNVDA2, H17, abc123, 3a4

def _mask(t: str, extra_ids=()):
    """Replace non-quantity spans with spaces (same length) and record what was skipped."""
    skipped = []; t = list(t); s = "".join(t)
    for i in sorted(set(extra_ids or ()), key=len, reverse=True):
        for m in re.finditer(re.escape(i), s):
            skipped.append((m.group(0), "id")); t[m.start():m.end()] = " " * (m.end() - m.start())
        s = "".join(t)
    for why, rx in SKIP_PATTERNS:
        for m in rx.finditer(s):
            skipped.append((m.group(0), why)); t[m.start():m.end()] = " " * (m.end() - m.start())
        s = "".join(t)
    for m in _GLUED.finditer(s):
        tok = m.group(0)
        if re.fullmatch(r"\d+(?:\.\d+)?(?:e[-+]?\d+)?(?:[kKMBT]|bn|mn|tn|bps?|pp|ppt|hrs?|mins?|secs?|ms|x)", tok, re.I): continue
        skipped.append((tok, "identifier")); t[m.start():m.end()] = " " * (m.end() - m.start())
    s = "".join(t)
    # bare years (1990..2100 integers, not followed by a unit/magnitude and not preceded by a currency sign)
    for m in re.finditer(r"(?<![\d.,$€£¥-])(19[9]\d|20\d\d|2100)(?![\d.,%])(?!\s*(?:bp|bps|%|x|k|K|M|B|USD|USDT|shares|contracts)\b)", s):
        skipped.append((m.group(0), "year")); t[m.start():m.end()] = " " * 4
    return "".join(t), skipped

# ------------------------------------------------------------------------------------------------ number reading
NUM_RE = re.compile(
    r"(?P<sign>[-+])?(?P<num>\d{1,3}(?:,\d{3})+(?![\d,])(?:\.\d+)?|\d{1,3}(?:\.\d{3}){2,}(?![\d.])(?:,\d+)?|\d{1,3}\.\d{3},\d+|"
    r"\d+(?:,\d+)?(?:\.\d+)?|\.\d+)"
    r"(?:[eE](?P<exp>[-+]?\d+))?")
SUFFIX_RE = re.compile(r"\s?(?P<suf>百万|千万|thousand|million|billion|trillion|mn|MM|bn|tn|[kKMBT千万萬亿億兆])(?![A-Za-z])|(?P<m>m)(?![A-Za-z])")

def _read_digits(num: str):
    """(value, decimals) or (None, reason)."""
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", num):                      # US thousands
        v = num.replace(",", ""); dec = len(v.split(".")[1]) if "." in v else 0; return float(v), dec
    if re.fullmatch(r"\d{1,3}(?:\.\d{3}){2,}(?:,\d+)?", num) or re.fullmatch(r"\d{1,3}\.\d{3},\d+", num):   # EU thousands
        v = num.replace(".", "").replace(",", "."); dec = len(v.split(".")[1]) if "." in v else 0; return float(v), dec
    if "," in num:
        return None, "AMBIGUOUS_SEPARATOR"          # 1,5 / 3,25 / 1,2345 / 12,34,567
    dec = len(num.split(".")[1]) if "." in num else 0
    return float(num), dec

def _unit_after(t: str, j: int):
    """Look at text right after position j for a unit. Returns (dimension, unit, end, scale)."""
    rest = t[j:j + 40]
    m = re.match(r"\s?(%|％)", rest)
    if m: return "percent", "%", j + m.end(), 1e-2
    m = re.match(r"\s?(?:percentage[ -]points?|pct[ .]?pts?|ppts?|pp)(?![A-Za-z])", rest, re.I)
    if m: return "pp", "pp", j + m.end(), 1e-2
    m = re.match(r"\s?(?:percent|per cent|pct)(?![A-Za-z])", rest, re.I)
    if m: return "percent", "%", j + m.end(), 1e-2
    m = re.match(r"\s?(?:basis[ -]points?|bps|bp|个基点|基点)(?![A-Za-z])", rest, re.I)
    if m: return "bp", "bp", j + m.end(), 1e-4
    m = re.match(r"\s?(?:x|×)(?![A-Za-z\d])", rest)
    if m: return "multiple", "x", j + m.end(), 1.0
    m = re.match(r"\s?([A-Za-z\u4e00-\u9fff]+)", rest)
    if m:
        w = m.group(1); wl = w.lower()
        if wl in CUR_POST or w in CUR_POST: return "currency", CUR_POST.get(wl, CUR_POST.get(w)), j + m.end(), 1.0
        if wl in TIME or w in TIME: return "time", TIME.get(wl, TIME.get(w)), j + m.end(), 1.0
        if wl in COUNT: return "count", wl, j + m.end(), 1.0
    return None, None, j, 1.0

def _cur_before(t: str, i: int):
    m = re.search(r"(US\$|USD|USDT|USDC|EUR|CNY|RMB|JPY|GBP|[$€£¥])\s?$", t[max(0, i - 6):i])
    return CUR_PRE[m.group(1)] if m else None

GT = {">", ">=", "over", "above", "more than", "greater than", "at least", "exceeding", "≥"}
CMP_RE = re.compile(r"(>=|<=|≥|≤|>|<|\bover|\babove|\bmore than|\bgreater than|\bat least|\bexceeding|\bbelow|\bunder|\bless than|\bat most|\bsub-?)\s*[$€£¥]?\s*$", re.I)

# ------------------------------------------------------------------------------------------------ written numbers
_W = sorted(list(SMALL) + ["hundred", "thousand", "million", "billion", "trillion", "point", "and", "a"], key=len, reverse=True)
WORDNUM_RE = re.compile(r"(?<![A-Za-z])(?:(?:" + "|".join(_W) + r")(?:[ -]+|(?![A-Za-z])))+" , re.I)
DIGIT_WORD_RE = re.compile(r"(?<![A-Za-z])(zero|one|two|three|four|five|six|seven|eight|nine)(?![A-Za-z])", re.I)

def _words_value(phrase: str):
    toks = [w for w in re.split(r"[ -]+", phrase.lower().strip()) if w]
    while toks and toks[-1] in ("and", "a", "point"): toks.pop()
    while toks and toks[0] in ("and",): toks.pop(0)
    if not toks: return None
    if toks == ["one"] or toks == ["a"] or toks == ["zero"]: return None          # prose, not a claim
    if all(w == "a" or w == "and" for w in toks): return None
    total, cur, frac, in_frac, dec = 0.0, 0.0, "", False, 0
    seen_num = False
    for w in toks:
        if in_frac:
            if w in SMALL and SMALL[w] < 10: frac += str(SMALL[w]); continue
            if w in MAG:
                v = (cur + float("0." + frac if frac else 0)) * MAG[w]; total += v; cur = 0; in_frac = False; dec = len(frac); frac = ""
                continue
            return None
        if w == "a": cur = cur or 1; continue
        if w == "and": continue
        if w == "point": in_frac = True; continue
        if w == "dozen": cur = (cur or 1) * 12; seen_num = True; continue
        if w in SMALL: cur += SMALL[w]; seen_num = True; continue
        if w == "hundred": cur = (cur or 1) * 100; seen_num = True; continue
        if w in MAG: total += (cur or 1) * MAG[w]; cur = 0; seen_num = True; continue
        return None
    if in_frac and frac: cur += float("0." + frac); dec = len(frac)
    if not seen_num: return None
    return total + cur, dec

def _cjk_value(s: str):
    """CJK numeral string (possibly with leading digits, e.g. 3.2万) -> value."""
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(百万|千万|万|萬|亿|億|兆|千)", s)
    if m: return float(m.group(1)) * MAG[m.group(2)]
    total, section, cur = 0.0, 0.0, 0
    for ch in s:
        if ch in CJK_D: cur = CJK_D[ch]
        elif ch in CJK_U: section += (cur or 1) * CJK_U[ch]; cur = 0
        elif ch in CJK_B: total += (section + cur) * CJK_B[ch]; section, cur = 0.0, 0
        else: return None
    return total + section + cur

CJK_RE = re.compile(r"[〇零一二两三四五六七八九十百千万萬亿億兆]{2,}|[二两三四五六七八九十]")

# ------------------------------------------------------------------------------------------------ main entry
# grouping the separator rules above do not cover (security audit C-04):
#   "7_000"      underscore groups (code-literal style) -> read as 7000 (it then has to bind like any other number)
#   "7 000"      plain-space groups -> AMBIGUOUS (7000, or 7 and 000?) -> REJECT, never guessed
_USCORE_GROUP = re.compile(r"(?<![\w.,])\d{1,3}(?:_\d{3})+(?![\w.,]|\.\d)")
_SPACE_GROUP = re.compile(r"(?<![\d.,_])\d{1,3}(?: \d{3})+(?![\d,_]|\.\d)")
# number words in other languages: never parsed, always REJECT (the model must write digits). Words that are also common
# English / abbreviations (sept, cent, mil, elf, dos, sei, nove, tres?) are deliberately left out to avoid false rejects.
FOREIGN_WORDS = re.compile(r"(?<![A-Za-z\u00C0-\u024F\u0400-\u04FF])(?:"
    r"zwei|drei|vier|f[uü]nf|sechs|sieben|acht|neun|zehn|zw[oö]lf|zwanzig|drei[sß]ig|vierzig|f[uü]nfzig|hundert|tausend|millionen?|milliarden?|"
    r"deux|trois|quatre|cinq|huit|neuf|dix|onze|douze|vingt|trente|quarante|cinquante|soixante|septante|octante|huitante|nonante|milliards?|"
    r"cuatro|cinco|seis|siete|ocho|nueve|diez|veinte|treinta|cuarenta|cincuenta|cien|ciento|millones|"
    r"quatro|sete|oito|dez|vinte|trinta|quarenta|cinquenta|"
    r"quattro|cinque|sette|otto|dieci|venti|trenta|quaranta|cinquanta|cento|mila|"
    r"twee|vijf|zes|zeven|negen|tien|twintig|honderd|duizend|miljoen|"
    r"один|одна|два|две|три|четыре|пять|шесть|семь|восемь|девять|десять|двадцать|тридцать|сорок|пятьдесят|сто|тысяч[аи]?|миллион(?:а|ов)?"
    r")(?![A-Za-z\u00C0-\u024F\u0400-\u04FF])", re.I)

def normalize_claim(text: str, ids: Iterable[str] = ()) -> NormalizedClaim:
    """Every quantity in text, typed. `ids`: evidence ids quoted in the text (their digits are not claims)."""
    t0 = _prep(text); t, skipped = _mask(t0, ids)
    out = NormalizedClaim(text=text, skipped=skipped)
    pre = []
    for m in _USCORE_GROUP.finditer(t):
        pre.append(Quantity(raw=t0[m.start():m.end()], start=m.start(), end=m.end(), value=float(m.group(0).replace("_", "")), tol=0.5 + 1e-12))
    for m in _SPACE_GROUP.finditer(t):
        pre.append(Quantity(raw=t0[m.start():m.end()], start=m.start(), end=m.end(), status="REJECT", reason="AMBIGUOUS_SPACE_GROUPING"))
    for m in FOREIGN_WORDS.finditer(t):
        pre.append(Quantity(raw=t0[m.start():m.end()], start=m.start(), end=m.end(), form="words", status="REJECT", reason="FOREIGN_NUMBER_WORD"))
    for q in pre:
        out.quantities.append(q); t = t[:q.start] + " " * (q.end - q.start) + t[q.end:]
    used = [False] * len(t)
    def take(a, b):
        for k in range(a, b): used[k] = True
    # 1) digit forms
    i = 0
    for m in NUM_RE.finditer(t):
        a, b = m.start(), m.end()
        sign = m.group("sign")
        if sign:
            before = t[:a].rstrip()
            if before and (before[-1].isdigit() or before[-1] in "%x") : sign = None; a += 1     # '3-5%' / '3 - 5' range
            elif a > 0 and t[a - 1].isalnum(): sign = None; a += 1                               # 'Q3-2' / 'a-1'
        if a > 0 and (t[a - 1].isalpha() or t[a - 1] in "_."): continue            # glued to a word / mid-decimal
        if a > 0 and t[a - 1].isdigit(): continue
        num = m.group("num")
        rv, dec = _read_digits(num)
        q = Quantity(raw=t0[a:b], start=a, end=b, sign_explicit=bool(sign))
        if rv is None:
            q.status, q.reason = "REJECT", dec; out.quantities.append(q); take(a, b); continue
        exp = int(m.group("exp")) if m.group("exp") else 0
        val = rv * 10 ** exp; form = "sci" if exp else "digits"
        tol = 0.5 * 10 ** (exp - dec)
        mult = 1.0; j = b
        sm = SUFFIX_RE.match(t, b)
        if sm:
            suf = sm.group("suf") or sm.group("m")
            nxt = t[sm.end():sm.end() + 3]
            # 'm' is metres/minutes ambiguity: accept as million only right after a currency
            if suf == "m" and not _cur_before(t, a): suf = None
            if suf:
                mult = MAG[suf]; j = sm.end(); form = "suffix" if form == "digits" else form
        val *= mult; tol *= mult
        if mult != 1.0 or exp: tol = min(tol, 0.05 * abs(val)) if val else tol
        if sign == "-": val = -val
        cur = _cur_before(t, a)
        dim, unit, j2, scale = _unit_after(t, j)
        if cur and dim in (None, "currency"):
            dim, unit = "currency", cur if dim is None else unit
        if dim is None: dim, unit = "bare", None
        if dim in ("percent", "pp", "bp"): val *= scale; tol *= scale
        q.raw = t0[a:max(j2, j)]; q.end = max(j2, j); q.value = val; q.tol = tol + 1e-12; q.dimension = dim; q.unit = unit; q.form = form
        cm = CMP_RE.search(t[max(0, a - 16):a] if not cur else t[max(0, a - 20):a].rstrip()[:-1] if t[max(0, a - 20):a].rstrip().endswith(("$", "€", "£", "¥")) else t[max(0, a - 20):a])
        if cm: q.comparator = ">" if cm.group(1).lower().strip() in GT else "<"
        out.quantities.append(q); take(a, q.end)
    # 2) ranges "3-5%" / "10 to 20 bp": propagate a trailing unit to the first number of the pair
    qs = sorted([q for q in out.quantities if q.status == "OK"], key=lambda q: q.start)
    for x, y in zip(qs, qs[1:]):
        gap = t[x.end:y.start]
        if x.dimension == "bare" and y.dimension in ("percent", "bp", "pp", "currency", "time") and re.fullmatch(r"\s*(?:-|to|–|~)\s*", gap):
            x.dimension, x.unit = y.dimension, y.unit
            if y.dimension in ("percent", "pp"): x.value *= 1e-2; x.tol *= 1e-2
            if y.dimension == "bp": x.value *= 1e-4; x.tol *= 1e-4
            if y.sign_explicit is False and x.sign_explicit and gap.strip() == "-": pass
    # 3) English words
    for m in WORDNUM_RE.finditer(t):
        a, b = m.start(), m.end()
        if any(used[a:b]): continue
        phrase = m.group(0)
        r = _words_value(phrase)
        if r is None: continue
        val, dec = r
        bb = a + len(phrase.rstrip(" -"))
        dim, unit, j2, scale = _unit_after(t, bb)
        cur = _cur_before(t, a)
        if cur and dim is None: dim, unit = "currency", cur
        if dim is None: dim, unit = "bare", None
        neg = bool(re.search(r"(?:minus|negative)\s+$", t[max(0, a - 10):a], re.I))
        if neg: val = -val
        tol = min(0.5 * 10 ** (-dec) * (max(1.0, 10 ** (math.floor(math.log10(abs(val))) - 1) if val and not dec else 1.0)), 0.05 * abs(val) if val else 1)
        if dim in ("percent", "pp", "bp"): val *= scale; tol *= scale
        out.quantities.append(Quantity(raw=t0[a:max(j2, bb)], start=a, end=max(j2, bb), value=val, dimension=dim, unit=unit,
                                       tol=tol + 1e-12, sign_explicit=neg, form="words"))
        take(a, max(j2, bb))
    # 4) CJK numerals
    for m in re.finditer(r"\d+(?:\.\d+)?(?:百万|千万|万|萬|亿|億|兆)|" + CJK_RE.pattern, t):
        a, b = m.start(), m.end()
        if any(used[a:b]) and not re.match(r"\d", m.group(0)): continue
        if re.match(r"\d", m.group(0)) and any(q.start == a and q.status == "OK" for q in out.quantities): continue
        v = _cjk_value(m.group(0))
        if v is None: continue
        dim, unit, j2, scale = _unit_after(t, b)
        if dim is None: dim, unit = "bare", None
        if dim in ("percent", "pp", "bp"): v *= scale
        out.quantities.append(Quantity(raw=t0[a:max(j2, b)], start=a, end=max(j2, b), value=v, dimension=dim, unit=unit,
                                       tol=0.05 * abs(v) + 1e-12 if v else 1e-12, form="cjk"))
    out.quantities.sort(key=lambda q: q.start)
    return out

# ------------------------------------------------------------------------------------------------ typed facts + binding
@dataclass
class Fact:
    path: str
    value: float
    dimension: str            # ratio | bp_field | pct_field | currency | count | time | dimensionless | unknown
    evidence_id: Optional[str] = None

_DIMLESS = re.compile(r"(?:^|_)(z|zscore|r2|beta\w*|corr\w*|confidence|t_?stat|sharpe|score|weight|lever\w*|ratio)(?:_|$)", re.I)
_RATIO = re.compile(r"(?:^|_)(ret|return|returns|rate|frac|share|hit_rate\w*|pct_ratio|drift|move|gap|vol|sd|resid\w*|premium|basis|chg|change)(?:_|$)|_ret_|ret_\d+h", re.I)
_BP = re.compile(r"(?:^|_)(bp|bps)(?:_|$)|_bp_", re.I)
_PCT = re.compile(r"(?:^|_)(pct|percent)(?:_|$)", re.I)
_CUR = re.compile(r"(?:^|_)(usd|usdt|usdc|price|px|close|open|high|low|mid\w*|notional|depth\w*|cost_usd\w*|pnl\w*|equity|value|vol_usdt|quote_vol\w*)(?:_|$)", re.I)
_COUNT = re.compile(r"(?:^|_)(n|count|num|precedents|trades|events|shares|contracts|filings)(?:_|$)", re.I)
_TIME = re.compile(r"(?:^|_)(hours|hour|h|minutes|min|days|d|seconds|s|ms|age\w*|horizon\w*)(?:_|$)", re.I)

def field_dimension(path: str) -> str:
    leaf = path.split(".")[-1]
    if _BP.search(leaf): return "bp_field"
    if _PCT.search(leaf): return "pct_field"
    if _TIME.search(leaf) and not _CUR.search(leaf): return "time"
    if _COUNT.search(leaf): return "count"
    if _DIMLESS.search(leaf): return "dimensionless"
    if _CUR.search(leaf) and not re.search(r"quote_vol_24h_usdt|vol", leaf) or re.search(r"usdt|usd", leaf, re.I): return "currency"
    if _RATIO.search(leaf): return "ratio"
    return "unknown"

def facts_from(obj, evidence_id=None, prefix="") -> list:
    out = []
    if isinstance(obj, bool) or obj is None: return out
    if isinstance(obj, (int, float)):
        if math.isfinite(float(obj)): out.append(Fact(prefix or "value", float(obj), field_dimension(prefix or "value"), evidence_id))
        return out
    if isinstance(obj, dict):
        for k, v in obj.items(): out += facts_from(v, evidence_id, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj): out += facts_from(v, evidence_id, f"{prefix}[{i}]")
    elif isinstance(obj, str):
        try:
            x = float(obj)
            if math.isfinite(x) and re.fullmatch(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", obj.strip()):
                out.append(Fact(prefix, x, field_dimension(prefix), evidence_id))
        except ValueError: pass
    return out

_TS = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")
_WIN = re.compile(r"(?:^|_)(\d+)(h|d|m|min|w)(?:_|$)")

def _walk(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items(): yield from _walk(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj): yield from _walk(v, f"{prefix}[{i}]")
    else: yield prefix, obj

def time_facts(payload, evidence_id=None) -> list:
    """Time quantities the evidence itself implies: windows named in field names (ret_24h -> 24 h,
    mean_follow_residual_24h_bp -> 24 h) and gaps between the item's own timestamps (bar_open -> as_of = 1 h).
    Lets '1h bar' / 'within 2 hours' bind to evidence instead of to an unrelated count."""
    from datetime import datetime
    out, stamps = [], []
    for path, v in _walk(payload):
        for m in _WIN.finditer(path.split(".")[-1]):
            n, u = float(m.group(1)), m.group(2)
            hours = n * {"h": 1, "d": 24, "m": 1 / 60, "min": 1 / 60, "w": 168}[u]
            out.append(Fact(f"{path}#window", hours, "time_h", evidence_id))
        if isinstance(v, str) and _TS.match(v):
            try: stamps.append((path, datetime.fromisoformat(v.replace("Z", "+00:00"))))
            except ValueError: pass
    for i, (pa, a) in enumerate(stamps):
        for pb, b in stamps[i + 1:]:
            try: h = abs((a - b).total_seconds()) / 3600
            except TypeError: continue
            if 0 < h <= 24 * 30: out.append(Fact(f"{pa}-{pb}#gap", round(h, 6), "time_h", evidence_id))
    return out

def facts_from_evidence(items: dict) -> list:
    """items: {evidence_id: tool_output dict}."""
    out = []
    for eid, payload in (items or {}).items(): out += facts_from(payload, eid) + time_facts(payload, eid)
    return out

# allowed (quantity dimension -> fact dimensions) and the value transform applied to the FACT before comparing
def _candidates(q: Quantity, f: Fact):
    d, fd, v = q.dimension, f.dimension, f.value
    if d == "bare":
        # bare numbers: identity only (no %/bp rescale). Any fact dimension.
        return [v]
    if d in ("percent", "pp", "bp"):
        if fd in ("ratio", "unknown", "dimensionless"): return [v]          # quantity already a ratio
        if fd == "bp_field": return [v * 1e-4]
        if fd == "pct_field": return [v * 1e-2]
        return []
    if d == "currency":
        return [v] if fd in ("currency", "unknown") else []
    if d == "count":
        return [v] if fd in ("count", "unknown", "dimensionless") else []
    if d == "time":
        if fd == "time_h":                                   # derived facts are in hours
            to_h = {"ms": 1 / 3.6e6, "s": 1 / 3600, "min": 1 / 60, "h": 1, "d": 24, "w": 168}.get(q.unit, None)
            return [v / to_h] if to_h else []
        return [v] if fd in ("time", "unknown") else []
    if d == "multiple":
        return [v] if fd in ("dimensionless", "unknown", "ratio") else []
    return []

def bind(q: Quantity, facts: list):
    """(Fact | None, reason). reason in OK | UNIT_MISMATCH | SIGN_MISMATCH | UNBOUND."""
    near_unit, near_sign = None, None
    for f in facts:
        cands = _candidates(q, f)
        for c in cands:
            if q.comparator and (abs(c) > abs(q.value) if q.comparator == ">" else abs(c) < abs(q.value)):
                return f, "OK"                                # 'depth >1M' bound by a fact that satisfies it
            if abs(abs(c) - abs(q.value)) <= q.tol:
                if q.sign_explicit and c != 0 and (c > 0) != (q.value > 0): near_sign = f; continue
                return f, "OK"
        if q.dimension in ("percent", "pp", "bp"):
            # would it bind if units were ignored? -> unit mismatch (e.g. '55%' vs a *_bp field holding 55)
            raw = q.value
            if q.dimension in ("percent", "pp"): raw = q.value * 1e2
            elif q.dimension == "bp": raw = q.value * 1e4
            if abs(abs(f.value) - abs(raw)) <= max(q.tol * (1e2 if q.dimension in ("percent", "pp") else 1e4 if q.dimension == "bp" else 1), 1e-9):
                near_unit = f
    if near_sign is not None: return near_sign, "SIGN_MISMATCH"
    if near_unit is not None: return near_unit, "UNIT_MISMATCH"
    return None, "UNBOUND"

def check_text(text: str, facts: list, ids: Iterable[str] = (), allow_words: bool = True, extra_values: Iterable[float] = ()):
    """('OK', {}) when every quantity is readable and binds to a compatible fact; else the first failure class and
    details. Order of severity: AMBIGUOUS/REJECT, NUMBER_WORD (if allow_words False), UNIT_MISMATCH, SIGN_MISMATCH,
    UNBOUND_NUMBER."""
    nc = normalize_claim(text, ids)
    facts = list(facts) + [Fact(f"extra[{i}]", float(v), "unknown") for i, v in enumerate(extra_values)]
    bad = nc.rejects
    if bad: return "AMBIGUOUS_NUMBER", {"tokens": [q.raw for q in bad][:5], "reasons": [q.reason for q in bad][:5]}
    if not allow_words:
        w = [q.raw for q in nc.quantities if q.form in ("words", "cjk")]
        if w: return "NUMBER_WORD", {"words": w[:5]}
    fails = {}
    for q in nc.ok:
        f, r = bind(q, facts)
        if r != "OK": fails.setdefault(r, []).append(q.raw)
    for r in ("UNIT_MISMATCH", "SIGN_MISMATCH", "UNBOUND"):
        if r in fails: return ("UNBOUND_NUMBER" if r == "UNBOUND" else r), {"tokens": fails[r][:5]}
    return "OK", {"n_quantities": len(nc.ok)}

def validate_numbers(text: str, evidence_items: dict, cited_ids: Optional[Iterable[str]] = None, allow_words=True, extra_values=()):
    """Bind the numbers in `text` to the facts in the cited evidence items (all items when cited_ids is None)."""
    items = evidence_items if cited_ids is None else {i: evidence_items[i] for i in cited_ids if i in evidence_items}
    return check_text(text, facts_from_evidence(items), ids=list(evidence_items), allow_words=allow_words, extra_values=extra_values)
