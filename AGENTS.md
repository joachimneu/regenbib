# AGENTS.md

Guidance for AI agents working in this repository.

## Overview

regenbib (re-)generates tidy `.bib` files from online metadata sources (DBLP, arXiv, IACR ePrint, DOI). Users maintain a `references.yaml` with pointers to online sources; regenbib fetches authoritative metadata and renders consistent BibTeX.

Three entry points:

- `regenbib` — render `.bib` from YAML (`regenbib.cli_render:run`)
- `regenbib-import` — pull cited keys from a LaTeX `.aux` file and interactively look them up (`regenbib.cli_import:run`)
- `regenbib-scrub` — sort, dedup, freeze/unfreeze arXiv versions, clear cache (`regenbib.cli_scrub:run`)

## Development

Everything runs through [uv](https://docs.astral.sh/uv/); the build backend is `uv_build`. Source lives in `src/regenbib/`, so the test suite exercises the installed package rather than the working tree.

```bash
uv sync --group dev     # create .venv with runtime + dev dependencies
uv run pytest           # test
uv run ruff check .     # lint
uv run ruff format .    # format
uv build                # build sdist + wheel
```

CI (`.github/workflows/ci.yml`) runs lint, the test matrix on Python 3.10–3.14, and a build job that checks wheel metadata and smoke-tests the console scripts.

## Architecture

- `store.py` — data models (`RawBibtexEntry`, `DblpEntry`, `ArxivEntry`, `EprintEntry`, `DoiEntry`, `Store`) serialized to/from YAML via marshmallow-dataclass; the `_lookup_*` metadata fetchers, disk-cached under `~/.cache/regenbib/` (~24h TTL); `LookupConfig` for per-source delays and User-Agent headers.
- `cli_render.py` — loads YAML, renders each entry via `render_pybtex_entry()`, applies optional hooks from `regenbib.cfg.py`, writes BibTeX or BibLaTeX.
- `cli_import.py` — parses `.aux` files (BibTeX and BibLaTeX citation macros), searches DBLP, prompts the user to add entries to the YAML.
- `cli_scrub.py` — the `sort`, `dedup`, `freeze-arxiv`, `unfreeze-arxiv`, and `rmcache` subcommands.

## Testing Pitfalls

- `store.py` builds its `diskcache.Cache` under `Path.home()` at import time. `tests/conftest.py` redirects `HOME` into a temporary directory *before* importing it; preserve that ordering.
- An autouse fixture blocks all network transports, so unstubbed lookups fail loudly. Use the `stub_lookups` fixture.
- `cli_scrub` binds `_lookup_arxiv_version_by_arxivid` via `from`-import, so it must be patched in both modules (`stub_lookups` does).

## Dependency Constraints

- `marshmallow-dataclass` must stay `>=8.7.1`, requested without extras. Earlier versions pull typeguard 3.x, which cannot be imported on Python 3.12+ — and the failure surfaces only when `Store.Schema()` is first built (`--help` still works). `tests/test_serialization.py::TestUnionDiscrimination` guards this.
- `Store.entries` is annotated `list[Union[...]]` and the annotation is consumed at runtime by marshmallow-dataclass; do not rewrite it as a PEP 604 union (ruff's `UP007` is ignored for this reason).

## Branch Workflow

- `main` — production branch
- `dev` — development branch; PRs merge into `dev` or `main`
