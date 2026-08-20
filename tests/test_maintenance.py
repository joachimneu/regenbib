"""``Store.sort`` / ``Store.dedup`` — the logic behind ``regenbib-scrub``."""

import pytest

from regenbib.store import ArxivEntry, DblpEntry, RawBibtexEntry, Store


def _keyfn(order):
    """Mirror of the key function cli_scrub builds for `sort --by`."""

    def key(e):
        return [
            e.sortkey_source
            if o == "S"
            else e.sortkey_bibtexid
            if o == "B"
            else e.sortkey_contentid
            if o == "C"
            else ""
            for o in order
        ]

    return key


class TestSort:
    def test_by_bibtexid(self, loaded_store):
        loaded_store.sort(_keyfn("B"))
        ids = [e.bibtexid for e in loaded_store.entries]
        assert ids == sorted(ids)

    def test_by_source_groups_entry_types(self, loaded_store):
        loaded_store.sort(_keyfn("S"))
        sources = [e.sortkey_source for e in loaded_store.entries]
        assert sources == sorted(sources)
        # Each type occupies exactly one contiguous run.
        runs = [s for i, s in enumerate(sources) if i == 0 or s != sources[i - 1]]
        assert len(runs) == len(set(sources))

    def test_by_source_then_bibtexid_is_stable_within_group(self, loaded_store):
        loaded_store.sort(_keyfn("SB"))
        seen = [(e.sortkey_source, e.bibtexid) for e in loaded_store.entries]
        assert seen == sorted(seen)

    @pytest.mark.parametrize("order", ["S", "B", "C", "SB", "BC", "SBC"])
    def test_sort_is_a_permutation(self, loaded_store, order):
        before = sorted(e.bibtexid for e in loaded_store.entries)
        loaded_store.sort(_keyfn(order))
        assert sorted(e.bibtexid for e in loaded_store.entries) == before

    @pytest.mark.parametrize("order", ["S", "B", "C", "SBC"])
    def test_sort_is_idempotent(self, loaded_store, order):
        loaded_store.sort(_keyfn(order))
        once = list(loaded_store.entries)
        loaded_store.sort(_keyfn(order))
        assert loaded_store.entries == once


class TestDedup:
    def test_removes_exact_duplicate_pair(self, capsys):
        store = Store([DblpEntry("k", "conf/x/Y99"), DblpEntry("k", "conf/x/Y99")])
        store.dedup()
        assert len(store.entries) == 1
        assert "Duplicate entry: k" in capsys.readouterr().out

    def test_removes_exact_duplicate_triple(self, capsys):
        store = Store([DblpEntry("k", "conf/x/Y99")] * 3)
        store.dedup()
        assert len(store.entries) == 1

    def test_keeps_conflicting_entries_and_warns(self, capsys):
        # Same bibtexid, different content: needs a human, so nothing is dropped.
        store = Store([DblpEntry("k", "conf/x/Y99"), DblpEntry("k", "conf/x/DIFFERENT")])
        store.dedup()
        assert len(store.entries) == 2
        assert "MANUAL CLEANUP REQUIRED" in capsys.readouterr().out

    def test_conflicting_across_types_is_kept(self, capsys):
        store = Store([DblpEntry("k", "p"), ArxivEntry("k", "p", "")])
        store.dedup()
        assert len(store.entries) == 2
        assert "MANUAL CLEANUP REQUIRED" in capsys.readouterr().out

    def test_four_identical_entries_need_manual_cleanup(self, capsys):
        # Only the 2x and 3x cases are auto-resolved; 4x falls through.
        store = Store([DblpEntry("k", "conf/x/Y99")] * 4)
        store.dedup()
        assert len(store.entries) == 4
        assert "MANUAL CLEANUP REQUIRED" in capsys.readouterr().out

    def test_distinct_ids_are_untouched(self, loaded_store):
        before = list(loaded_store.entries)
        loaded_store.dedup()
        assert loaded_store.entries == before

    def test_empty_store(self):
        store = Store([])
        store.dedup()
        assert store.entries == []

    def test_dedup_preserves_first_occurrence_order(self):
        store = Store(
            [
                DblpEntry("a", "conf/x/A"),
                DblpEntry("b", "conf/x/B"),
                DblpEntry("a", "conf/x/A"),
                RawBibtexEntry("c", ["@misc{c}"]),
            ]
        )
        store.dedup()
        assert [e.bibtexid for e in store.entries] == ["a", "b", "c"]


class TestBibtexIds:
    def test_bibtexids_yields_every_id(self, loaded_store):
        assert list(loaded_store.bibtexids) == [e.bibtexid for e in loaded_store.entries]
