"""Auto deep-dive into cached news links: extract, cache, enrich, validate."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.forecast_assumptions.run import _source_payload, _validate  # noqa: E402
from app import news_fetch, store  # noqa: E402


HTML_SAMPLE = """<html><head><title>Sample issuer story</title></head><body>
<nav>menu noise</nav><article>
<h1>Issuer posts strong quarter</h1>
<p>PT Example Tbk reported revenue growth driven by higher sales volume in the second quarter,
with management noting improved operating efficiency across its main plants.</p>
<p>The company also announced a new distribution agreement that is expected to support
sales over the coming quarters, while capital expenditure remains focused on maintenance.</p>
</article></body></html>"""


def test_extract_text_skips_nav_and_keeps_paragraphs():
    out = news_fetch.extract_text(HTML_SAMPLE)
    assert "Sample issuer story" in out["title"]
    assert "revenue growth" in out["text"]
    assert "menu noise" not in out["text"]


def test_enrich_one_uses_disk_cache_offline(tmp_path, monkeypatch):
    url = "https://contoh.test/berita/1"
    record = {"source_url": url, "title": "Judul cache", "timestamp": "2026-09-10T10:00:00",
              "fetch_status": "fetched", "fetched_at": "2026-09-11T00:00:00+00:00",
              "full_text": "Teks lengkap tersimpan untuk pengujian offline.",
              "full_length": 46, "title_extracted": "Judul cache"}
    store.put(news_fetch.COLLECTION, news_fetch._url_key(url), record, tmp_path)
    monkeypatch.setenv("SEKTORAL_DISABLE_DEEPDIVE", "1")
    out = news_fetch.enrich_one({"source": url, "title": "Judul cache",
                                 "timestamp": "2026-09-10T10:00:00"}, db=tmp_path)
    assert out["full_text"].startswith("Teks lengkap tersimpan")
    assert out["fetch_status"] == "fetched"


def test_enrich_one_bad_url_never_raises(tmp_path):
    out = news_fetch.enrich_one({"source": "notaurl", "title": "x",
                                 "timestamp": "2026-09-10T10:00:00"}, db=tmp_path)
    assert out["fetch_status"] == "unavailable_bad_url"
    assert out["full_text"] == ""


def test_enrich_all_preserves_order_offline(tmp_path, monkeypatch):
    monkeypatch.setenv("SEKTORAL_DISABLE_DEEPDIVE", "1")
    rows = [{"source": "https://contoh.test/a", "title": "A",
             "timestamp": "2026-09-10T10:00:00", "body": "snippet a"},
            {"source": "notaurl", "title": "B",
             "timestamp": "2026-09-10T10:00:00", "body": "snippet b"}]
    out = news_fetch.enrich_all(rows, db=tmp_path)
    assert [item["source_url"] for item in out] == ["https://contoh.test/a", "notaurl"]
    assert out[0]["fetch_status"] == "unavailable_offline"


def test_source_payload_carries_full_text_and_quote_validates():
    intake = {"ticker": "AMMN", "as_of": "2026-09-11", "model_profile": "finite_life_mining",
              "latest_official_actual": None, "official_evidence": {},
              "news": [{"title": "Copper update", "timestamp": "2026-09-10T10:00:00",
                        "source": "https://news.test/copper", "body": "snippet"}],
              "news_full": [{"source_url": "https://news.test/copper",
                             "fetch_status": "fetched", "fetched_at": "2026-09-11T00:00:00+00:00",
                             "full_text": "Copper output rose on higher mill throughput."}]}
    source = _source_payload(intake)
    assert source["news"][0]["full_text"].startswith("Copper output")
    plan = {"news_effects": [{"article_index": 0, "title": "Copper update",
                              "timestamp": "2026-09-10T10:00:00",
                              "source_url": "https://news.test/copper",
                              "driver": "revenue_growth_pp", "change": 2.0,
                              "years": [2026, 2027],
                              "factual_basis": "大多 fact basis indonesia cukup panjang",
                              "mechanism": "mekanisme yang cukup panjang dijelaskan",
                              "uncertainty": "ketidakpastian yang cukup panjang отсутствует",
                              "rationale": "Rasional analis yang cukup panjang untuk validasi.",
                              "full_text_quote": "higher mill throughput"}],
            "interim_scenario": None}
    # fix rationale language length fields to valid Indonesian text
    plan["news_effects"][0]["factual_basis"] = "Basis fakta dari teks lengkap yang cukup panjang."
    plan["news_effects"][0]["mechanism"] = "Mekanisme operasi yang cukup panjang dijelaskan."
    plan["news_effects"][0]["uncertainty"] = "Ketidakpastian harga dan volume yang cukup panjang."
    assert _validate(plan, source) == []
    bad = json.loads(json.dumps(plan))
    bad["news_effects"][0]["full_text_quote"] = "kutipan yang tidak ada di teks"
    assert any("full_text_quote" in problem for problem in _validate(bad, source))


def test_new_facts_finds_material_beyond_snippet():
    snippet = "IHSG fell as BBRI recorded large transactions."
    full = ("IHSG fell as BBRI recorded large transactions on Tuesday. "
            "Management approved a new efficiency program that cuts operating costs "
            "by renegotiating supplier contracts across Java. "
            "Trading volume reached high levels across the market.")
    facts = news_fetch.new_facts(snippet, full)
    assert any("efficiency program" in fact for fact in facts)
