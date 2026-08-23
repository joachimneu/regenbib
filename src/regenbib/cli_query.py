#! /usr/bin/env python3

import argparse
import math

import bibtex_dblp.database
import bibtex_dblp.dblp_api
import yaml
from pybtex.errors import set_strict_mode

from .store import (
    ArxivEntry,
    DblpEntry,
    DoiEntry,
    EprintEntry,
    RawBibtexEntry,
    Store,
    _get_dblp_session,
)
from .utils_args import add_lookup_config_args, set_lookup_config_from_args
from .utils_latex import cited_bibtexids, find_bib_entry


def print_yaml_and_bibtex(entry):
    dumped_entries = Store.Schema().dump(Store([entry]))["entries"]
    print("YAML entry (append under `entries:` in the .yaml file):")
    print(
        yaml.dump(dumped_entries, sort_keys=True, default_flow_style=False, width=math.inf),
        end="",
    )
    print()
    print("BibTeX preview (before any regenbib.cfg.py hooks):")
    entry_pybtex = entry.render_pybtex_entry()
    entry_pybtex.key = entry.bibtexid
    print(entry_pybtex.to_string("bibtex"), end="")


def cmd_search_dblp(args):
    search_results = bibtex_dblp.dblp_api.search_publication(
        _get_dblp_session(), args.query, max_search_results=args.max_results
    )

    if search_results.total_matches == 0:
        print("0 matches.")
        return

    print(f"{search_results.total_matches} matches (showing {len(search_results.results)}):")
    for i, result in enumerate(search_results.results, start=1):
        pub = result.publication
        print()
        print(f"({i}) dblpid: {pub.key}")
        fields = [
            ("title", pub.title),
            ("authors", ", ".join(str(author) for author in pub.authors)),
            ("venue", pub.venue),
            ("volume", pub.volume),
            ("booktitle", pub.booktitle),
            ("year", pub.year),
            ("pages", pub.pages),
            ("doi", pub.doi),
            ("ee", pub.ee),
            ("url", pub.url),
        ]
        for name, value in fields:
            if value:
                print(f"    {name}: {value}")


def cmd_get_dblp(args):
    print_yaml_and_bibtex(DblpEntry(args.bibtexid, args.dblpid))


def cmd_get_arxiv(args):
    print_yaml_and_bibtex(ArxivEntry.from_manual(args.bibtexid, args.arxivid))


def cmd_get_eprint(args):
    print_yaml_and_bibtex(EprintEntry.from_manual(args.bibtexid, args.eprintid))


def cmd_get_doi(args):
    print_yaml_and_bibtex(DoiEntry.from_manual(args.bibtexid, args.doi))


def cmd_get_raw(args):
    if args.lax_pybtex_import:
        set_strict_mode(False)
    bibtex_entries = bibtex_dblp.database.load_from_file(args.bib)
    set_strict_mode()

    entry_old = find_bib_entry(bibtex_entries, args.key)
    assert entry_old is not None, f"Entry '{args.key}' not found in {args.bib}"
    bibtexid = args.bibtexid if args.bibtexid is not None else args.key
    print_yaml_and_bibtex(RawBibtexEntry.from_pybtex_entry(bibtexid, entry_old))


def cmd_missing(args):
    cited = cited_bibtexids(args.aux)
    known = set(Store.load_or_empty(args.yaml).bibtexids)
    missing = [bibtexid for bibtexid in cited if bibtexid not in known]

    if args.bib is None:
        for bibtexid in missing:
            print(bibtexid)
        return

    if args.lax_pybtex_import:
        set_strict_mode(False)
    bibtex_entries = bibtex_dblp.database.load_from_file(args.bib)
    set_strict_mode()

    for bibtexid in missing:
        print(f"== {bibtexid} ==")
        entry_old = find_bib_entry(bibtex_entries, bibtexid)
        if entry_old is None:
            print("(no entry in the .bib file)")
        else:
            print(entry_old.to_string("bibtex"), end="")
        print()


def _add_bibtexid_arg(parser):
    parser.add_argument(
        "--bibtexid",
        metavar="KEY",
        type=str,
        default="FIXME",
        help="BibTeX key to use in the previewed entry (default: FIXME)",
    )


