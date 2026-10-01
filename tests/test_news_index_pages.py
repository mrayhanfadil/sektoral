"""Topic, tag, search and quote pages are not articles (app.news_sources)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import news_sources as N  # noqa: E402


def test_topic_pages_are_rejected_by_path_or_title():
    assert N.index_page("https://www.bisnis.com/topic/2539/bbri", "Berita BBRI")
    assert N.index_page("https://x.id/tag/bbri", "BBRI")
    assert N.index_page("https://x.id/news", "Berita BBRI Terkini dan Terbaru Hari Ini | Bisnis.com")
    assert N.index_page("https://market.bisnis.com/read/20260916/7/1/bri-buyback",
                        "BRI (BBRI) Tuntaskan Buyback Saham") is None


def test_the_register_records_the_rejection():
    items = [{"title": "Berita BBRI Terkini dan Terbaru Hari Ini | Bisnis.com",
              "date": "2026-09-23", "url": "https://www.bisnis.com/topic/2539/bbri",
              "snippet": "BBRI"},
             {"title": "BBRI tuntaskan buyback", "date": "2026-09-16",
              "url": "https://market.bisnis.com/read/20260916/7/1/bri-buyback", "snippet": "BBRI"}]
    out = N.build_register("BBRI", "PT Bank Rakyat Indonesia (Persero) Tbk", "2026-09-24", [], items)
    assert [a["title"] for a in out["articles"]] == ["BBRI tuntaskan buyback"]
    assert any("topik/indeks" in r["reason"] for r in out["rejected"])


def test_quote_and_company_profile_pages_are_rejected():
    assert N.index_page("https://www.cnbcindonesia.com/market-data/quote/SIDO.JK",
                        "SIDO (INDUSTRI JAMU DA) - Harga, Analisis, dan Berita Terkini - CNBC Indonesia")
    assert N.index_page("https://www.reuters.com/markets/companies/B2O.F/profile",
                        "(B2O.F) | Stock Price & Latest News | Reuters")
    assert N.index_page("https://x.id/news", "(B2O.F) | Stock Price & Latest News | Reuters")
    assert N.index_page("https://www.idnfinancials.com/news/1/powr-data-center-power",
                        "Cikarang Listrindo (POWR) wins data-centre power deals") is None


JAPFA = "JAPFA Comfeed Indonesia Tbk"
ROUNDUP = {  # JPFA's only Sectors article in the 25 Sep run: a foreign-flow list
    "title": "Foreign investors net buy PT Bank Rakyat Indonesia Tbk and other top stocks on "
             "May 25, 2026",
    "timestamp": "2026-05-26T08:33:00", "source": "https://investor.id/stock/440479/asing",
    "body": "On May 25, 2026, foreign investors posted net purchases of Rp 147.1 billion in PT "
            "Bank Rakyat Indonesia Tbk, Rp 112.1 billion in PT Merdeka Copper Gold Tbk, Rp 82.1 "
            "billion in PT Bank Central Asia Tbk, Rp 26 billion in PT United Tractors Tbk and "
            "Rp 7.2 billion in PT Japfa Comfeed Indonesia Tbk.",
    "symbols": ["BBRI.JK", "MDKA.JK", "BBCA.JK", "UNTR.JK", "JPFA.JK"]}


def test_a_sectors_article_must_name_the_issuer():
    """Sectors tags an article with every ticker it lists; the tag alone is not
    relevance. The issuer must be named in the title or body."""
    other = {"title": "Bank Mandiri books record profit", "timestamp": "2026-09-20",
             "source": "https://x.id/read/1/mandiri", "symbols": ["BMRI.JK", "JPFA.JK"],
             "body": "PT Bank Mandiri (Persero) Tbk reported a record first-half profit."}
    own = {"title": "Japfa Comfeed raises poultry output", "timestamp": "2026-09-21",
           "source": "https://x.id/read/2/japfa", "symbols": ["JPFA.JK"],
           "body": "The feed maker plans a new hatchery."}
    by_ticker = {**own, "title": "Feed prices ease", "source": "https://x.id/read/3/feed",
                 "body": "JPFA and peers see lower corn costs in the second half."}
    out = N.build_register("JPFA", JAPFA, "2026-09-24", [other, own, by_ticker], [])
    assert sorted(a["title"] for a in out["articles"]) == ["Feed prices ease",
                                                     "Japfa Comfeed raises poultry output"]
    assert [r["reason"] for r in out["rejected"]] == ["issuer identity not verified in title/body"]


def test_a_market_roundup_naming_the_issuer_in_passing_is_rejected():
    out = N.build_register("JPFA", JAPFA, "2026-09-24", [ROUNDUP], [])
    assert out["articles"] == []
    assert out["rejected"][0]["reason"].startswith("market roundup naming 5 issuers")
    # The same list is the issuer's article when its title names it.
    headline = {**ROUNDUP, "title": "Foreign investors net buy Japfa Comfeed and other stocks"}
    assert N.build_register("JPFA", JAPFA, "2026-09-24", [headline], [])["articles"]
    # A Tavily snippet listing four issuers counts the same way.
    tavily = {"title": "Asing Net Sell Rp 791 Miliar, Intip Saham yang Banyak Dijual",
              "date": "2026-09-20", "url": "https://x.id/read/4/asing", "snippet": ROUNDUP["body"]}
    out = N.build_register("JPFA", JAPFA, "2026-09-24", [], [tavily])
    assert out["articles"] == [] and "market roundup" in out["rejected"][0]["reason"]
