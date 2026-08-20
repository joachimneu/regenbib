#! /usr/bin/env python3

import argparse
import copy
import functools
import re

import bibtex_dblp.database
import bibtex_dblp.dblp_api
import bibtex_dblp.dblp_data
import bibtex_dblp.io
from pybtex.errors import set_strict_mode

from .store import Store


def format_dblp_publication(pub: bibtex_dblp.dblp_data.DblpPublication):
    authors = ", ".join([str(author) for author in pub.authors])
    book = ""
    if pub.venue:
        book += pub.venue + (f" ({pub.volume})" if pub.volume else "")
    if pub.booktitle:
        book += pub.booktitle
    return f"{authors}:\n\t\t{pub.title} {book} {pub.year} ({pub.pages})\n\t\t{pub.ee}  {pub.url}?view=bibtex"


def search_key_on_dblp(search_query, max_search_results=5):
    search_results = bibtex_dblp.dblp_api.search_publication(
        search_query, max_search_results=max_search_results
    )

    if search_results.total_matches == 0:
        return ("not-found", None)

    print(f"-----> The search returned {search_results.total_matches} matches:")
    if search_results.total_matches > max_search_results:
        print(f"-----> Displaying only the first {max_search_results} matches.")
    for i in range(len(search_results.results)):
        result = search_results.results[i]
        print(f"-----> ({i + 1})\t{format_dblp_publication(result.publication)}")

    # Let user select correct publication
    select = bibtex_dblp.io.get_user_number(
        "-----> Intended publication? [0=abort]: ", 0, search_results.total_matches
    )
    if select == 0:
        return ("cancelled", None)

    publication = search_results.results[select - 1].publication
    return ("found", publication.key)


def import_dblp_free_search(bibtexid):
    from .store import DblpEntry

    while True:
        search_query = bibtex_dblp.io.get_user_input("---> DBLP query [<empty>=abort]: ")
        if search_query == "":
            return None
        (status, key) = search_key_on_dblp(search_query)

        if status == "cancelled":
            print("---> Aborted, retry!")
        elif status == "not-found":
            print("---> No entry found, retry!")
        elif status == "found":
            return DblpEntry(bibtexid, key)
        else:
            raise NotImplementedError()


def import_dblp_search_title(bibtexid, entry_old):
    from .store import DblpEntry

    search_query = entry_old.fields["title"]
    (status, key) = search_key_on_dblp(search_query)

    if status == "cancelled" or status == "not-found":
        return None
    elif status == "found":
        return DblpEntry(bibtexid, key)
    else:
        raise NotImplementedError()


def import_dblp_search_authortitle(bibtexid, entry_old):
    from .store import DblpEntry

    authors = ", ".join([str(author) for author in entry_old.persons["author"]])
    search_query = "{} {}".format(authors, entry_old.fields["title"])
    (status, key) = search_key_on_dblp(search_query)

    if status == "cancelled" or status == "not-found":
        return None
    elif status == "found":
        return DblpEntry(bibtexid, key)
    else:
        raise NotImplementedError()


def import_current_raw_entry(bibtexid, entry_old):
    from .store import RawBibtexEntry

    return RawBibtexEntry.from_pybtex_entry(bibtexid, entry_old)


def import_arxiv_manualid(bibtexid):
    from .store import ArxivEntry

    while True:
        manual = bibtex_dblp.io.get_user_input("---> arXiv ID [<empty>=abort]: ")
        if manual == "":
            return None

        try:
            return ArxivEntry.from_manual(bibtexid, manual)
        except AssertionError:
            print("---> Assertion on parsing manual input, retry!")


def import_eprint_manualid(bibtexid):
    from .store import EprintEntry

    while True:
        manual = bibtex_dblp.io.get_user_input("---> IACR ePrint ID [<empty>=abort]: ")
        if manual == "":
            return None

        try:
            return EprintEntry.from_manual(bibtexid, manual)
        except AssertionError:
            print("---> Assertion on parsing manual input, retry!")


def import_doi_manualid(bibtexid):
    from .store import DoiEntry

    while True:
        manual = bibtex_dblp.io.get_user_input("---> DOI [<empty>=abort]: ")
        if manual == "":
            return None

        try:
            return DoiEntry.from_manual(bibtexid, manual)
        except AssertionError:
            print("---> Assertion on parsing manual input, retry!")


