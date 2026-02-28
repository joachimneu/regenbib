# AGENTS.md

This file provides guidance to AI agents when working with code in this repository.

## Project Overview

regenbib is a Python CLI tool that (re-)generates tidy `.bib` files from online metadata sources (DBLP, arXiv, IACR ePrint, DOI). Users maintain a YAML file (`references.yaml`) with references to online sources, and regenbib fetches authoritative metadata to produce consistent BibTeX output.

## Build & Development Commands

```bash
poetry install          # Install dependencies
poetry build            # Build package (wheel + sdist)
poetry publish          # Publish to PyPI
```

There are three CLI entry points:
- `regenbib` — Main command: renders `.bib` from YAML (`regenbib.cli_render:run`)
- `regenbib-import` — Parses LaTeX `.aux` files, searches online sources, adds entries to YAML (`regenbib.cli_import:run`)
- `regenbib-scrub` — Sorts, deduplicates entries, or clears cache (`regenbib.cli_scrub:run`)

There is no test suite or CI pipeline.

## Architecture

All source code lives in `regenbib/` (4 files, ~800 lines total):

- **`store.py`** — Core module. Contains all data models (`RawBibtexEntry`, `DblpEntry`, `ArxivEntry`, `EprintEntry`, `DoiEntry`, `Store`) as `@dataclass` classes with `marshmallow-dataclass` for YAML serialization. Also contains all metadata lookup functions (`_lookup_dblp_by_dblpid`, `_lookup_arxiv_by_arxivid`, `_lookup_eprint_by_eprintid`, `_lookup_doi_by_doi`) which use `diskcache` for persistent caching (~24h TTL at `~/.cache/regenbib/`). The `LookupConfig` class manages per-source delays and User-Agent headers.

- **`cli_render.py`** — Generates `.bib` output. Loads YAML, calls each entry's `render_pybtex_entry()`, applies optional hooks from `regenbib.cfg.py`, writes BibTeX or BibLaTeX output. Contains `MyBiblatexWriter` for BibLaTeX-specific formatting.

- **`cli_import.py`** — Interactive import workflow. Parses `.aux` files (both BibTeX and BibLaTeX formats), searches DBLP, and prompts user to select/add entries to YAML.

- **`cli_scrub.py`** — Maintenance subcommands: `sort`, `dedup`, `rmcache`.

## Key Patterns

- Each entry type class has: `render_pybtex_entry()` for BibTeX generation, `from_manual()` classmethod for parsing user input, and `sortkey_*` properties for sorting.
- Lookup functions are module-level with disk caching; they fetch BibTeX strings from external APIs/endpoints.
- The ePrint lookup uses Sickle (OAI-PMH protocol) against `https://eprint.iacr.org/oai`.
- arXiv lookup fetches from `https://arxiv.org/bibtex/{id}`.
- Error handling uses `assert` for validation. The `--fail-to-pdb` flag drops into pdb on exceptions.

## Dependencies

Requires Python `^3.10`. Key libraries: `bibtex-dblp` (DBLP API), `arxiv` (arXiv API), `Sickle` (OAI-PMH for ePrint), `requests` (HTTP/DOI), `marshmallow-dataclass` (pinned at `8.5.14` for YAML serialization), `diskcache` (persistent caching), `pybtex` (BibTeX processing).

## Branch Workflow

- `main` — production branch
- `dev` — development branch
- Feature branches are typically prefixed with `copilot/` or `dev-`
- PRs merge into `dev` or `main`