"""End-to-end tests of the regenbib-query entry point: one-shot, non-interactive
queries driven via sys.argv, with the network stubbed out."""

import shutil
import sys

import bibtex_dblp.dblp_api
import bibtex_dblp.dblp_data
import pytest
import requests
import yaml

from regenbib import cli_query
from regenbib.store import Store


@pytest.fixture
def workdir(tmp_path, references_yaml):
    shutil.copy(references_yaml, tmp_path / "references.yaml")
    return tmp_path


def _argv(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["prog", *args])


SEARCH_JSON = {
    "result": {
        "query": "streamlet",
        "status": {"@code": "200", "text": "OK"},
        "hits": {
            "@total": "2",
            "hit": [
                {
                    "@score": "3",
                    "info": {
                        "title": "Streamlet: Textbook Streamlined Blockchains.",
                        "venue": "AFT",
                        "pages": "1-11",
                        "year": "2020",
                        "type": "Conference and Workshop Papers",
                        "key": "conf/aft/ChanS20",
                        "doi": "10.1145/3419614.3423256",
                        "ee": "https://doi.org/10.1145/3419614.3423256",
                        "url": "https://dblp.org/rec/conf/aft/ChanS20",
                        "authors": {
                            "author": [
                                {"@pid": "130/522", "text": "Benjamin Y. Chan"},
                                {"@pid": "13/3158", "text": "Elaine Shi"},
                            ]
                        },
                    },
                },
                {
                    "@score": "2",
                    "info": {
                        "title": "Streamlet: Textbook Streamlined Blockchains.",
                        "venue": "IACR Cryptol. ePrint Arch.",
                        "year": "2020",
                        "key": "journals/iacr/ChanS20",
                        "ee": "https://eprint.iacr.org/2020/088",
                        "url": "https://dblp.org/rec/journals/iacr/ChanS20",
                        "authors": {"author": {"@pid": "130/522", "text": "Benjamin Y. Chan"}},
                    },
                },
            ],
        },
    }
}

EMPTY_SEARCH_JSON = {
    "result": {
        "query": "nothing",
        "status": {"@code": "200", "text": "OK"},
        "hits": {"@total": "0"},
    }
}


class TestSearchDblp:
    def test_lists_matches_with_dblpids(self, monkeypatch, capsys):
        recorded = {}

        def fake_search(session, query, max_search_results):
            recorded["query"] = query
            recorded["max_search_results"] = max_search_results
            return bibtex_dblp.dblp_data.DblpSearchResults(SEARCH_JSON)

        monkeypatch.setattr(bibtex_dblp.dblp_api, "search_publication", fake_search)
        _argv(monkeypatch, "search-dblp", "streamlet textbook", "--max-results", "7")
        cli_query.run()

        out = capsys.readouterr().out
        assert recorded == {"query": "streamlet textbook", "max_search_results": 7}
        assert "2 matches (showing 2):" in out
        assert "(1) dblpid: conf/aft/ChanS20" in out
        assert "(2) dblpid: journals/iacr/ChanS20" in out
        assert "authors: Benjamin Y. Chan, Elaine Shi" in out
        assert "venue: AFT" in out
        assert "pages: 1-11" in out
        assert "ee: https://eprint.iacr.org/2020/088" in out

    def test_no_matches(self, monkeypatch, capsys):
        monkeypatch.setattr(
            bibtex_dblp.dblp_api,
            "search_publication",
            lambda session, query, max_search_results: bibtex_dblp.dblp_data.DblpSearchResults(
                EMPTY_SEARCH_JSON
            ),
        )
        _argv(monkeypatch, "search-dblp", "no such paper")
        cli_query.run()
        assert capsys.readouterr().out == "0 matches.\n"

    def test_unstubbed_search_chain(self, monkeypatch, capsys):
        """Drive the real bibtex_dblp search_publication/DblpSession code with HTTP
        faked at the transport, so an upstream signature change fails here."""

        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return SEARCH_JSON

        monkeypatch.setattr(requests.Session, "request", lambda self, *a, **kw: FakeResponse())
        _argv(monkeypatch, "search-dblp", "streamlet textbook")
        cli_query.run()
        assert "(1) dblpid: conf/aft/ChanS20" in capsys.readouterr().out


