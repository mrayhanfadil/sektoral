"""Published mining route (FY EV/EBITDA on the validated interim scenario).

The fixture is AMMN's validated live plan of 2026-09-24. Before this test the
route had no coverage and crashed on an undefined name once a scenario
validated.
"""
import json
from pathlib import Path

from app import build

PLAN = json.loads((Path(__file__).parent / "fixtures" / "ammn_interim_plan.json").read_text())


def test_ammn_publishes_on_the_validated_interim_scenario(tmp_path):
    doc = build.build("AMMN", tmp_path, as_of="2026-09-24", assumption_plan=PLAN,
                      assumption_status="validated")
    assert doc["meta"]["status"] == "distributable_assumption_led"
    assert doc["harness"]["blockers"] == []
    assert doc["meta"]["rating"] in {"Buy", "Hold", "Sell"} and doc["meta"]["tp"]
    titles = {e["judul"] for e in doc["exhibits"]}
    # The branch that raised NameError builds this table from the sales bridge.
    assert "Volume penjualan dan net realized price per logam" in titles
    text = " ".join(p["isi"] for p in doc["cover"]["paragraf"])
    assert "Q4 2027" not in text and "Risiko utama:" in text
