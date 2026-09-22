"""Opsi B: DDM bank (spesifikasi Instruksi-Report-v3.md bagian 4, Opsi B).

DDM adalah valuasi ekuitas langsung: arus dividen (DPS) didiskonto dengan
Cost of Equity (CoE), BUKAN WACC. WACC hanya berlaku untuk FCFF
perusahaan non-keuangan; untuk bank, pendekatan berbasis ROE
berkelanjutan (Gordon Growth Model ekuitas) dengan silang cek P/BV
vs ROE (jalur Inverse CoE).
"""


def _median(xs):
    s = sorted(x for x in xs if x is not None)
    if not s:
        return None
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2


def value_bank(net_profits, payout_hist, dps_hist, shares, coe, g, roae_fwd,
               bvps, payout_announced=None):
    """Valuasi DDM bank: jalur Gordon DPS + jalur Inverse CoE.

    net_profits: list laba bersih forecast (3 tahun, mata uang pelaporan).
    payout_hist: list payout ratio historis (fraksi, mis. 0.4 = 40%).
    dps_hist: list DPS historis per saham (dipakai bila payout_hist kosong).
    shares: jumlah saham beredar. coe: Cost of Equity. g: pertumbuhan
    terminal abadi (wajib < coe). roae_fwd: ROAE forward (fraksi).
    bvps: nilai buku per saham forecast. payout_announced: kebijakan
    payout yang diumumkan (fraksi); bila diisi, dipakai langsung dan
    mengalahkan median historis.

    Diskonto memakai CoE dengan konvensi mid-year, sama seperti DCF inti:
    df = (1+coe)^(i+0,5) untuk tahun eksplisit, terminal didiskonto
    penuh (1+coe)^n. BUKAN WACC, karena yang didiskonto adalah arus
    ekuitas, bukan arus perusahaan.
    """
    assert shares and shares > 0, "shares harus > 0"
    assert coe > g, "CoE harus > g agar Gordon terdefinisi"
    assert net_profits, "net_profits forecast tidak boleh kosong"

    if payout_announced is not None:
        payout_used = float(payout_announced)
        payout_basis = "kebijakan dividen yang diumumkan"
    else:
        m = _median(payout_hist or [])
        if m is not None:
            payout_used = m
            payout_basis = "median payout historis di cache"
        elif (dps_hist or []) and net_profits[0]:
            payout_used = dps_hist[-1] * shares / net_profits[0]
            payout_basis = ("DPS terakhir atas laba forecast tahun pertama "
                            "(tanpa payout historis di cache)")
        else:
            payout_used = 0.25
            payout_basis = "asumsi analis 25% (tanpa payout historis di cache)"
    payout_used = max(0.0, min(1.5, payout_used))

    dps_forecast = [max(n, 0) * payout_used / shares for n in net_profits]
    n = len(dps_forecast)
    pv_dps = sum(d / (1 + coe) ** (i + 0.5)
                 for i, d in enumerate(dps_forecast))
    terminal_dps = dps_forecast[-1] * (1 + g)
    tv = terminal_dps / (coe - g)
    tp_gordon = pv_dps + tv / (1 + coe) ** n

    fair_pbv = (roae_fwd - g) / (coe - g)
    tp_inverse = fair_pbv * bvps

    method_note = (
        "DDM ekuitas langsung: DPS didiskonto dengan Cost of Equity "
        "%.1f%%, bukan WACC; payout %.1f%% (%s); terminal Gordon g=%.1f%% "
        "(< CoE); konvensi mid-year; silang cek Inverse CoE "
        "P/BV wajar=(ROAE-g)/(CoE-g)."
        % (coe * 100, payout_used * 100, payout_basis, g * 100)
    ).replace(".", ",")
    return {"payout_used": payout_used, "dps_forecast": dps_forecast,
            "pv_dps": pv_dps, "terminal_dps": terminal_dps,
            "tp_gordon": tp_gordon, "fair_pbv": fair_pbv,
            "tp_inverse": tp_inverse, "method_note": method_note}
