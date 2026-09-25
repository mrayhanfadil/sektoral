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
