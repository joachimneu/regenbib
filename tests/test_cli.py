"""End-to-end tests of the three console entry points, driven via sys.argv in a
tmp_path sandbox with the network stubbed out."""

import shutil
import sys

import pytest

from regenbib import cli_import, cli_render, cli_scrub
from regenbib.store import ArxivEntry, DblpEntry, Store


@pytest.fixture
def workdir(tmp_path, references_yaml):
    shutil.copy(references_yaml, tmp_path / 'references.yaml')
    (tmp_path / 'references.bib').write_text('')
    return tmp_path


def _argv(monkeypatch, *args):
    monkeypatch.setattr(sys, 'argv', ['prog', *args])


class TestRender:
    def test_writes_a_bib_for_every_entry(self, workdir, monkeypatch, stub_lookups):
        out = workdir / 'out.bib'
        _argv(
            monkeypatch,
            '--yaml', str(workdir / 'references.yaml'),
            '--bib', str(out),
            '--cfgpy', str(workdir / 'absent.cfg.py'),
        )
        cli_render.run()

        text = out.read_text()
        for bibtexid in ('pbft', 'dls', 'tendermint', 'gafni-losa', 'hotstuff2', 'some-doi'):
            assert '{%s,' % bibtexid in text

    def test_every_backend_is_consulted_exactly_once_per_entry(
        self, workdir, monkeypatch, stub_lookups
    ):
        _argv(
            monkeypatch,
            '--yaml', str(workdir / 'references.yaml'),
            '--bib', str(workdir / 'out.bib'),
            '--cfgpy', str(workdir / 'absent.cfg.py'),
        )
        cli_render.run()

        assert sorted(stub_lookups['dblp']) == ['conf/osdi/CastroL99', 'journals/jacm/DworkLS88']
        assert sorted(stub_lookups['arxiv']) == ['1807.04938v3', '2102.07932']
        assert stub_lookups['eprint'] == ['2023/397']
        assert stub_lookups['doi'] == ['10.1145/3719027.3765032']

    def test_cfgpy_hook_is_applied(self, workdir, monkeypatch, stub_lookups):
        (workdir / 'regenbib.cfg.py').write_text(
            'def render_entry_hook(entry, entry_pybtex):\n'
            '    entry_pybtex.fields["title"] = "HOOKED"\n'
            '    return (entry, entry_pybtex)\n'
        )
        out = workdir / 'out.bib'
        _argv(
            monkeypatch,
            '--yaml', str(workdir / 'references.yaml'),
            '--bib', str(out),
            '--cfgpy', str(workdir / 'regenbib.cfg.py'),
        )
        cli_render.run()
        assert out.read_text().count('HOOKED') == 8

    def test_biblatex_mode(self, workdir, monkeypatch, stub_lookups):
        out = workdir / 'out.bib'
        _argv(
            monkeypatch,
            '--yaml', str(workdir / 'references.yaml'),
            '--bib', str(out),
            '--cfgpy', str(workdir / 'absent.cfg.py'),
            '--biblatex',
        )
        cli_render.run()
        text = out.read_text()
        assert 'ids = {' in text
        assert '@inproceedings{reference_' in text or '@misc{reference_' in text

    def test_biblatex_group_collapses_duplicate_content(
        self, workdir, monkeypatch, stub_lookups
    ):
        Store(
            [DblpEntry('key-a', 'conf/x/Y99'), DblpEntry('key-b', 'conf/x/Y99')]
        ).dump(str(workdir / 'dup.yaml'))
        out = workdir / 'out.bib'
        _argv(
            monkeypatch,
            '--yaml', str(workdir / 'dup.yaml'),
            '--bib', str(out),
            '--cfgpy', str(workdir / 'absent.cfg.py'),
            '--biblatex', '--biblatex-group',
        )
        cli_render.run()
        text = out.read_text()
        assert text.count('@inproceedings{') == 1
        assert 'key-a, key-b' in text

    def test_biblatex_group_requires_biblatex(self, workdir, monkeypatch, stub_lookups):
        _argv(
            monkeypatch,
            '--yaml', str(workdir / 'references.yaml'),
            '--bib', str(workdir / 'out.bib'),
            '--biblatex-group',
        )
        with pytest.raises(AssertionError):
            cli_render.run()

    @pytest.mark.parametrize('flag', ['--delay-dblp', '--delay-arxiv', '--delay-eprint', '--delay-doi'])
    def test_negative_delays_are_rejected(self, workdir, monkeypatch, stub_lookups, flag):
        _argv(
            monkeypatch,
            '--yaml', str(workdir / 'references.yaml'),
            '--bib', str(workdir / 'out.bib'),
            flag, '-1',
        )
        with pytest.raises(AssertionError):
            cli_render.run()

    def test_empty_yaml_produces_empty_bib(self, workdir, monkeypatch, stub_lookups):
        Store([]).dump(str(workdir / 'empty.yaml'))
        out = workdir / 'out.bib'
        _argv(
            monkeypatch,
            '--yaml', str(workdir / 'empty.yaml'),
            '--bib', str(out),
            '--cfgpy', str(workdir / 'absent.cfg.py'),
        )
        cli_render.run()
        assert out.read_text().strip() == ''


