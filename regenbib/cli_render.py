#! /usr/bin/env python3

import sys
import os
import copy
import argparse
import importlib.util
import bibtex_dblp.database
from .store import Store


def load_cfgpy(cfgpy_filename):
    if not os.path.exists(cfgpy_filename):
        return {}

    original_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True

    cfgpy_spec = importlib.util.spec_from_file_location('cfgpy', cfgpy_filename)
    cfgpy = importlib.util.module_from_spec(cfgpy_spec)
    cfgpy_spec.loader.exec_module(cfgpy)

    sys.dont_write_bytecode = original_dont_write_bytecode

    return cfgpy


def default_render_entry_hook(entry, entry_pybtex):
    if entry_pybtex.fields.get('series', '') == 'Lecture Notes in Computer Science':
        entry_pybtex.fields['series'] = 'LNCS'

    if entry_pybtex.fields.get('url', '').startswith('https://eprint.iacr.org/'):
        entry_pybtex.fields['note'] = entry_pybtex.fields.get('note', '')
        del entry_pybtex.fields['note']

    return (entry, entry_pybtex)


def run():
    parser = argparse.ArgumentParser(
        description='Render .bib bibliography file from references provided in .yaml file')
    parser.add_argument('--yaml', metavar='YAML_FILE', type=str,
                        default='references.yaml', help='File name of .yaml file')
    parser.add_argument('--bib', metavar='BIB_FILE', type=str,
                        default='references.bib', help='File name of .bib file')
    parser.add_argument('--cfgpy', metavar='CFGPY_FILE', type=str,
                        default='regenbib.cfg.py', help='File name of .cfg.py file')
    args = parser.parse_args()

    store = Store.load_or_empty(args.yaml)
    bib = bibtex_dblp.database.parse_bibtex('')
    cfgpy = load_cfgpy(args.cfgpy)

    render_entry_hook = cfgpy.get('render_entry_hook', default_render_entry_hook)

    for entry in store.entries:
        print(entry)
        entry_pybtex = entry.render_pybtex_entry()
        (entry, entry_pybtex) = render_entry_hook(copy.deepcopy(entry), copy.deepcopy(entry_pybtex))
        print(entry_pybtex)

        bib.entries[entry.bibtexid] = entry_pybtex

    bibtex_dblp.database.write_to_file(bib, args.bib)


if __name__ == '__main__':
    run()
