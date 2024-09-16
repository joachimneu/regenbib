#! /usr/bin/env python3

import argparse
from .store import Store


def run():
    parser = argparse.ArgumentParser(
        description='Perform maintenance on references provided in .yaml file')
    parser.add_argument('--yaml', metavar='YAML_FILE', type=str,
                        default='references.yaml', help='File name of .yaml file')
    subparsers = parser.add_subparsers(dest='command')
    subparser_sort = subparsers.add_parser('sort', help='Sort .yaml file')
    subparser_sort.add_argument('--by', metavar='ORDER', type=str,
                                help='Sort order (non-empty combination of: S = source, B = bibtex-id, C = content-id)')
    args = parser.parse_args()

    store = Store.load_or_empty(args.yaml)

    if args.command == 'sort':
        assert set(args.by) <= set("SBC")
        keyfn = lambda e: [ e.sortkey_source if o == 'S' else e.sortkey_bibtexid if o == 'B' else e.sortkey_contentid if o == 'C' else '' for o in args.by ]
        store.sort(keyfn)

    store.dump(args.yaml)


if __name__ == '__main__':
    run()
