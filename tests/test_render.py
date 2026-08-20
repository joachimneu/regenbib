"""Rendering entries to pybtex, and the ``regenbib.cfg.py`` hook mechanism."""

import textwrap

import pytest

from regenbib.cli_render import default_render_entry_hook, load_cfgpy
from regenbib.store import (
    ArxivEntry,
    DblpEntry,
    DoiEntry,
    EprintEntry,
    RawBibtexEntry,
)


class TestRawBibtexEntry:
    def test_renders_without_any_lookup(self, loaded_store):
        entry = next(e for e in loaded_store.entries if e.bibtexid == 'gafni-losa')
        rendered = entry.render_pybtex_entry()
        assert rendered.fields['title'].startswith('Invited Paper')
        assert rendered.fields['year'] == '2023'
        assert [str(p) for p in rendered.persons['author']] == ['Gafni, Eli', 'Losa, Giuliano']

    def test_from_pybtex_entry_round_trips(self):
        original = RawBibtexEntry(
            'k',
            [
                '@article{k,',
                '    author = "Doe, Jane",',
                '    title = "A Title",',
                '    year = "2020"',
                '}',
                '',
            ],
        )
        pybtex_entry = original.render_pybtex_entry()
        rebuilt = RawBibtexEntry.from_pybtex_entry('k', pybtex_entry)
        assert rebuilt.render_pybtex_entry().fields['title'] == 'A Title'

    def test_rejects_multi_entry_payload(self):
        entry = RawBibtexEntry('k', ['@misc{a, title = "A"}', '@misc{b, title = "B"}'])
        with pytest.raises(AssertionError):
            entry.render_pybtex_entry()


class TestDblpEntry:
    def test_uses_the_dblp_lookup(self, stub_lookups):
        rendered = DblpEntry('my-key', 'conf/osdi/CastroL99').render_pybtex_entry()
        assert stub_lookups['dblp'] == ['conf/osdi/CastroL99']
        assert rendered.fields['title'] == 'A Paper About conf/osdi/CastroL99'


class TestArxivEntry:
    def test_unversioned(self, stub_lookups):
        rendered = ArxivEntry('k', '2102.07932', '').render_pybtex_entry()
        assert stub_lookups['arxiv'] == ['2102.07932']
        assert rendered.fields['eprint'] == '2102.07932'
        assert rendered.fields['_howpublished'] == 'arXiv:2102.07932 [cs.DC]'
        assert rendered.fields['_url'] == 'https://arxiv.org/abs/2102.07932'

    def test_versioned_queries_and_records_the_version(self, stub_lookups):
        rendered = ArxivEntry('k', '1807.04938', '3').render_pybtex_entry()
        assert stub_lookups['arxiv'] == ['1807.04938v3']
        assert rendered.fields['eprint'] == '1807.04938v3'
        assert rendered.fields['_howpublished'] == 'arXiv:1807.04938v3 [cs.DC]'
        assert rendered.fields['_url'] == 'https://arxiv.org/abs/1807.04938v3'

    def test_plain_url_is_removed(self, stub_lookups):
        # url is dropped in favor of _url so the cfg hook controls it.
        rendered = ArxivEntry('k', '2102.07932', '').render_pybtex_entry()
        assert 'url' not in rendered.fields

    def test_key_is_replaced_by_bibtexid(self, stub_lookups):
        rendered = ArxivEntry('my-chosen-key', '2102.07932', '').render_pybtex_entry()
        assert rendered.key == 'my-chosen-key'

    def test_missing_primaryclass_omits_the_bracket(self, monkeypatch, stub_lookups):
        from regenbib import store

        monkeypatch.setattr(
            store,
            '_lookup_arxiv_by_arxivid',
            lambda qid: (
                '@misc{a,\n  title = {T},\n  eprint = {2102.07932},\n'
                '  url = {https://arxiv.org/abs/2102.07932}\n}\n'
            ),
        )
        rendered = ArxivEntry('k', '2102.07932', '').render_pybtex_entry()
        assert rendered.fields['_howpublished'] == 'arXiv:2102.07932'

    def test_mismatched_eprint_is_rejected(self, monkeypatch, stub_lookups):
        from regenbib import store

        monkeypatch.setattr(
            store,
            '_lookup_arxiv_by_arxivid',
            lambda qid: (
                '@misc{a,\n  title = {T},\n  eprint = {9999.99999},\n'
                '  url = {https://arxiv.org/abs/9999.99999}\n}\n'
            ),
        )
        with pytest.raises(AssertionError):
            ArxivEntry('k', '2102.07932', '').render_pybtex_entry()

    def test_versioned_eprint_field_from_backend_is_rejected(self, monkeypatch, stub_lookups):
        from regenbib import store

        monkeypatch.setattr(
            store,
            '_lookup_arxiv_by_arxivid',
            lambda qid: (
                '@misc{a,\n  title = {T},\n  eprint = {2102.07932v2},\n'
                '  url = {https://arxiv.org/abs/2102.07932}\n}\n'
            ),
        )
        with pytest.raises(AssertionError):
            ArxivEntry('k', '2102.07932', '').render_pybtex_entry()


