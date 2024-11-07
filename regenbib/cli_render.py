#! /usr/bin/env python3

import sys
import os
import copy
import hashlib
import argparse
import importlib.util
import bibtex_dblp.database
from pybtex.database.output.bibtex import Writer
from .store import Store


def default_render_entry_hook(entry, entry_pybtex):
    if entry_pybtex.fields.get('series', '') == 'Lecture Notes in Computer Science':
        entry_pybtex.fields['series'] = 'LNCS'

    if entry_pybtex.fields.get('url', '').startswith('https://eprint.iacr.org/'):
        entry_pybtex.fields['note'] = entry_pybtex.fields.get('note', '')
        del entry_pybtex.fields['note']

    return (entry, entry_pybtex)


cfgpy_defaults = {
    'render_entry_hook': default_render_entry_hook,
}

def load_cfgpy(cfgpy_filename):
    cfgpy_dict = {}

    if not os.path.exists(cfgpy_filename):
        return copy.deepcopy(cfgpy_defaults)

    original_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True

    cfgpy_spec = importlib.util.spec_from_file_location('cfgpy', cfgpy_filename)
    cfgpy = importlib.util.module_from_spec(cfgpy_spec)
    cfgpy_spec.loader.exec_module(cfgpy)

    sys.dont_write_bytecode = original_dont_write_bytecode

    for k in cfgpy_defaults.keys():
        cfgpy_dict[k] = getattr(cfgpy, k, cfgpy_defaults[k])

    return cfgpy_dict


class MyBiblatexWriter(Writer):
    def _write_rawlist(self, stream, type, value):
        stream.write(u',\n    %s = {%s}' % (type, ', '.join(value)))

    def write_stream(self, bib_data, stream):
        self._write_preamble(stream, bib_data.preamble)

        first = True
        for key, entry in bib_data.entries.items():
            if not first:
                stream.write(u'\n')
            first = False

            stream.write(u'@%s' % entry.original_type)
            stream.write(u'{%s' % key)
            for type, value in entry.rawlists.items():
                self._write_rawlist(stream, type, value)
            for role, persons in entry.persons.items():
                self._write_persons(stream, persons, role)
            for type, value in entry.fields.items():
                self._write_field(stream, type, value)
            stream.write(u'\n}\n')


def run():
    parser = argparse.ArgumentParser(
        description='Render .bib bibliography file from references provided in .yaml file')
    parser.add_argument('--yaml', metavar='YAML_FILE', type=str,
                        default='references.yaml', help='File name of .yaml file')
    parser.add_argument('--bib', metavar='BIB_FILE', type=str,
                        default='references.bib', help='File name of .bib file')
    parser.add_argument('--cfgpy', metavar='CFGPY_FILE', type=str,
                        default='regenbib.cfg.py', help='File name of .cfg.py file')
    parser.add_argument('--biblatex', action='store_true',
                        default=False, help='Render BibLaTeX instead of BibTeX')
    parser.add_argument('--biblatex-group', action='store_true',
                        default=False, help='Identify and collapse identical entries (BibLaTeX only)')
    args = parser.parse_args()

    assert(not args.biblatex_group or args.biblatex)

    store = Store.load_or_empty(args.yaml)
    bib = bibtex_dblp.database.parse_bibtex('')
    cfgpy = load_cfgpy(args.cfgpy)

    entries = []

    for entry in store.entries:
        print(entry)
        entry_pybtex = entry.render_pybtex_entry()
        (entry, entry_pybtex) = cfgpy['render_entry_hook'](copy.deepcopy(entry), copy.deepcopy(entry_pybtex))
        entry_contentid = hashlib.sha256(repr(entry.sortkey_contentid).encode()).hexdigest()
        print(entry_pybtex)
        entries.append((entry_contentid, entry, entry_pybtex))

    if args.biblatex_group:
        new_entries = {}

        for (entry_contentid, entry, entry_pybtex) in entries:
            if not entry_contentid in new_entries.keys():
                entry_pybtex.rawlists = getattr(entry_pybtex, 'rawlists', {})
                entry_pybtex.rawlists['ids'] = entry_pybtex.rawlists.get('ids', [])
                new_entries[entry_contentid] = (entry_contentid, entry, entry_pybtex)
            
            new_entries[entry_contentid][2].rawlists['ids'].append(entry.bibtexid)

        entries = list(new_entries.values())

    if args.biblatex:
        # Biblatex rendering
        for (entry_contentid, entry, entry_pybtex) in entries:
            entry_pybtex.rawlists = getattr(entry_pybtex, 'rawlists', {})
            entry_pybtex.rawlists['ids'] = entry_pybtex.rawlists.get('ids', [])
            entry_pybtex.rawlists['ids'].append(entry.bibtexid)
            entry_pybtex.rawlists['ids'] = list(set(entry_pybtex.rawlists['ids']))
            cnt = -1
            primary_bibtexid = None
            while True:
                cnt += 1
                primary_bibtexid = 'reference_' + entry_contentid + '_' + str(cnt)
                if not primary_bibtexid in bib.entries.keys():
                    break
            bib.entries[primary_bibtexid] = entry_pybtex
        MyBiblatexWriter().write_file(bib, args.bib)

    else:
        # Bibtex rendering
        for (entry_contentid, entry, entry_pybtex) in entries:
            bib.entries[entry.bibtexid] = entry_pybtex
        bibtex_dblp.database.write_to_file(bib, args.bib)


if __name__ == '__main__':
    run()
