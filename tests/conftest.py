"""Shared fixtures: no network access, no shared state with the developer's machine."""

import os
import shutil
import tempfile

# store.py builds its diskcache.Cache under Path.home() at import time, so HOME
# must be redirected before regenbib is imported below.
_TMP_HOME = tempfile.mkdtemp(prefix="regenbib-test-home-")
os.environ["HOME"] = _TMP_HOME
os.environ["USERPROFILE"] = _TMP_HOME

import pytest  # noqa: E402
import requests  # noqa: E402

from regenbib import cli_scrub, store  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TMP_HOME, ignore_errors=True)


class NetworkAccessAttempted(RuntimeError):
    pass


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fail loudly on any real network call; blocks the transports, not the lookups."""

    def _blocked(*args, **kwargs):
        raise NetworkAccessAttempted(
            "test attempted real network access; stub the relevant "
            "regenbib.store._lookup_* function instead"
        )

    monkeypatch.setattr(requests, "get", _blocked)
    monkeypatch.setattr(requests, "post", _blocked)
    monkeypatch.setattr(requests.Session, "request", _blocked)
    monkeypatch.setattr(store, "Sickle", _blocked)


@pytest.fixture(autouse=True)
def clean_lookup_config():
    """Reset the module-global lookup config between tests."""
    original = store._lookup_config
    store.set_lookup_config(store.LookupConfig())
    yield
    store.set_lookup_config(original)


@pytest.fixture
def data_dir():
    return DATA_DIR


@pytest.fixture
def references_yaml():
    # Fixture bibliography covering all five entry types.
    return os.path.join(DATA_DIR, "references.yaml")


@pytest.fixture
def aux_file():
    return os.path.join(DATA_DIR, "main.aux")


@pytest.fixture
def loaded_store(references_yaml):
    return store.Store.load(references_yaml)


@pytest.fixture
def stub_lookups(monkeypatch):
    """Deterministic stand-ins for every remote lookup; returns the recorded calls."""
    calls = {"dblp": [], "arxiv": [], "arxiv_version": [], "eprint": [], "doi": []}

    def fake_dblp(dblpid):
        calls["dblp"].append(dblpid)
        return (
            "@inproceedings{DBLP:%s,\n"
            "  author    = {Ada Lovelace},\n"
            "  title     = {A Paper About %s},\n"
            "  booktitle = {A Venue},\n"
            "  year      = {1999}\n"
            "}\n" % (dblpid, dblpid)
        )

    def fake_arxiv(qid):
        calls["arxiv"].append(qid)
        base = qid.split("v")[0]
        return (
            "@misc{arxiv-%s,\n"
            "  author       = {Grace Hopper},\n"
            "  title        = {A Preprint About %s},\n"
            "  year         = {2021},\n"
            "  eprint       = {%s},\n"
            "  primaryclass = {cs.DC},\n"
            "  url          = {https://arxiv.org/abs/%s}\n"
            "}\n" % (qid, qid, base, base)
        )

    def fake_arxiv_version(arxivid):
        calls["arxiv_version"].append(arxivid)
        return "7"

    def fake_eprint(eprintid):
        calls["eprint"].append(eprintid)
        year = eprintid.split("/")[0]
        return (
            "@misc{cryptoeprint:%s,\n"
            "  author = {Alan Turing},\n"
            "  title = {An ePrint About %s},\n"
            "  howpublished = {Cryptology {ePrint} Archive, Paper %s},\n"
            "  year = {%s},\n"
            "  url = {https://eprint.iacr.org/%s}\n"
            "}\n" % (eprintid, eprintid, eprintid, year, eprintid)
        )

    def fake_doi(doi):
        calls["doi"].append(doi)
        return (
            "@article{doi-entry,\n"
            "  author = {Barbara Liskov},\n"
            "  title = {An Article With DOI %s},\n"
            "  year = {2025}\n"
            "}\n" % doi
        )

    monkeypatch.setattr(store, "_lookup_dblp_by_dblpid", fake_dblp)
    monkeypatch.setattr(store, "_lookup_arxiv_by_arxivid", fake_arxiv)
    monkeypatch.setattr(store, "_lookup_arxiv_version_by_arxivid", fake_arxiv_version)
    monkeypatch.setattr(store, "_lookup_eprint_by_eprintid", fake_eprint)
    monkeypatch.setattr(store, "_lookup_doi_by_doi", fake_doi)

    # cli_scrub binds _lookup_arxiv_version_by_arxivid via from-import, so it
    # holds its own reference and must be patched separately.
    monkeypatch.setattr(cli_scrub, "_lookup_arxiv_version_by_arxivid", fake_arxiv_version)

    return calls
