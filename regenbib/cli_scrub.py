#! /usr/bin/env python3

import argparse
from .store import Store, disk_cache, get_arxiv_current_version, ArxivEntry


def run():
    parser = argparse.ArgumentParser(description='Perform maintenance on references provided in .yaml file')
    parser.add_argument('--yaml', metavar='YAML_FILE', type=str, default='references.yaml', help='File name of .yaml file')
    parser.add_argument('--fail-to-pdb', action='store_true',
                        default=False, help='Drop into pdb debugger on unexpected exceptions')
    
    subparsers = parser.add_subparsers(dest='command', required=True)

    subparser_sort = subparsers.add_parser('sort', help='Sort .yaml file')
    subparser_sort.add_argument('--by', metavar='ORDER', required=True, type=str, help='Sort order (non-empty combination of: S = source, B = bibtex-id, C = content-id)')
    
    subparser_dedup = subparsers.add_parser('dedup', help='Deduplicate .yaml file')

    subparser_rmcache = subparsers.add_parser('rmcache', help='Clear cached metadata')
    
    subparser_freeze_arxiv = subparsers.add_parser('freeze-arxiv', help='Set explicit versions for arXiv entries')
    subparser_freeze_arxiv.add_argument('entry_ids', metavar='ENTRY_ID', nargs='*', 
                                        help='BibTeX IDs of entries to freeze (if not provided, all arXiv entries are frozen)')

    args = parser.parse_args()

    try:
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
        
        elif args.command == 'freeze-arxiv':
            entry_ids = set(args.entry_ids) if args.entry_ids else None
            modified = False
            
            for entry in store.entries:
                if entry_ids is not None and entry.bibtexid not in entry_ids:
                    continue
                
                if not isinstance(entry, ArxivEntry):
                    if entry_ids is not None and entry.bibtexid in entry_ids:
                        assert False, f"Entry '{entry.bibtexid}' is not an arXiv entry"
                    continue
                
                if entry.version:
                    print(f"Skipping {entry.bibtexid}: version already set to v{entry.version}")
                    continue
                
                print(f"Freezing {entry.bibtexid} (arXiv:{entry.arxivid})...", end=" ")
                current_version = get_arxiv_current_version(entry.arxivid)
                entry.version = current_version
                modified = True
                print(f"set to v{current_version}")
            
            if not modified:
                return

        store.dump(args.yaml)
    except Exception:
        if args.fail_to_pdb:
            import pdb
            import traceback
            traceback.print_exc()
            pdb.post_mortem()
        else:
            raise


if __name__ == '__main__':
    run()