class TestScrub:
    def test_sort_rewrites_the_yaml(self, workdir, monkeypatch):
        target = workdir / 'references.yaml'
        _argv(monkeypatch, '--yaml', str(target), 'sort', '--by', 'B')
        cli_scrub.run()
        ids = [e.bibtexid for e in Store.load(str(target)).entries]
        assert ids == sorted(ids)

    def test_sort_rejects_unknown_order(self, workdir, monkeypatch):
        _argv(monkeypatch, '--yaml', str(workdir / 'references.yaml'), 'sort', '--by', 'X')
        with pytest.raises(AssertionError):
            cli_scrub.run()

    def test_dedup_rewrites_the_yaml(self, workdir, monkeypatch):
        target = workdir / 'dup.yaml'
        Store([DblpEntry('k', 'conf/x/Y99'), DblpEntry('k', 'conf/x/Y99')]).dump(str(target))
        _argv(monkeypatch, '--yaml', str(target), 'dedup')
        cli_scrub.run()
        assert len(Store.load(str(target)).entries) == 1

    def test_freeze_arxiv_sets_versions(self, workdir, monkeypatch, stub_lookups):
        target = workdir / 'references.yaml'
        _argv(monkeypatch, '--yaml', str(target), 'freeze-arxiv')
        cli_scrub.run()

        by_id = {e.bibtexid: e for e in Store.load(str(target)).entries}
        assert by_id['fast-authenticated-bft'].version == '7'  # was empty, now frozen
        assert by_id['tendermint'].version == '3'  # already frozen, untouched
        assert stub_lookups['arxiv_version'] == ['2102.07932']

    def test_freeze_arxiv_targeted(self, workdir, monkeypatch, stub_lookups):
        target = workdir / 'references.yaml'
        _argv(monkeypatch, '--yaml', str(target), 'freeze-arxiv', 'fast-authenticated-bft')
        cli_scrub.run()
        by_id = {e.bibtexid: e for e in Store.load(str(target)).entries}
        assert by_id['fast-authenticated-bft'].version == '7'

    def test_freeze_arxiv_rejects_non_arxiv_entry(self, workdir, monkeypatch, stub_lookups):
        _argv(monkeypatch, '--yaml', str(workdir / 'references.yaml'), 'freeze-arxiv', 'pbft')
        with pytest.raises(AssertionError):
            cli_scrub.run()

    def test_freeze_arxiv_rejects_unknown_entry(self, workdir, monkeypatch, stub_lookups):
        _argv(monkeypatch, '--yaml', str(workdir / 'references.yaml'), 'freeze-arxiv', 'nope')
        with pytest.raises(AssertionError):
            cli_scrub.run()

    def test_unfreeze_arxiv_clears_versions(self, workdir, monkeypatch, stub_lookups):
        target = workdir / 'references.yaml'
        _argv(monkeypatch, '--yaml', str(target), 'unfreeze-arxiv')
        cli_scrub.run()
        by_id = {e.bibtexid: e for e in Store.load(str(target)).entries}
        assert by_id['tendermint'].version == ''
        assert stub_lookups['arxiv_version'] == []

    def test_unfreeze_is_a_noop_when_nothing_is_frozen(self, workdir, monkeypatch, stub_lookups):
        target = workdir / 'plain.yaml'
        Store([ArxivEntry('k', '1234.5678', '')]).dump(str(target))
        before = target.read_text()
        _argv(monkeypatch, '--yaml', str(target), 'unfreeze-arxiv')
        cli_scrub.run()
        assert target.read_text() == before

    def test_freeze_then_unfreeze_restores_the_file(self, workdir, monkeypatch, stub_lookups):
        target = workdir / 'plain.yaml'
        Store([ArxivEntry('k', '1234.5678', '')]).dump(str(target))
        before = target.read_text()

        _argv(monkeypatch, '--yaml', str(target), 'freeze-arxiv')
        cli_scrub.run()
        assert target.read_text() != before

        _argv(monkeypatch, '--yaml', str(target), 'unfreeze-arxiv')
        cli_scrub.run()
        assert target.read_text() == before