class TestGetPreviews:
    def _yaml_snippet(self, out):
        body = out.split("YAML entry (append under `entries:` in the .yaml file):\n", 1)[1]
        return body.split("\nBibTeX preview", 1)[0]

    def test_get_dblp(self, monkeypatch, capsys, stub_lookups):
        _argv(monkeypatch, "get-dblp", "conf/osdi/CastroL99", "--bibtexid", "pbft")
        cli_query.run()

        out = capsys.readouterr().out
        assert stub_lookups["dblp"] == ["conf/osdi/CastroL99"]
        assert yaml.safe_load(self._yaml_snippet(out)) == [
            {"bibtexid": "pbft", "dblpid": "conf/osdi/CastroL99"}
        ]
        assert "@inproceedings{pbft" in out

    def test_get_arxiv_normalizes_versioned_id(self, monkeypatch, capsys, stub_lookups):
        _argv(monkeypatch, "get-arxiv", "2102.07932v3")
        cli_query.run()

        out = capsys.readouterr().out
        assert stub_lookups["arxiv"] == ["2102.07932v3"]
        assert yaml.safe_load(self._yaml_snippet(out)) == [
            {"arxivid": "2102.07932", "bibtexid": "FIXME", "version": "3"}
        ]
        assert "@misc{FIXME" in out

    def test_get_arxiv_rejects_prefixed_id(self, monkeypatch, stub_lookups):
        _argv(monkeypatch, "get-arxiv", "arXiv:2102.07932")
        with pytest.raises(AssertionError):
            cli_query.run()

    def test_get_eprint(self, monkeypatch, capsys, stub_lookups):
        _argv(monkeypatch, "get-eprint", "2023/397")
        cli_query.run()

        out = capsys.readouterr().out
        assert stub_lookups["eprint"] == ["2023/397"]
        assert yaml.safe_load(self._yaml_snippet(out)) == [
            {"bibtexid": "FIXME", "eprintid": "2023/397"}
        ]
        assert "@misc{FIXME" in out

    def test_get_doi_strips_url_prefix(self, monkeypatch, capsys, stub_lookups):
        _argv(monkeypatch, "get-doi", "https://doi.org/10.1145/3719027.3765032")
        cli_query.run()

        out = capsys.readouterr().out
        assert stub_lookups["doi"] == ["10.1145/3719027.3765032"]
        assert yaml.safe_load(self._yaml_snippet(out)) == [
            {"bibtexid": "FIXME", "doi": "10.1145/3719027.3765032"}
        ]

    def test_get_raw_wraps_the_old_bib_entry(self, tmp_path, monkeypatch, capsys):
        (tmp_path / "old.bib").write_text(
            "@article{known,\n  author = {Doe, Jane},\n  title = {T},\n  year = {2020}\n}\n"
        )
        _argv(monkeypatch, "get-raw", "known", "--bib", str(tmp_path / "old.bib"))
        cli_query.run()

        out = capsys.readouterr().out
        entries = yaml.safe_load(self._yaml_snippet(out))
        assert entries[0]["bibtexid"] == "known"
        assert any('author = "Doe, Jane"' in line for line in entries[0]["rawbibtex"])
        assert "@article{known" in out

        store = Store.Schema().load({"entries": entries})
        assert store.entries[0].render_pybtex_entry().fields["title"] == "T"

    def test_get_raw_honors_ids_alias_and_bibtexid(self, tmp_path, monkeypatch, capsys):
        (tmp_path / "old.bib").write_text("@misc{real,\n  title = {U},\n  ids = {aliased}\n}\n")
        _argv(
            monkeypatch,
            "get-raw",
            "aliased",
            "--bib",
            str(tmp_path / "old.bib"),
            "--bibtexid",
            "newkey",
        )
        cli_query.run()

        out = capsys.readouterr().out
        entries = yaml.safe_load(self._yaml_snippet(out))
        assert entries[0]["bibtexid"] == "newkey"
        assert not any("ids" in line for line in entries[0]["rawbibtex"])
        assert "@misc{newkey" in out

    def test_get_raw_rejects_unknown_key(self, tmp_path, monkeypatch):
        (tmp_path / "old.bib").write_text("")
        _argv(monkeypatch, "get-raw", "nope", "--bib", str(tmp_path / "old.bib"))
        with pytest.raises(AssertionError):
            cli_query.run()

    def test_yaml_snippet_loads_back_into_the_store(self, monkeypatch, capsys, stub_lookups):
        # The printed snippet must be appendable to a .yaml file verbatim.
        _argv(monkeypatch, "get-arxiv", "2102.07932v3", "--bibtexid", "k")
        cli_query.run()

        entries = yaml.safe_load(self._yaml_snippet(capsys.readouterr().out))
        store = Store.Schema().load({"entries": entries})
        assert store.entries[0].bibtexid == "k"
        assert store.entries[0].arxivid == "2102.07932"
        assert store.entries[0].version == "3"


class TestSharedOptions:
    def test_lookup_flags_may_follow_the_subcommand(self, monkeypatch, capsys, stub_lookups):
        from regenbib import store

        _argv(monkeypatch, "get-eprint", "2023/397", "--user-agent-eprint", "TestAgent")
        cli_query.run()
        assert store._lookup_config.user_agent_eprint == "TestAgent"


class TestMissing:
    def test_lists_missing_keys_in_citation_order(self, workdir, aux_file, monkeypatch, capsys):
        Store([]).dump(str(workdir / "empty.yaml"))
        _argv(monkeypatch, "missing", "--aux", aux_file, "--yaml", str(workdir / "empty.yaml"))
        cli_query.run()

        assert capsys.readouterr().out.splitlines() == [
            "pbft",
            "dls",
            "gafni-losa",
            "tendermint",
            "fast-authenticated-bft",
            "hotstuff2",
            "some-doi",
        ]

    def test_no_output_when_nothing_is_missing(self, workdir, aux_file, monkeypatch, capsys):
        _argv(monkeypatch, "missing", "--aux", aux_file, "--yaml", str(workdir / "references.yaml"))
        cli_query.run()
        assert capsys.readouterr().out == ""

    def test_with_bib_shows_old_entries_and_aliases(self, workdir, monkeypatch, capsys):
        aux = workdir / "some.aux"
        aux.write_text("\\citation{known}\n\\citation{aliased}\n\\citation{absent}\n")
        (workdir / "old.bib").write_text(
            "@article{known,\n  author = {Doe, Jane},\n  title = {T},\n  year = {2020}\n}\n"
            "@misc{real,\n  title = {U},\n  ids = {aliased, other}\n}\n"
        )
        Store([]).dump(str(workdir / "empty.yaml"))
        _argv(
            monkeypatch,
            "missing",
            "--aux",
            str(aux),
            "--yaml",
            str(workdir / "empty.yaml"),
            "--bib",
            str(workdir / "old.bib"),
        )
        cli_query.run()

        out = capsys.readouterr().out
        assert "== known ==" in out
        assert "@article{known" in out
        assert "== aliased ==" in out
        assert "@misc{aliased" in out
        assert "ids =" not in out
        assert "== absent ==" in out
        assert "(no entry in the .bib file)" in out
