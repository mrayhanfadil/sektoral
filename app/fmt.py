"""Format angka Indonesia: 1.234,5. Nol em-dash, nol emoji di output."""


def _id(x, dec=1):
    s = f"{x:,.{dec}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def rp(v):
    """Harga / per saham: tanpa desimal."""
    return _id(v, 0)


def miliar(v):
    """Nilai besar dalam Rp miliar, 1 desimal."""
    return _id(v / 1e9, 1)


def pct(v, dec=1):
    return _id(v * 100, dec) + "%"


def mult(v, dec=1):
    return _id(v, dec) + "x"


def words(s):
    return len(s.split())
