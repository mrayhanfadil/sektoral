"""Cache-only news filtering, provenance validation, and report integration."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import build, intake, narrative, news  # noqa: E402


def test_catalysts_use_validated_paraphrases_not_raw_trade_call_headlines():
    raw_only = {"news": [{"title": "Stocks to Buy now", "timestamp": "2026-09-07"}],
                "news_analysis": [], "corp_actions": []}
    rows = narrative._katalis(raw_only)
    assert all("Stocks to Buy" not in cell for row in rows for cell in row)

    validated = {**raw_only, "news_analysis": [{
        "summary": "Foreign inflow returned to the market",
        "connection": "The flow may affect demand for Indonesian equities.",
        "timestamp": "2026-09-07T10:00:00",
    }]}
    rows = narrative._katalis(validated)
    assert rows[0][0] == "Foreign inflow returned to the market"
    assert rows[0][2] == validated["news_analysis"][0]["connection"]


def test_relevant_news_is_ticker_filtered_and_as_of_capped():
    payload = {"results": [
        {"title": "AMMN recent", "timestamp": "2026-09-10T12:00:00",
         "symbols": ["AMMN.JK"]},
        {"title": "AMMN future", "timestamp": "2026-09-12T12:00:00",
         "symbols": ["AMMN.JK"]},
        {"title": "Other issuer", "timestamp": "2026-09-10T12:00:00",
         "symbols": ["BBCA.JK"]},
    ]}

    rows = news.relevant_rows("AMMN", payload, "2026-09-11")

    assert [row["title"] for row in rows] == ["AMMN recent"]


def test_report_includes_only_agent_news_matched_to_current_cache(monkeypatch, tmp_path):
    cached_intake, _ = intake.load("AMMN")
    article = cached_intake["news"][0]
    analysis_dir = tmp_path / "agent-news"
    analysis_dir.mkdir()
    (analysis_dir / "AMMN.json").write_text(json.dumps({
        "ticker": "AMMN",
        "news_analysis": [{
            "summary": "A jump in copper benchmarks coincided with renewed market interest.",
            "connection": "The commodity move may support sentiment and netback expectations, "
                          "but it cannot quantify revenue without cached volume and realized-price data.",
            "caveat": "Media context only; not company guidance and not an earnings assumption.",
            "source": f"sectors_cache /news/ | {article['title']} | {article['source']}",
            "timestamp": article["timestamp"],
        }],
    }), encoding="utf-8")
    monkeypatch.setattr(news, "NEWS_ANALYSIS_DIR", analysis_dir)

    doc = build.build("AMMN", tmp_path / "report")

    news_exhibit = next(item for item in doc["exhibits"]
                        if item["judul"] == "Konteks berita dari cache dan implikasi")
    section = next(item for item in doc["bagian"]
                   if item["judul"] == "Konteks berita dan kaitannya ke tesis")
    assert news_exhibit["data"]["rows"][0][1].startswith("A jump in copper")
    assert article["source"] in news_exhibit["catatan_sumber"]
    assert section["exhibit"] == [news_exhibit]
    assert "tp" not in doc["meta"]


def test_external_or_unmatched_news_narratives_are_ignored(tmp_path):
    actual = {"title": "Cached headline", "source": "https://cache.test/item",
              "timestamp": "2026-09-10T10:00:00", "symbols": ["AMMN.JK"],
              "body": "News body from the allowed cache record."}
    forged = [{"summary": "Unrelated external item", "connection": "A narrative connection to AMMN.",
               "caveat": "Cached", "source": "sectors_cache /news/ | Other headline",
               "timestamp": "2026-09-10T10:00:00"}]

    assert news.validate_analysis("AMMN", forged, [actual], "2026-09-11") == []


def test_news_analysis_requires_exact_cached_timestamp_and_no_extra_url():
    article = {
        "title": "Copper supply tightens",
        "source": "https://news.example.test/copper",
        "timestamp": "2026-09-10T10:00:00",
        "symbols": ["AMMN.JK"],
        "body": "Benchmark copper advanced amid tighter supply.",
    }
    analysis = [{
        "summary": "Benchmark copper strengthened as traders priced in tighter supply.",
        "connection": "This may lift sentiment and expected netbacks, but does not establish AMMN's realized price.",
        "caveat": "Media context only; not company guidance.",
        "source": "sectors_cache /news/ | Copper supply tightens | https://news.example.test/copper",
        "timestamp": article["timestamp"],
    }]

    assert len(news.validate_analysis("AMMN", analysis, [article], "2026-09-11")) == 1
    assert news.validate_analysis(
        "AMMN", [{**analysis[0], "timestamp": "2026-09-09T10:00:00"}],
        [article], "2026-09-11") == []
    assert news.validate_analysis(
        "AMMN", [{**analysis[0], "source": analysis[0]["source"] +
                  " https://outside.example.test/story"}], [article], "2026-09-11") == []
    assert news.validate_analysis(
        "AMMN", [{**analysis[0], "connection": "Buy this stock before the rally."}],
        [article], "2026-09-11") == []


def test_third_party_trade_call_headline_is_not_published_even_as_source():
    article = {
        "title": "Stocks to Buy before earnings",
        "source": "https://news.example.test/story",
        "timestamp": "2026-09-10T10:00:00",
        "symbols": ["BBCA.JK"],
        "body": "A third-party market comment.",
    }
    analysis = [{
        "summary": "Investors reviewed a sector update.",
        "connection": "This provides media context for the issuer.",
        "caveat": "The article does not quantify company earnings.",
        "source": "sectors_cache /news/ | Stocks to Buy before earnings | " + article["source"],
        "timestamp": article["timestamp"],
    }]
    assert news.validate_analysis("BBCA", analysis, [article], "2026-09-11") == []

    article["title"] = "Banking market update"
    analysis[0]["source"] = "sectors_cache /news/ | Banking market update | " + article["source"]
    analysis[0]["connection"] = "The broker recommends buying this issuer before earnings."
    assert news.validate_analysis("BBCA", analysis, [article], "2026-09-11") == []