class TestImportAuxParsing:
    def _parsed_ids(self, capsys):
        return [
            ln.split('Importing entry:', 1)[1].strip()
            for ln in capsys.readouterr().out.splitlines()
            if 'Importing entry:' in ln
        ]

    def test_extracts_both_citation_forms_in_order(
        self, workdir, aux_file, monkeypatch, capsys
    ):
        # Empty store, so every parsed id is reported before any interaction.
        Store([]).dump(str(workdir / 'empty.yaml'))
        monkeypatch.setattr(cli_import, 'attempt_import', lambda methods: None)
        _argv(
            monkeypatch,
            '--aux', aux_file,
            '--bib', str(workdir / 'references.bib'),
            '--yaml', str(workdir / 'empty.yaml'),
        )
        cli_import.run()

        assert self._parsed_ids(capsys) == [
            'pbft',
            'dls',
            'gafni-losa',
            'tendermint',
            'fast-authenticated-bft',
            'hotstuff2',
            'some-doi',
        ]

    def test_entries_already_present_are_skipped(
        self, workdir, aux_file, monkeypatch, capsys
    ):
        monkeypatch.setattr(cli_import, 'attempt_import', lambda methods: None)
        _argv(
            monkeypatch,
            '--aux', aux_file,
            '--bib', str(workdir / 'references.bib'),
            '--yaml', str(workdir / 'references.yaml'),
        )
        cli_import.run()
        assert self._parsed_ids(capsys) == []

    def test_yaml_untouched_when_nothing_to_import(
        self, workdir, aux_file, monkeypatch
    ):
        target = workdir / 'references.yaml'
        before = target.read_text()
        monkeypatch.setattr(cli_import, 'attempt_import', lambda methods: None)
        _argv(
            monkeypatch,
            '--aux', aux_file,
            '--bib', str(workdir / 'references.bib'),
            '--yaml', str(target),
        )
        cli_import.run()
        assert target.read_text() == before

    def test_imported_entry_is_appended_and_persisted(
        self, workdir, aux_file, monkeypatch
    ):
        target = workdir / 'empty.yaml'
        Store([]).dump(str(target))
        monkeypatch.setattr(
            cli_import,
            'attempt_import',
            lambda methods: DblpEntry('injected', 'conf/x/Y99'),
        )
        _argv(
            monkeypatch,
            '--aux', aux_file,
            '--bib', str(workdir / 'references.bib'),
            '--yaml', str(target),
        )
        cli_import.run()
        assert [e.bibtexid for e in Store.load(str(target)).entries] == ['injected'] * 7

    def test_import_methods_are_bound_to_the_right_entry(self, workdir, monkeypatch):
        """Each offered method is built with functools.partial, so it must close
        over its own bibtexid rather than the loop variable."""
        aux = workdir / 'two.aux'
        aux.write_text('\\citation{alpha}\n\\citation{beta}\n')
        Store([]).dump(str(workdir / 'empty.yaml'))

        recorded = []

        def fake_method_without_old(bibtexid):
            recorded.append(('without', bibtexid))
            return None

        monkeypatch.setattr(
            cli_import, 'import_arxiv_manualid', fake_method_without_old, raising=True
        )

        seen_names = []

        def fake_attempt_import(methods):
            seen_names.append([name for (name, _) in methods])
            # Invoke only the stubbed method; the others block on stdin.
            for name, thunk in methods:
                if name == 'arxiv-manual-id':
                    thunk()
            return None

        monkeypatch.setattr(cli_import, 'attempt_import', fake_attempt_import)
        _argv(
            monkeypatch,
            '--aux', str(aux),
            '--bib', str(workdir / 'references.bib'),
            '--yaml', str(workdir / 'empty.yaml'),
        )
        cli_import.run()

        # The arXiv method was invoked once per id, bound to that id.
        assert ('without', 'alpha') in recorded
        assert ('without', 'beta') in recorded
        # No old entry exists in the empty .bib, so only the four
        # without-old-entry methods are offered.
        assert seen_names == [
            ['dblp-free-search', 'arxiv-manual-id', 'eprint-manual-id', 'doi-manual-id'],
        ] * 2

    def test_old_entry_adds_the_with_oldentry_methods(self, workdir, monkeypatch):
        aux = workdir / 'one.aux'
        aux.write_text('\\citation{known}\n')
        Store([]).dump(str(workdir / 'empty.yaml'))
        (workdir / 'withentry.bib').write_text(
            '@article{known,\n  author = {Doe, Jane},\n  title = {T},\n  year = {2020}\n}\n'
        )

        seen_names = []
        monkeypatch.setattr(
            cli_import,
            'attempt_import',
            lambda methods: seen_names.append([name for (name, _) in methods]),
        )
        _argv(
            monkeypatch,
            '--aux', str(aux),
            '--bib', str(workdir / 'withentry.bib'),
            '--yaml', str(workdir / 'empty.yaml'),
        )
        cli_import.run()

        assert seen_names == [
            [
                'dblp-free-search', 'arxiv-manual-id', 'eprint-manual-id', 'doi-manual-id',
                'current-entry', 'dblp-search-title', 'dblp-search-authorstitle',
            ]
        ]

    def test_multiline_and_padded_citation_lists(self, workdir, tmp_path, monkeypatch, capsys):
        aux = tmp_path / 'padded.aux'
        aux.write_text('\\citation{ alpha , beta }\n\\citation{alpha}\n')
        Store([]).dump(str(workdir / 'empty.yaml'))
        monkeypatch.setattr(cli_import, 'attempt_import', lambda methods: None)
        _argv(
            monkeypatch,
            '--aux', str(aux),
            '--bib', str(workdir / 'references.bib'),
            '--yaml', str(workdir / 'empty.yaml'),
        )
        cli_import.run()
        assert self._parsed_ids(capsys) == ['alpha', 'beta']