class TestEprintEntry:
    def test_uses_the_eprint_lookup(self, stub_lookups):
        rendered = EprintEntry('k', '2023/397').render_pybtex_entry()
        assert stub_lookups['eprint'] == ['2023/397']
        assert rendered.fields['year'] == '2023'
        assert rendered.fields['url'] == 'https://eprint.iacr.org/2023/397'


class TestDoiEntry:
    def test_uses_the_doi_lookup(self, stub_lookups):
        rendered = DoiEntry('k', '10.1145/3719027.3765032').render_pybtex_entry()
        assert stub_lookups['doi'] == ['10.1145/3719027.3765032']
        assert rendered.fields['title'].startswith('An Article With DOI')

    def test_strict_mode_is_restored_after_rendering(self, stub_lookups):
        # The DOI path toggles pybtex strict mode; it must not leak.
        import pybtex.errors

        DoiEntry('k', '10.1/2').render_pybtex_entry()
        assert pybtex.errors.strict is True


class TestDefaultRenderHook:
    def _entry(self, bibtex):
        import bibtex_dblp.database

        data = bibtex_dblp.database.parse_bibtex(textwrap.dedent(bibtex))
        return data.entries[list(data.entries.keys())[0]]

    def test_lncs_series_is_abbreviated(self):
        pybtex_entry = self._entry("""
            @inproceedings{k,
              title = {T},
              series = {Lecture Notes in Computer Science}
            }
        """)
        _, out = default_render_entry_hook(object(), pybtex_entry)
        assert out.fields['series'] == 'LNCS'

    def test_other_series_untouched(self):
        pybtex_entry = self._entry('@inproceedings{k, title = {T}, series = {LIPIcs}}')
        _, out = default_render_entry_hook(object(), pybtex_entry)
        assert out.fields['series'] == 'LIPIcs'

    def test_eprint_note_is_dropped(self):
        pybtex_entry = self._entry("""
            @misc{k,
              title = {T},
              note = {some note},
              url = {https://eprint.iacr.org/2023/397}
            }
        """)
        _, out = default_render_entry_hook(object(), pybtex_entry)
        assert 'note' not in out.fields

    def test_non_eprint_note_is_kept(self):
        pybtex_entry = self._entry("""
            @misc{k,
              title = {T},
              note = {some note},
              url = {https://example.com/}
            }
        """)
        _, out = default_render_entry_hook(object(), pybtex_entry)
        assert out.fields['note'] == 'some note'


class TestLoadCfgpy:
    def test_missing_file_yields_defaults(self, tmp_path):
        cfg = load_cfgpy(str(tmp_path / 'absent.cfg.py'))
        assert cfg['render_entry_hook'] is not None
        assert set(cfg) == {'render_entry_hook'}

    def test_defaults_are_not_shared_between_calls(self, tmp_path):
        first = load_cfgpy(str(tmp_path / 'absent.cfg.py'))
        first['render_entry_hook'] = 'clobbered'
        second = load_cfgpy(str(tmp_path / 'absent.cfg.py'))
        assert second['render_entry_hook'] != 'clobbered'

    def test_custom_hook_is_picked_up(self, tmp_path):
        cfg_file = tmp_path / 'regenbib.cfg.py'
        cfg_file.write_text(
            'def render_entry_hook(entry, entry_pybtex):\n'
            '    entry_pybtex.fields["title"] = "REWRITTEN"\n'
            '    return (entry, entry_pybtex)\n'
        )
        cfg = load_cfgpy(str(cfg_file))
        entry = RawBibtexEntry('k', ['@misc{k, title = "Original"}'])
        _, out = cfg['render_entry_hook'](entry, entry.render_pybtex_entry())
        assert out.fields['title'] == 'REWRITTEN'

    def test_partial_cfg_falls_back_for_absent_keys(self, tmp_path):
        cfg_file = tmp_path / 'regenbib.cfg.py'
        cfg_file.write_text('SOMETHING_ELSE = 1\n')
        cfg = load_cfgpy(str(cfg_file))
        assert cfg['render_entry_hook'] is default_render_entry_hook

    def test_no_bytecode_is_written_for_the_config(self, tmp_path):
        cfg_file = tmp_path / 'regenbib.cfg.py'
        cfg_file.write_text('render_entry_hook = None\n')
        load_cfgpy(str(cfg_file))
        assert not list(tmp_path.glob('__pycache__/*'))
