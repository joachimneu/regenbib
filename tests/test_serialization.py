"""YAML serialization: round-tripping, union discrimination, and line wrapping."""

import os

import marshmallow
import pytest
import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from regenbib.store import (
    ArxivEntry,
    DblpEntry,
    DoiEntry,
    EprintEntry,
    RawBibtexEntry,
    Store,
)

# Printable, single-line, no whitespace padding — keeps the property tests about
# the schema rather than YAML's quoting corner cases.
_TEXT = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    min_size=1,
    max_size=40,
)


@st.composite
def _entries(draw):
    kind = draw(st.sampled_from(['raw', 'dblp', 'arxiv', 'eprint', 'doi']))
    bibtexid = draw(_TEXT)
    if kind == 'raw':
        lines = draw(st.lists(_TEXT, min_size=1, max_size=5))
        return RawBibtexEntry(bibtexid, lines)
    if kind == 'dblp':
        return DblpEntry(bibtexid, draw(_TEXT))
    if kind == 'arxiv':
        return ArxivEntry(bibtexid, draw(_TEXT), draw(st.sampled_from(['', '1', '12'])))
    if kind == 'eprint':
        return EprintEntry(bibtexid, draw(_TEXT))
    return DoiEntry(bibtexid, draw(_TEXT))


class TestUnionDiscrimination:
    """Each YAML mapping must deserialize to the correct entry class — this is the
    marshmallow-dataclass/typeguard union resolution that regressions break first."""

    def test_fixture_types(self, loaded_store):
        by_id = {e.bibtexid: type(e).__name__ for e in loaded_store.entries}
        assert by_id == {
            'fast-authenticated-bft': 'ArxivEntry',
            'tendermint': 'ArxivEntry',
            'pbft': 'DblpEntry',
            'dls': 'DblpEntry',
            'hotstuff2': 'EprintEntry',
            'gafni-losa': 'RawBibtexEntry',
            'naor-keidar': 'RawBibtexEntry',
            'some-doi': 'DoiEntry',
        }

    def test_fields_survive(self, loaded_store):
        by_id = {e.bibtexid: e for e in loaded_store.entries}
        assert by_id['tendermint'].arxivid == '1807.04938'
        assert by_id['tendermint'].version == '3'
        assert by_id['fast-authenticated-bft'].version == ''
        assert by_id['pbft'].dblpid == 'conf/osdi/CastroL99'
        assert by_id['hotstuff2'].eprintid == '2023/397'
        assert by_id['some-doi'].doi == '10.1145/3719027.3765032'
        assert by_id['gafni-losa'].rawbibtex[0] == '@inproceedings{gafni-losa,'

    @pytest.mark.parametrize(
        ('payload', 'expected'),
        [
            ({'bibtexid': 'k', 'dblpid': 'conf/x/Y99'}, DblpEntry),
            ({'bibtexid': 'k', 'arxivid': '1.2', 'version': ''}, ArxivEntry),
            ({'bibtexid': 'k', 'eprintid': '2023/1'}, EprintEntry),
            ({'bibtexid': 'k', 'doi': '10.1/2'}, DoiEntry),
            ({'bibtexid': 'k', 'rawbibtex': ['@misc{k}']}, RawBibtexEntry),
        ],
    )
    def test_each_shape_round_trips_to_its_class(self, payload, expected):
        store = Store.Schema().load({'entries': [payload]})
        assert isinstance(store.entries[0], expected)

    def test_unknown_shape_is_rejected(self):
        with pytest.raises(marshmallow.ValidationError):
            Store.Schema().load({'entries': [{'bibtexid': 'k', 'nonsense': 'x'}]})


class TestRoundTrip:
    def test_real_fixture_is_byte_identical(self, references_yaml, tmp_path):
        """load -> dump reproduces the checked-in file exactly, so import/scrub
        never introduce spurious diffs in a user's references.yaml."""
        out = tmp_path / 'out.yaml'
        Store.load(references_yaml).dump(str(out))
        with open(references_yaml) as f:
            expected = f.read()
        assert out.read_text() == expected

    def test_dump_then_load_preserves_entries(self, loaded_store, tmp_path):
        out = tmp_path / 'out.yaml'
        loaded_store.dump(str(out))
        assert Store.load(str(out)).entries == loaded_store.entries

    @settings(max_examples=75, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(entries=st.lists(_entries(), max_size=8))
    def test_arbitrary_stores_round_trip(self, entries, tmp_path):
        out = tmp_path / 'prop.yaml'
        Store(entries).dump(str(out))
        assert Store.load(str(out)).entries == entries

    def test_load_or_empty_on_missing_file(self, tmp_path):
        store = Store.load_or_empty(str(tmp_path / 'does-not-exist.yaml'))
        assert store.entries == []

    def test_load_raises_on_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            Store.load(str(tmp_path / 'does-not-exist.yaml'))

    def test_keys_are_sorted(self, tmp_path):
        out = tmp_path / 'out.yaml'
        Store([ArxivEntry('k', '1234.5678', '2')]).dump(str(out))
        emitted = [ln.strip().lstrip('- ') for ln in out.read_text().splitlines()]
        emitted = [ln.split(':')[0] for ln in emitted if ':' in ln]
        assert emitted == ['entries', 'arxivid', 'bibtexid', 'version']


class TestNoForcedLineWrapping:
    """Store.dump passes width=math.inf to PyYAML; otherwise it wraps at 80
    columns, mangling long author lists into multi-line scalars."""

    LONG_AUTHORS = (
        '    author = "Naor, Oded and Baudet, Mathieu and Malkhi, Dahlia '
        'and Spiegelman, Alexander",'
    )

    def test_long_line_is_not_split(self, tmp_path):
        out = tmp_path / 'out.yaml'
        Store([RawBibtexEntry('k', [self.LONG_AUTHORS])]).dump(str(out))
        text = out.read_text()
        assert len(self.LONG_AUTHORS) > 80  # the fixture must actually be long
        assert self.LONG_AUTHORS in text
        assert max(len(ln) for ln in text.splitlines()) > 80

    def test_very_long_scalar_stays_on_one_line(self, tmp_path):
        out = tmp_path / 'out.yaml'
        payload = 'x' * 500
        Store([DblpEntry('k', payload)]).dump(str(out))
        lines = out.read_text().splitlines()
        assert any(payload in ln for ln in lines)

    def test_embedded_newlines_still_break(self, tmp_path):
        """Semantic breaks are preserved; only width-driven wrapping is off."""
        out = tmp_path / 'out.yaml'
        Store([RawBibtexEntry('k', ['line one\nline two'])]).dump(str(out))
        reloaded = Store.load(str(out))
        assert reloaded.entries[0].rawbibtex == ['line one\nline two']


class TestOnDiskFormat:
    def test_dump_is_valid_plain_yaml(self, loaded_store, tmp_path):
        out = tmp_path / 'out.yaml'
        loaded_store.dump(str(out))
        raw = yaml.safe_load(out.read_text())
        assert set(raw) == {'entries'}
        assert len(raw['entries']) == len(loaded_store.entries)

    def test_no_python_specific_tags(self, loaded_store, tmp_path):
        out = tmp_path / 'out.yaml'
        loaded_store.dump(str(out))
        assert '!!python' not in out.read_text()

    def test_dump_overwrites_rather_than_appends(self, loaded_store, tmp_path):
        out = tmp_path / 'out.yaml'
        out.write_text('entries: []\n' + '# stale content\n' * 50)
        loaded_store.dump(str(out))
        assert 'stale content' not in out.read_text()
        assert os.path.getsize(out) > 0
