import copy
import re


def cited_bibtexids(aux_filename):
    """Cited BibTeX keys from a LaTeX .aux file (BibTeX and BibLaTeX citation
    macros), in citation order, deduplicated."""
    bibtexids = []
    with open(aux_filename) as infile:
        for line in infile.readlines():
            line = line.strip()

            # BibLaTeX
            matches = re.findall(r"\\abx@aux@cite\{0\}\{(.*?)\}", line)
            assert len(matches) <= 1
            if matches:
                m = matches[0]
                if m not in bibtexids:
                    bibtexids.append(m)

            # BibTeX
            matches = re.findall(r"\\citation\{(.*?)\}", line)
            assert len(matches) <= 1
            if matches:
                for m in matches[0].split(","):
                    m = m.strip()
                    if m not in bibtexids:
                        bibtexids.append(m)

    return bibtexids


def find_bib_entry(bib_data, bibtexid):
    """Entry for `bibtexid` in parsed .bib data, honoring BibLaTeX `ids`
    aliases; None if absent."""
    if bibtexid in bib_data.entries:
        return bib_data.entries[bibtexid]

    for entry in bib_data.entries.values():
        ids = entry.fields.get("ids", "")
        ids = [tmp_id.strip() for tmp_id in ids.split(",")] if ids else []
        if bibtexid in ids:
            entry = copy.deepcopy(entry)
            entry.key = bibtexid
            del entry.fields["ids"]
            return entry

    return None
