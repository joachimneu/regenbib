import yaml
from typing import Union
from marshmallow_dataclass import dataclass
import pybtex.database
import bibtex_dblp.dblp_api
import bibtex_dblp.database
import arxiv
import requests
from bs4 import BeautifulSoup
import hashlib


@dataclass
class RawBibtexEntry:
    bibtexid: str
    rawbibtex: list[str]

    @classmethod
    def from_pybtex_entry(cls, bibtexid, pybtexentry: pybtex.database.Entry):
        slf = cls(bibtexid, "")
        slf.rawbibtex = pybtexentry.to_string("bibtex").split("\n")
        return slf

    def render_pybtex_entry(self):
        data = bibtex_dblp.database.parse_bibtex("\n".join(self.rawbibtex))
        assert len(data.entries) == 1
        key = list(data.entries.keys())[0]
        return data.entries[key]

    @property
    def sortkey_source(self):
        return self.__class__.__name__

    @property
    def sortkey_bibtexid(self):
        return self.bibtexid

    @property
    def sortkey_contentid(self):
        h = hashlib.sha256()
        h.update(repr(self.rawbibtex).encode())
        return (self.sortkey_source, h.hexdigest())


@dataclass
class DblpEntry:
    bibtexid: str
    dblpid: str

    def render_pybtex_entry(self):
        result_dblp = bibtex_dblp.dblp_api.get_bibtex(
            self.dblpid, bib_format=bibtex_dblp.dblp_api.BibFormat.condensed)
        data = bibtex_dblp.database.parse_bibtex(result_dblp)
        assert len(data.entries) == 1
        key = list(data.entries.keys())[0]
        return data.entries[key]

    @property
    def sortkey_source(self):
        return self.__class__.__name__

    @property
    def sortkey_bibtexid(self):
        return self.bibtexid

    @property
    def sortkey_contentid(self):
        return (self.sortkey_source, self.dblpid)


@dataclass
class ArxivEntry:
    bibtexid: str
    arxivid: str
    version: str

    @classmethod
    def from_manual(cls, bibtexid, manual: str):
        slf = cls(bibtexid, "", "")
        manual = manual.strip().lower()
        assert not 'arxiv' in manual
        (arxivid, version) = manual.split(
            'v', 1) if 'v' in manual else (manual, '')
        assert arxivid
        slf.arxivid = arxivid
        slf.version = version
        return slf

    def render_pybtex_entry(self):
        qid = self.arxivid + (('v' + self.version) if self.version else '')
        search = arxiv.Search(id_list=[qid])
        res = list(search.results())
        assert len(res) == 1
        entry = res[0]

        bibtex_string = """
            @misc{%s,
                author        = {%s},
                title         = {%s},
                _howpublished  = {arXiv:%s [%s]},
                _url           = {%s},
                year          = {%d},
                archivePrefix = {arXiv},
                eprint        = {%s},
                primaryClass  = {%s},
            }
        """ % (
            self.bibtexid,
            ' and '.join([a.name for a in entry.authors]),
            entry.title,
            entry.get_short_id(),
            entry.primary_category,
            entry.entry_id,
            entry.published.year,
            entry.get_short_id(),
            entry.primary_category,
        )

        data = bibtex_dblp.database.parse_bibtex(bibtex_string)
        assert len(data.entries) == 1
        key = list(data.entries.keys())[0]
        return data.entries[key]

    @property
    def sortkey_source(self):
        return self.__class__.__name__

    @property
    def sortkey_bibtexid(self):
        return self.bibtexid

    @property
    def sortkey_contentid(self):
        return (self.sortkey_source, "%sv%s" % (self.arxivid, self.version))


@dataclass
class EprintEntry:
    bibtexid: str
    eprintid: str

    @classmethod
    def from_manual(cls, bibtexid, manual: str):
        slf = cls(bibtexid, "")
        manual = manual.strip().lower()
        assert not 'eprint' in manual
        assert not 'iacr' in manual
        eprintid = manual
        assert eprintid
        assert '/' in eprintid
        slf.eprintid = eprintid
        return slf

    def render_pybtex_entry(self):
        url = "https://eprint.iacr.org/" + self.eprintid
        soup = BeautifulSoup(requests.get(url).text, features="html.parser")

        data = bibtex_dblp.database.parse_bibtex(
            soup.select("#bibtex")[0].text)
        assert len(data.entries) == 1
        key = list(data.entries.keys())[0]
        return data.entries[key]

    @property
    def sortkey_source(self):
        return self.__class__.__name__

    @property
    def sortkey_bibtexid(self):
        return self.bibtexid

    @property
    def sortkey_contentid(self):
        return (self.sortkey_source, self.eprintid)


@dataclass
class Store:
    entries: list[Union[
        RawBibtexEntry,
        DblpEntry,
        ArxivEntry,
        EprintEntry,
    ]]

    def dump(self, filename):
        with open(filename, 'w') as outfile:
            yaml.dump(Store.Schema().dump(self),
                      outfile, sort_keys=True, default_flow_style=False)

    @classmethod
    def load(cls, filename):
        with open(filename, 'r') as infile:
            return Store.Schema().load(yaml.safe_load(infile.read()))

    @classmethod
    def load_or_empty(cls, filename):
        try:
            return cls.load(filename)
        except FileNotFoundError:
            return cls([])

    @property
    def bibtexids(self):
        for e in self.entries:
            yield e.bibtexid

    def sort(self, keyfn):
        self.entries.sort(key=keyfn)
