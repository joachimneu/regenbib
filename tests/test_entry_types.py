"""Parsing and identity behavior of the five entry types in ``store.py``."""

import pytest

from regenbib.store import (
    ArxivEntry,
    DblpEntry,
    DoiEntry,
    EprintEntry,
    RawBibtexEntry,
)


class TestArxivEntryFromManual:
    @pytest.mark.parametrize(
        ('manual', 'arxivid', 'version'),
        [
            ('2102.07932', '2102.07932', ''),
            ('2102.07932v3', '2102.07932', '3'),
            ('  2102.07932V2  ', '2102.07932', '2'),  # stripped and lowercased
            ('cs/0102003', 'cs/0102003', ''),  # old-style identifier
        ],
    )
    def test_parses(self, manual, arxivid, version):
        entry = ArxivEntry.from_manual('some-key', manual)
        assert (entry.bibtexid, entry.arxivid, entry.version) == ('some-key', arxivid, version)

    @pytest.mark.parametrize('manual', ['arXiv:2102.07932', 'arxiv/2102.07932', ''])
    def test_rejects(self, manual):
        with pytest.raises(AssertionError):
            ArxivEntry.from_manual('some-key', manual)

    def test_version_split_is_on_first_v_only(self):
        entry = ArxivEntry.from_manual('k', '1234.5678v1v2')
        assert (entry.arxivid, entry.version) == ('1234.5678', '1v2')


class TestEprintEntryFromManual:
    @pytest.mark.parametrize(
        ('manual', 'eprintid'),
        [('2023/397', '2023/397'), ('  2024/1533 ', '2024/1533')],
    )
    def test_parses(self, manual, eprintid):
        entry = EprintEntry.from_manual('k', manual)
        assert entry.eprintid == eprintid

    @pytest.mark.parametrize(
        'manual',
        [
            'eprint:2023/397',  # contains 'eprint'
            'https://eprint.iacr.org/2023/397',  # contains both banned words
            '2023-397',  # missing the required '/'
            '',
        ],
    )
    def test_rejects(self, manual):
        with pytest.raises(AssertionError):
            EprintEntry.from_manual('k', manual)


class TestDoiEntryFromManual:
    @pytest.mark.parametrize(
        'manual',
        [
            '10.1145/3719027.3765032',
            'doi:10.1145/3719027.3765032',
            'DOI:10.1145/3719027.3765032',
            'https://doi.org/10.1145/3719027.3765032',
            'http://doi.org/10.1145/3719027.3765032',
            '  10.1145/3719027.3765032  ',
        ],
    )
    def test_prefixes_are_stripped(self, manual):
        assert DoiEntry.from_manual('k', manual).doi == '10.1145/3719027.3765032'

    def test_case_is_preserved(self):
        # Unlike arXiv/ePrint parsing, DOIs must not be lowercased.
        assert DoiEntry.from_manual('k', 'doi:10.1145/AbCd').doi == '10.1145/AbCd'

    @pytest.mark.parametrize('manual', ['', '   ', 'doi:'])
    def test_rejects_empty(self, manual):
        with pytest.raises(AssertionError):
            DoiEntry.from_manual('k', manual)


class TestSortKeys:
    def test_source_is_the_class_name(self):
        cases = [
            (RawBibtexEntry('k', ['@misc{k}']), 'RawBibtexEntry'),
            (DblpEntry('k', 'conf/x/Y99'), 'DblpEntry'),
            (ArxivEntry('k', '1234.5678', ''), 'ArxivEntry'),
            (EprintEntry('k', '2023/397'), 'EprintEntry'),
            (DoiEntry('k', '10.1/2'), 'DoiEntry'),
        ]
        for entry, expected in cases:
            assert entry.sortkey_source == expected

    def test_bibtexid_passthrough(self):
        assert DblpEntry('the-key', 'conf/x/Y99').sortkey_bibtexid == 'the-key'

    def test_contentid_ignores_bibtexid(self):
        # Entries pointing at the same work share a content id, which is what
        # lets --biblatex-group collapse duplicates.
        a = DblpEntry('key-a', 'conf/x/Y99')
        b = DblpEntry('key-b', 'conf/x/Y99')
        assert a.sortkey_contentid == b.sortkey_contentid

    def test_contentid_distinguishes_different_works(self):
        a = DblpEntry('k', 'conf/x/Y99')
        b = DblpEntry('k', 'conf/x/Z00')
        assert a.sortkey_contentid != b.sortkey_contentid

    def test_contentid_distinguishes_entry_types(self):
        a = EprintEntry('k', '2023/397')
        b = DoiEntry('k', '2023/397')
        assert a.sortkey_contentid != b.sortkey_contentid

    def test_arxiv_contentid_tracks_version(self):
        unversioned = ArxivEntry('k', '1234.5678', '')
        versioned = ArxivEntry('k', '1234.5678', '3')
        assert unversioned.sortkey_contentid != versioned.sortkey_contentid

    def test_rawbibtex_contentid_is_content_addressed(self):
        a = RawBibtexEntry('k', ['@misc{k,', '  title = "T"', '}'])
        b = RawBibtexEntry('other', ['@misc{k,', '  title = "T"', '}'])
        c = RawBibtexEntry('k', ['@misc{k,', '  title = "DIFFERENT"', '}'])
        assert a.sortkey_contentid == b.sortkey_contentid
        assert a.sortkey_contentid != c.sortkey_contentid
