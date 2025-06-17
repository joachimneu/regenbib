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


## AI-Assisted Import with OpenAI

`regenbib-import-openai` provides advanced AI-assisted bibliography import using OpenAI's structured output and tool capabilities. This is a separate command from the regular `regenbib-import` that leverages artificial intelligence to intelligently search and recommend the most appropriate bibliographic entries.

### Setup

To use AI-assisted import, you need to:

1. Install the OpenAI Python library (included in dependencies)
2. Set your OpenAI API key as an environment variable:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

### Usage

Run the AI-assisted import with:
```bash
regenbib-import-openai
```

The AI assistant will:
1. Analyze existing bibliographic information from your .bib file
2. Use multiple search tools to find relevant entries:
   - Web search for general information
   - DBLP database queries
   - arXiv preprint searches  
   - IACR ePrint archive searches
   - Website content reading for additional context
3. Apply intelligent prioritization rules:
   - Prefer officially published versions over preprints
   - For preprints without official publications, prefer direct IACR/arXiv entries over DBLP references
   - Only use raw BibTeX entries as a last resort
4. Present up to 5 ranked suggestions with detailed reasoning
5. Allow you to select the most appropriate entry

### Key Features

- **Intelligent Search**: Uses OpenAI's GPT-4 with custom tools to search multiple academic databases
- **Smart Prioritization**: Automatically prioritizes official publications over preprints
- **Multi-Source Search**: Searches DBLP, arXiv, IACR ePrint, and the general web
- **Structured Output**: Provides detailed reasoning for each suggestion
- **Seamless Integration**: Works with existing .aux, .bib, and .yaml workflow

### How It Works

The AI assistant uses OpenAI's tool/function calling capabilities to:
1. Search DBLP for officially published versions
2. Query arXiv for preprints and academic papers
3. Search IACR ePrint for cryptography-related works
4. Perform web searches for additional context
5. Read specific websites when promising leads are found
6. Synthesize all information to provide ranked recommendations

This approach ensures you get the most appropriate and highest-quality bibliographic entries for your references.
