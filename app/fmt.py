"""Format angka Indonesia: 1.234,5. Nol em-dash, nol emoji di output."""
import math


def _id(x, dec=1):
    if x is None:
        return "n.a."
    try:
        val = float(x)
    except (ValueError, TypeError):
        return "n.a."
    s = f"{val:,.{dec}f}"
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


def mult(v, dec=1):
    if v is None:
        return "n.a."
    try:
        val = float(v)
    except (ValueError, TypeError):
        return "n.a."
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

