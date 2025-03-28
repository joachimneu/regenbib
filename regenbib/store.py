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
from diskcache import Cache
from pathlib import Path
import os


disk_cache_dir = os.path.join(str(Path.home()), '.cache', 'regenbib')
disk_cache = Cache(directory=disk_cache_dir)

@disk_cache.memoize(expire=60*60*24, tag='dblp')
def _lookup_dblp_by_dblpid(dblpid):
    return bibtex_dblp.dblp_api.get_bibtex(dblpid, bib_format=bibtex_dblp.dblp_api.BibFormat.condensed)

@disk_cache.memoize(expire=60*60*24, tag='arxiv')
def _lookup_arxiv_by_arxivid(arxivid):
    return arxiv.Search(id_list=[arxivid])

@disk_cache.memoize(expire=60*60*24, tag='eprint')
def _lookup_eprint_by_url(url):
    return requests.get(url).text


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
        result_dblp = _lookup_dblp_by_dblpid(self.dblpid)
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
        search = _lookup_arxiv_by_arxivid(qid)
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
        soup = BeautifulSoup(_lookup_eprint_by_url(url), features="html.parser")

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

    def dedup(self):
        entries = {}
        entries_to_remove = []

        for (idx, entry) in enumerate(self.entries):
            if not entry.bibtexid in entries.keys():
                entries[entry.bibtexid] = []
            entries[entry.bibtexid].append(idx)
        
        for (bibtexid, idxs) in entries.items():
            if len(idxs) > 1:
                print(f">>> Duplicate entry: {bibtexid} ({len(idxs)}x)")
                for idx in idxs:
                    print(self.entries[idx].sortkey_contentid, " ", self.entries[idx])
                if len(idxs) == 2 and self.entries[idxs[0]].sortkey_contentid == self.entries[idxs[1]].sortkey_contentid:
                    entries_to_remove.append(idxs[1])
                elif len(idxs) == 3 and self.entries[idxs[0]].sortkey_contentid == self.entries[idxs[1]].sortkey_contentid and self.entries[idxs[0]].sortkey_contentid == self.entries[idxs[2]].sortkey_contentid:
                    entries_to_remove.append(idxs[1])
                    entries_to_remove.append(idxs[2])
                else:
                    print("!!! MANUAL CLEANUP REQUIRED !!!")

        entries_to_remove.sort(reverse=True)
        for idx in entries_to_remove:
            del self.entries[idx]

