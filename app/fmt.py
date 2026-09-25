"""Format angka Indonesia: 1.234,5. Nol em-dash, nol emoji di output."""
import math
import re


def _id(x, dec=1):
    if x is None:
        return "n.a."
    try:
        val = float(x)
    except (ValueError, TypeError):
        return "n.a."
    s = f"{val:,.{dec}f}"
    if s.startswith("-") and not any(c in "123456789" for c in s):
        s = s[1:]  # a value that rounds to zero is 0, not -0
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


# IDX price fractions (fraksi harga): tick size by price band.
_TICKS = ((200, 1), (500, 2), (2000, 5), (5000, 10), (float("inf"), 25))


def tick(v):
    """Round a per-share value to the IDX tick for its price band.

    A flat Rp10 rounding collapsed low-priced targets (Rp56 stock: base,
    downside and upside all became Rp30)."""
    if v is None:
        return None
    step = next(size for bound, size in _TICKS if abs(v) < bound)
    units = math.floor(abs(v) / step + 0.5)  # half-up, not banker's rounding
    return int(math.copysign(units * step, v)) if units else 0


def rp(v):
    """Harga / per saham: tanpa desimal."""
    if v is None:
        return "n.a."
    try:
        val = float(v)
    except (ValueError, TypeError):
        return "n.a."
    return _id(val, 0)


def miliar(v):
    """Nilai besar dalam Rp miliar, 1 desimal."""
    if v is None:
        return "n.a."
    try:
        val = float(v)
    except (ValueError, TypeError):
        return "n.a."
    return _id(val / 1e9, 1)


def pct(v, dec=1):
    if v is None:
        return "n.a."
    try:
        val = float(v)
    except (ValueError, TypeError):
        return "n.a."
    return _id(val * 100, dec) + "%"


# Above this a P/E or P/B says only that the base (earnings, equity) is tiny.
MULT_CAP = 100


def mult(v, dec=1, cap=None):
    """``cap``: values above it read "n.m." (not meaningful), e.g. a 9.141,7x P/E."""
    if v is None:
        return "n.a."
    try:
        val = float(v)
    except (ValueError, TypeError):
        return "n.a."
    if cap is not None and val > cap:
        return "n.m."
    return _id(val, dec) + "x"


def words(s):
    return len(s.split())


DEFAULT_SOURCE = "Source: Company, Sektoral Estimates"


def pe(v, dec=1):
    """P/E ratio: nilai <= 0 atau > 200 menghasilkan 'n.m.' (not meaningful).

    House format guard: rasio P/E negatif atau ekstrem (> 200) tidak bermakna
    secara analitis sehingga harus diformat sebagai 'n.m.'.
    """
    if v is None:
        return "n.a."
    try:
        val = float(v)
    except (ValueError, TypeError):
        return "n.a."
    if val <= 0 or val > 200:
        return "n.m."
    return mult(val, dec)


# Explicit alias
fmt_pe = pe


def margin(v, dec=1):
    """Marjin laba/rugi dalam notasi persentase Indonesia: koma desimal, persen."""
    if v is None:
        return "n.a."
    try:
        val = float(v)
    except (ValueError, TypeError):
        return "n.a."
    return pct(val, dec)


def revenue_idr(v, dec=1, in_miliar=True):
    """Pendapatan dalam format standar Indonesia: pemisah ribuan titik, desimal koma."""
    if v is None:
        return "n.a."
    try:
        val = float(v)
    except (ValueError, TypeError):
        return "n.a."
    if in_miliar:
        return miliar(val)
    return _id(val, dec)


def source_citation(note: str = "") -> str:
    """Baris sitasi sumber sesuai standar house report format.

    Selalu berkonformasi ke 'Source: Company, Sektoral Estimates' atau
    provenansi terverifikasi ('Source: ...').
    """
    if not note or not str(note).strip():
        return DEFAULT_SOURCE
    s = str(note).strip()
    if not s.startswith("Source:"):
        return f"Source: {s}"
    return s


def provenance_detail(note) -> str:
    """An exhibit's own provenance (data set, dates, method, caveats) with the
    house line taken off: what the report's source appendix prints for it.
    The exhibit footer itself is always DEFAULT_SOURCE (spec §5.5)."""
    detail = re.sub(r"^\s*(Source|Sumber)\s*:\s*", "", str(note or "")).strip()
    detail = re.sub(r"^Company,\s*Sektoral Estimates[.;,]?\s*", "", detail)
    detail = re.sub(r"^Sectors,\s*Sektoral Estimates", "Sectors", detail)
    detail = re.sub(r"^Sektoral Estimates[.;,]?\s*", "", detail)
    return detail if detail.strip(" ;.") else ""


def house_source_line(note) -> str:
    """The house line followed by the exhibit's own provenance: the full
    audit form of a source note (trace, appendix), not the exhibit footer."""
    detail = provenance_detail(note)
    return DEFAULT_SOURCE + (f"; {detail}" if detail else "")


_NEG_MONEY = re.compile(r"(?<![\w(])((?:Rp|US\$)\s?)[-−]\s?(\d[\d.,]*(?:\s?(?:triliun|miliar|juta|ribu)\b)?)")
_NEG_CELL = re.compile(r"^[-−]\s?(\d[\d.,]*)(%|x|\s?pp|\s?bps)?$")


def bracket_negatives(text: str, whole: bool = False) -> str:
    """Spec §5.5: negative figures in brackets. Money written inline
    ("Rp-39,8 miliar") becomes "(Rp39,8 miliar)" anywhere in `text`; with
    `whole`, a bare negative figure ("-4,1%", "-12") filling the text does too.
    Ranges ("2024-2025", "8-10x") are left alone."""
    if not isinstance(text, str):
        return text
    out = _NEG_MONEY.sub(r"(\1\2)", text)
    if whole:
        out = _NEG_CELL.sub(lambda m: f"({m.group(1)}{m.group(2) or ''})", out.strip())
    return out


def is_valid_source_citation(note: str) -> bool:
    """Validasi baris sitasi sumber agar sesuai aturan house format."""
    if not note or not isinstance(note, str):
        return False
    s = note.strip()
    return s.startswith("Source: ") and len(s) > len("Source: ")


def clean_dashes(s: str) -> str:
    """Bersihkan en-dash (U+2013) dan em-dash (U+2014) dari teks."""
    if not isinstance(s, str):
        return s
    return s.replace("\u2014", " - ").replace("\u2013", "-")