def run():
    parser = argparse.ArgumentParser(
        description="One-shot, non-interactive metadata queries for maintaining a "
        "references .yaml file; each invocation answers a single question and exits, "
        "so a caller (e.g., an AI agent) can drive the import loop and edit the "
        ".yaml file itself"
    )

    # Shared options, attached to every subcommand so they can be given after it.
    common = argparse.ArgumentParser(add_help=False)
    add_lookup_config_args(common)
    common.add_argument(
        "--fail-to-pdb",
        action="store_true",
        default=False,
        help="Drop into pdb debugger on unexpected exceptions",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparser = subparsers.add_parser(
        "missing",
        parents=[common],
        help="List cited BibTeX keys that are absent from the .yaml file",
    )
    subparser.add_argument(
        "--aux",
        metavar="AUX_FILE",
        type=str,
        default="_build/main.aux",
        help="File name of .aux file",
    )
    subparser.add_argument(
        "--yaml",
        metavar="YAML_FILE",
        type=str,
        default="references.yaml",
        help="File name of .yaml file",
    )
    subparser.add_argument(
        "--bib",
        metavar="BIB_FILE",
        type=str,
        default=None,
        help="Also show each missing key's entry from this (old) .bib file",
    )
    subparser.add_argument(
        "--lax-pybtex-import",
        action="store_true",
        default=False,
        help="Disable strict mode of pybtex for .bib import",
    )
    subparser.set_defaults(func=cmd_missing)

    subparser = subparsers.add_parser(
        "search-dblp",
        parents=[common],
        help="Search DBLP for publications matching a free-text query",
    )
    subparser.add_argument(
        "query",
        metavar="QUERY",
        type=str,
        help="Free-text search query (e.g., title and/or author words)",
    )
    subparser.add_argument(
        "--max-results",
        metavar="N",
        type=int,
        default=10,
        help="Maximum number of matches to show (default: 10)",
    )
    subparser.set_defaults(func=cmd_search_dblp)

    subparser = subparsers.add_parser(
        "get-dblp",
        parents=[common],
        help="Preview the YAML entry and BibTeX for a DBLP ID",
    )
    subparser.add_argument(
        "dblpid", metavar="DBLPID", type=str, help="DBLP ID (e.g., conf/aft/ChanS20)"
    )
    _add_bibtexid_arg(subparser)
    subparser.set_defaults(func=cmd_get_dblp)

    subparser = subparsers.add_parser(
        "get-arxiv",
        parents=[common],
        help="Preview the YAML entry and BibTeX for an arXiv ID",
    )
    subparser.add_argument(
        "arxivid",
        metavar="ARXIVID",
        type=str,
        help="arXiv ID, optionally versioned (e.g., 2102.07932 or 2102.07932v3)",
    )
    _add_bibtexid_arg(subparser)
    subparser.set_defaults(func=cmd_get_arxiv)

    subparser = subparsers.add_parser(
        "get-eprint",
        parents=[common],
        help="Preview the YAML entry and BibTeX for an IACR ePrint ID",
    )
    subparser.add_argument(
        "eprintid", metavar="EPRINTID", type=str, help="IACR ePrint ID (e.g., 2023/397)"
    )
    _add_bibtexid_arg(subparser)
    subparser.set_defaults(func=cmd_get_eprint)

    subparser = subparsers.add_parser(
        "get-doi",
        parents=[common],
        help="Preview the YAML entry and BibTeX for a DOI",
    )
    subparser.add_argument(
        "doi",
        metavar="DOI",
        type=str,
        help="DOI, bare or as a doi.org URL (e.g., 10.1145/3419614.3423256)",
    )
    _add_bibtexid_arg(subparser)
    subparser.set_defaults(func=cmd_get_doi)

    subparser = subparsers.add_parser(
        "get-raw",
        parents=[common],
        help="Preview the YAML entry and BibTeX for an entry kept verbatim from an existing .bib file",
    )
    subparser.add_argument(
        "key",
        metavar="KEY",
        type=str,
        help="BibTeX key of the entry in the .bib file (BibLaTeX `ids` aliases are honored)",
    )
    subparser.add_argument(
        "--bib",
        metavar="BIB_FILE",
        type=str,
        default="references.bib",
        help="File name of .bib file",
    )
    subparser.add_argument(
        "--bibtexid",
        metavar="KEY",
        type=str,
        default=None,
        help="BibTeX key to use in the previewed entry (default: KEY)",
    )
    subparser.add_argument(
        "--lax-pybtex-import",
        action="store_true",
        default=False,
        help="Disable strict mode of pybtex for .bib import",
    )
    subparser.set_defaults(func=cmd_get_raw)

    args = parser.parse_args()

    try:
        set_lookup_config_from_args(args)
        args.func(args)

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