def attempt_import(methods):
    while True:
        methods_str = ", ".join(["0=skip"] + [f"{i + 1}={m[0]}" for (i, m) in enumerate(methods)])
        method = bibtex_dblp.io.get_user_number(
            f"-> Import method? [{methods_str}]: ", 0, len(methods)
        )

        if method == 0:
            return None
        else:
            ret = methods[method - 1][1]()
            if ret is not None:
                return ret
            else:
                continue


def run():
    parser = argparse.ArgumentParser(description="Import bibliography entries from DBLP.")
    parser.add_argument(
        "--bib",
        metavar="BIB_FILE",
        type=str,
        default="references.bib",
        help="File name of .bib file",
    )
    parser.add_argument(
        "--aux",
        metavar="AUX_FILE",
        type=str,
        default="_build/main.aux",
        help="File name of .aux file",
    )
    parser.add_argument(
        "--yaml",
        metavar="YAML_FILE",
        type=str,
        default="references.yaml",
        help="File name of .yaml file",
    )
    parser.add_argument(
        "--lax-pybtex-import",
        action="store_true",
        default=False,
        help="Disable strict mode of pybtex for .bib import",
    )
    parser.add_argument(
        "--fail-to-pdb",
        action="store_true",
        default=False,
        help="Drop into pdb debugger on unexpected exceptions",
    )
    args = parser.parse_args()

    try:
        METHODS_WITHOUT_OLDENTRY = [
            ("dblp-free-search", import_dblp_free_search),
            ("arxiv-manual-id", import_arxiv_manualid),
            ("eprint-manual-id", import_eprint_manualid),
            ("doi-manual-id", import_doi_manualid),
        ]

        METHODS_WITH_OLDENTRY = [
            ("current-entry", import_current_raw_entry),
            ("dblp-search-title", import_dblp_search_title),
            ("dblp-search-authorstitle", import_dblp_search_authortitle),
        ]

        bibtexids_included = []
        with open(args.aux) as infile:
            for line in infile.readlines():
                line = line.strip()

                # BibLaTeX
                matches = re.findall(r"\\abx@aux@cite\{0\}\{(.*?)\}", line)
                assert len(matches) <= 1
                if matches:
                    m = matches[0]
                    if m not in bibtexids_included:
                        bibtexids_included.append(m)

                # BibTeX
                matches = re.findall(r"\\citation\{(.*?)\}", line)
                assert len(matches) <= 1
                if matches:
                    for m in matches[0].split(","):
                        m = m.strip()
                        if m not in bibtexids_included:
                            bibtexids_included.append(m)

        store = Store.load_or_empty(args.yaml)

        if args.lax_pybtex_import:
            set_strict_mode(False)
        bibtex_entries = bibtex_dblp.database.load_from_file(args.bib)
        set_strict_mode()

        for bibtexid in bibtexids_included:
            if bibtexid in store.bibtexids:
                continue

            print("Importing entry:", bibtexid)

            entry_old = None
            if bibtexid in bibtex_entries.entries:
                entry_old = bibtex_entries.entries[bibtexid]
            else:
                for tmp_entry in bibtex_entries.entries.values():
                    tmp_ids = tmp_entry.fields.get("ids", "")
                    if not tmp_ids:
                        tmp_ids = []
                    else:
                        tmp_ids = [tmp_id.strip() for tmp_id in tmp_ids.split(",")]
                    if bibtexid in tmp_ids:
                        entry_old = copy.deepcopy(tmp_entry)
                        entry_old.key = bibtexid
                        del entry_old.fields["ids"]
                        break

            methods = [
                (name, functools.partial(fun, bibtexid)) for (name, fun) in METHODS_WITHOUT_OLDENTRY
            ]

            if entry_old is None:
                print("-> Not found in .bib file!")
            else:
                print("-> Current entry:", entry_old)
                methods += [
                    (name, functools.partial(fun, bibtexid, entry_old))
                    for (name, fun) in METHODS_WITH_OLDENTRY
                ]

            entry = attempt_import(methods)

            if entry is not None:
                store.entries.append(entry)
                store.dump(args.yaml)

    except Exception:
        if args.fail_to_pdb:
            import pdb
            import traceback

            traceback.print_exc()
            pdb.post_mortem()
        else:
            raise


if __name__ == "__main__":
    run()
