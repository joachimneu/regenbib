#! /usr/bin/env python3

import bibtex_dblp.database
from .store import Store
import sys


def run():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <YAML FILE> <BIB FILE>")
        exit(1)

    (YAML_FILE, BIB_FILE) = sys.argv[1:]

    store = Store.load_or_empty(YAML_FILE)
    bib = bibtex_dblp.database.parse_bibtex('')

    for entry in store.entries:
        print(entry)
        entry_pybtex = entry.render_pybtex_entry()

        if entry_pybtex.fields.get('series', '') == 'Lecture Notes in Computer Science':
            entry_pybtex.fields['series'] = 'LNCS'

        if entry_pybtex.fields.get('url', '').startswith('https://eprint.iacr.org/'):
            entry_pybtex.fields['note'] = entry_pybtex.fields.get('note', '')
            del entry_pybtex.fields['note']

        print(entry_pybtex)

        bib.entries[entry.bibtexid] = entry_pybtex

    bibtex_dblp.database.write_to_file(bib, BIB_FILE)


if __name__ == '__main__':
    run()
