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

The tool `regenbib-import` helps to maintain the `references.yaml` file. Using LaTeX's `.aux` file, it determines entries that are cited but are currently missing from the `references.yaml` file. It then helps the user determine an appropriate online reference through an interactive lookup right from the command line. In the lookup process, an old (possibly messy) `references.bib` file can be used to obtain starting points for the search (eg, title/author in an old `references.bib` entry can be used to lookup the paper on dblp).

See the usage example below for details.


## Installation

If your LaTeX project already has a Python virtual environment, activate it.
Otherwise, setup and activate a virtual environment like this:
```bash
$ python -m venv venv
$ echo "venv/" >> .gitignore
$ source venv/bin/activate
```
Then install `regenbib`:
```bash
$ pip install git+https://github.com/joachimneu/regenbib.git
```
You should now have the commands `regenbib` and `regenbib-import` available to you.


## Example Usage

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


## Supported Entry Types & Online Metadata Sources

See entry types in `regenbib/store.py`:
* dblp
* arXiv
* IACR ePrint
* Raw `.bib` entry

## AI-Assisted Import

`regenbib-import` now supports AI-assisted bibliography import using OpenAI's API. When enabled, this feature uses artificial intelligence to automatically generate optimal search queries for finding bibliographic entries on DBLP.

### Setup

To use AI-assisted import, you need to:

1. Install the OpenAI Python library (included in dependencies)
2. Set your OpenAI API key as an environment variable:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

### Usage

When running `regenbib-import`, you'll see "ai-assisted" as the first option in the import methods menu:

```
-> Import method? [0=skip, 1=ai-assisted, 2=dblp-free-search, 3=arxiv-manual-id, 4=eprint-manual-id, 5=ai-assisted, 6=current-entry, 7=dblp-search-title, 8=dblp-search-authorstitle]:
```

The AI-assisted method will:
1. Analyze the available bibliographic information (title, authors, year, venue)
2. Generate multiple optimized search queries using AI
3. Automatically try each query on DBLP
4. Present you with the best matches found

This is particularly useful when:
- You have incomplete or messy bibliographic data
- Manual searches are not finding the right entries
- You want to automate the search process

### How it works

The AI assistant examines your bibliographic data and creates targeted search queries, similar to how the [blockchain-deadlines chatgpt-updater](https://github.com/blockchain-deadlines/blockchain-deadlines.github.io/blob/main/chatgpt-updater.py) works for conference deadline updates.
