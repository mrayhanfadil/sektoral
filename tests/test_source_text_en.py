"""English for Indonesian source text quoted in report prose (data/source_text_en)."""
import json

import pytest

from app import prose_lang, scrub

FILES = sorted(prose_lang.SOURCE_TEXT_DIR.glob("*.json"))


def _load(path):
    """The file's pairs, refusing a key written twice (json.loads keeps the last)."""
    def pairs(items):
        keys = [k for k, _ in items]
        assert len(keys) == len(set(keys)), f"{path.name}: duplicate key"
        return dict(items)
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)


def test_the_directory_holds_dictionaries():
    assert FILES
    assert prose_lang.SOURCE_TEXT_DIR.joinpath("shared.json") in FILES


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_each_entry_is_english_with_the_same_figures(path):
    doc = _load(path)
    assert isinstance(doc, dict) and doc
    for id_text, en_text in doc.items():
        assert isinstance(id_text, str) and id_text.strip()
        assert isinstance(en_text, str) and en_text.strip(), id_text
        assert en_text != id_text, id_text
        # attach() drops an English field whose figures differ from the Indonesian.
        assert prose_lang.figures(id_text) == prose_lang.figures(en_text), id_text
        assert not (scrub.contains_banned(en_text) and not scrub.contains_banned(id_text)), en_text


def test_an_indonesian_text_has_one_english_across_files():
    seen = {}
    for path in FILES:
        for id_text in _load(path):
            assert id_text not in seen, f"{id_text!r} in {seen.get(id_text)} and {path.name}"
            seen[id_text] = path.name


def test_source_returns_the_dictionary_english_in_an_english_build():
    id_text, en_text = next(iter(_load(FILES[0]).items()))
    assert prose_lang.source(id_text) == id_text
    with prose_lang.building("en"):
        assert prose_lang.source(id_text) == en_text
