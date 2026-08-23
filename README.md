# regenbib

*(Re-)generate tidy `.bib` files from online sources*


## Motivation

The gist of `regenbib` is as follows.
Instead of manually maintaining a `references.bib` file with a bunch of entries like this ...
```bibtex
@inproceedings{streamlet,
    author = "Chan, Benjamin Y. and Shi, Elaine",
    title = "Streamlet: Textbook Streamlined Blockchains",
    booktitle = "{AFT}",
    pages = "1--11",
    publisher = "{ACM}",
    year = "2020"
}
```
... you should maintain a `references.yaml` file with corresponding entries like that:
```yaml
entries:
- bibtexid: streamlet
  dblpid: conf/aft/ChanS20
```
The tool `regenbib` can then automatically (re-)generate the `references.bib` from the `references.yaml` in a consistent way by retrieving high-quality metadata information from the corresponding online source (in the example above: [dblp](https://dblp.org/)'s entry [conf/aft/ChanS20](https://dblp.org/rec/conf/aft/ChanS20.html?view=bibtex&param=0)).

Two tools help to maintain the `references.yaml` file, one per kind of user:

* `regenbib-import` is for **humans**: an interactive command-line loop. Using LaTeX's `.aux` file, it determines entries that are cited but are currently missing from the `references.yaml` file, and then helps the user determine an appropriate online reference through an interactive lookup. In the lookup process, an old (possibly messy) `references.bib` file can be used to obtain starting points for the search (eg, title/author in an old `references.bib` entry can be used to lookup the paper on dblp).
* `regenbib-query` is for **AI agents and scripts**: the same lookup machinery, but as one-shot, non-interactive commands, with the caller driving the loop and editing `references.yaml` itself. **AI agents must use `regenbib-query` and never run `regenbib-import`, which blocks waiting for keyboard input.**

See the usage examples below for details.


## Installation

With [uv](https://docs.astral.sh/uv/), install `regenbib` as a standalone tool, isolated in its own environment and available on your `PATH`:
```bash
$ uv tool install git+https://github.com/joachimneu/regenbib.git
```

Alternatively, install it into a virtual environment. If your LaTeX project already has one, activate it; otherwise set one up like this:
```bash
$ python -m venv venv
$ echo "venv/" >> .gitignore
$ source venv/bin/activate
```
Then install `regenbib`:
```bash
$ pip install git+https://github.com/joachimneu/regenbib.git
```

Either way, you should now have the commands `regenbib`, `regenbib-import`, `regenbib-query`, and `regenbib-scrub` available to you.


## Example Usage: Interactive Import (Humans)

Suppose we have an old `references.bib` file with this entry (and suppose it does not have a corresponding entry in our `references.yaml` file):
```bibtex
@misc{streamlet,
  author = {Chan and Shi},
  title  = {Streamlet Textbook Streamlined Blockchains}
}
```
We can easily import a corresponding entry to our `references.yaml` file with `regenbib-import`:
```
$ regenbib-import --bib references.bib --aux _build/main.aux --yaml references.yaml
Importing entry: streamlet
-> Current entry: Entry('misc',
  fields=[
    ('title', 'Streamlet Textbook Streamlined Blockchains')],
  persons=OrderedCaseInsensitiveDict([('author', [Person('Chan'), Person('Shi')])]))
-> Import method? [0=skip, 1=dblp-free-search, 2=arxiv-manual-id, 3=eprint-manual-id, 4=current-entry, 5=dblp-search-title, 6=dblp-search-authorstitle]: 6
-----> The search returned 2 matches:
-----> (1)	Benjamin Y. Chan, Elaine Shi:
		Streamlet: Textbook Streamlined Blockchains. AFT 2020
		https://doi.org/10.1145/3419614.3423256  https://dblp.org/rec/conf/aft/ChanS20
-----> (2)	Benjamin Y. Chan, Elaine Shi:
		Streamlet: Textbook Streamlined Blockchains. IACR Cryptol. ePrint Arch. (2020) 2020
		https://eprint.iacr.org/2020/088  https://dblp.org/rec/journals/iacr/ChanS20
-----> Intended publication? [0=abort]: 1
```
As you see, `regenbib-import` uses the messy/incomplete information from the old `references.bib` file to help us quickly determine the appropriate dblp entry. This adds the following entry to `references.yaml`:
```yaml
entries:
- bibtexid: streamlet
  dblpid: conf/aft/ChanS20
```
We can then re-generate a tidy `references.bib` file based on the `references.yaml` file:
```
$ regenbib --yaml references.yaml --bib references.bib
DblpEntry(bibtexid='streamlet', dblpid='conf/aft/ChanS20')
Entry('inproceedings',
  fields=[
    ('title', 'Streamlet: Textbook Streamlined Blockchains'),
    ('booktitle', '{AFT}'),
    ('pages', '1--11'),
    ('publisher', '{ACM}'),
    ('year', '2020')],
  persons=OrderedCaseInsensitiveDict([('author', [Person('Chan, Benjamin Y.'), Person('Shi, Elaine')])]))
$ cat references.bib
@inproceedings{streamlet,
    author = "Chan, Benjamin Y. and Shi, Elaine",
    title = "Streamlet: Textbook Streamlined Blockchains",
    booktitle = "{AFT}",
    pages = "1--11",
    publisher = "{ACM}",
    year = "2020"
}
```


## Example Usage: Non-Interactive Queries (AI Agents & Scripts)

**If you are an AI agent maintaining a bibliography, this is your workflow.** Do not run `regenbib-import` (it blocks waiting for keyboard input); instead, drive the import loop yourself with `regenbib-query`, which answers one question per invocation and exits:

1. Determine which cited keys still need an entry in `references.yaml`:
   ```bash
   $ regenbib-query missing --aux _build/main.aux --yaml references.yaml
   ```
   Add `--bib references.bib` to also see each missing key's old (possibly messy) `.bib` entry, whose title/author words make good search input for the next step.
2. For each missing key, find the online source. For works published at a venue, search dblp:
   ```bash
   $ regenbib-query search-dblp "streamlet textbook blockchains"
   ```
   Each match is printed with its `dblpid`. Prefer the published venue record over dblp's preprint records; for works that live on arXiv or the IACR ePrint archive (dblp lists them as `journals/corr/...` or `journals/iacr/...`), prefer the dedicated entry types in step 3 over a dblp entry.
3. Verify the metadata by previewing the entry (pick the command matching the source):
   ```bash
   $ regenbib-query get-dblp conf/aft/ChanS20 --bibtexid streamlet
   $ regenbib-query get-arxiv 2102.07932v3 --bibtexid fast-bft
   $ regenbib-query get-eprint 2023/397 --bibtexid hotstuff2
   $ regenbib-query get-doi https://doi.org/10.1145/3419614.3423256 --bibtexid streamlet
   ```
   Each prints the YAML entry followed by the BibTeX it renders to.
   If the work is on none of the four sources (e.g., a blog post, RFC, or whitepaper), keep its old `.bib` entry verbatim as a raw entry:
   ```bash
   $ regenbib-query get-raw streamlet --bib references.bib
   ```
4. If the metadata is right, append the printed YAML entry verbatim under `entries:` in `references.yaml`; otherwise, go back to step 2.
5. Regenerate the `.bib` file: `regenbib --yaml references.yaml --bib references.bib` (or the project's `make` wrapper, if it has one).


## Supported Entry Types & Online Metadata Sources

See entry types in `src/regenbib/store.py`:
* dblp
* arXiv
* IACR ePrint
* DOI (via content negotiation)
* Raw `.bib` entry
