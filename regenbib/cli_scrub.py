#! /usr/bin/env python3

import argparse
from .store import Store, disk_cache


def run():
    parser = argparse.ArgumentParser(description='Perform maintenance on references provided in .yaml file')
    parser.add_argument('--yaml', metavar='YAML_FILE', type=str, default='references.yaml', help='File name of .yaml file')
    
    subparsers = parser.add_subparsers(dest='command', required=True)

    subparser_sort = subparsers.add_parser('sort', help='Sort .yaml file')
    subparser_sort.add_argument('--by', metavar='ORDER', required=True, type=str, help='Sort order (non-empty combination of: S = source, B = bibtex-id, C = content-id)')
    
    subparser_dedup = subparsers.add_parser('dedup', help='Deduplicate .yaml file')

    subparser_rmcache = subparsers.add_parser('rmcache', help='Clear cached metadata')

    args = parser.parse_args()

    store = Store.load_or_empty(args.yaml)

    if args.command == 'sort':
        assert set(args.by) <= set("SBC")
        keyfn = lambda e: [ e.sortkey_source if o == 'S' else e.sortkey_bibtexid if o == 'B' else e.sortkey_contentid if o == 'C' else '' for o in args.by ]
        store.sort(keyfn)
        
    elif args.command == 'dedup':
        store.dedup()

    elif args.command == 'rmcache':
        print("Pre-clear", "stats (hits, misses):", disk_cache.stats())
        print("Pre-clear", "check (warnings):", disk_cache.check())
        disk_cache.clear()
        print("Post-clear", "stats (hits, misses):", disk_cache.stats())
        print("Post-clear", "check (warnings):", disk_cache.check())

    store.dump(args.yaml)


if __name__ == '__main__':
    run()
