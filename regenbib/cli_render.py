#! /usr/bin/env python3

import argparse
import bibtex_dblp.database
from .store import Store


def run():
    parser = argparse.ArgumentParser(
        description='Render .bib bibliography file from references provided in .yaml file')
    parser.add_argument('--yaml', metavar='YAML_FILE', type=str,
                        default='references.yaml', help='File name of .yaml file')
    parser.add_argument('--bib', metavar='BIB_FILE', type=str,
                        default='references.bib', help='File name of .bib file')
    args = parser.parse_args()

    store = Store.load_or_empty(args.yaml)
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

    bibtex_dblp.database.write_to_file(bib, args.bib)


if __name__ == '__main__':
    run()
