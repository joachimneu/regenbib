#! /usr/bin/env python3

import argparse
import json
import os
import re
import copy
from typing import List, Optional, Union, Dict, Any, Literal
from pydantic import BaseModel
from pybtex.errors import set_strict_mode
import bibtex_dblp.dblp_data
import bibtex_dblp.dblp_api
import bibtex_dblp.io
import bibtex_dblp.database
import requests
from bs4 import BeautifulSoup
import arxiv
from .store import Store, DblpEntry, ArxivEntry, EprintEntry, RawBibtexEntry


# Pydantic models for structured output matching store entry types
class DblpEntryData(BaseModel):
    bibtexid: str
    dblpid: str
    entry_type: Literal["dblp"] = "dblp"


class ArxivEntryData(BaseModel):
    bibtexid: str
    arxivid: str
    version: str
    entry_type: Literal["arxiv"] = "arxiv"


class EprintEntryData(BaseModel):
    bibtexid: str
    eprintid: str
    entry_type: Literal["eprint"] = "eprint"


class RawBibtexEntryData(BaseModel):
    bibtexid: str
    rawbibtex: List[str]
    entry_type: Literal["raw"] = "raw"


class BibliographicSuggestions(BaseModel):
    """Structured output containing up to 5 bibliographic suggestions."""
    suggestions: List[Union[DblpEntryData, ArxivEntryData, EprintEntryData, RawBibtexEntryData]]
    reasoning: str  # Overall reasoning for the suggestions


def callback_search(query: str) -> Dict[str, Any]:
    """Search the web using Serper API."""
    serper_api_key = os.environ.get("SERPER_API_KEY")
    if not serper_api_key:
        return {"error": "SERPER_API_KEY environment variable not set"}
    
    try:
        url = "https://google.serper.dev/search"
        payload = json.dumps({
            "q": query,
            "num": 10
        })
        headers = {
            'X-API-KEY': serper_api_key,
            'Content-Type': 'application/json'
        }
        
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        
        return response.json()
        
    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}


def callback_browse_html(url: str) -> Dict[str, Any]:
    """Browse a website and return HTML content with length limitations."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Limit HTML content to avoid token limits (50KB max)
        html_content = response.text
        if len(html_content) > 50000:
            html_content = html_content[:50000] + "... [truncated]"
        
        return {
            "url": url,
            "status_code": response.status_code,
            "html": html_content
        }
        
    except Exception as e:
        return {"error": f"Failed to browse {url}: {str(e)}"}


def callback_browse_text(url: str) -> Dict[str, Any]:
    """Browse a website and return clean text content with length limitations."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text and clean it up
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        # Limit text length to avoid token limits (10KB max)
        if len(text) > 10000:
            text = text[:10000] + "... [truncated]"
        
        return {
            "url": url,
            "status_code": response.status_code,
            "text": text
        }
        
    except Exception as e:
        return {"error": f"Failed to browse {url}: {str(e)}"}


def callback_query_dblp(search_query: str, max_results: int = 5) -> Dict[str, Any]:
    """Query DBLP and return bibliographic information."""
    try:
        search_results = bibtex_dblp.dblp_api.search_publication(
            search_query, max_search_results=max_results)
        
        if search_results.total_matches == 0:
            return {"error": f"No DBLP results found for query: {search_query}"}
        
        results = []
        for i, result in enumerate(search_results.results[:max_results]):
            pub = result.publication
            authors = ", ".join([str(author) for author in pub.authors])
            venue_info = ""
            if pub.venue:
                venue_info += pub.venue + (" ({})".format(pub.volume) if pub.volume else "")
            if pub.booktitle:
                venue_info += pub.booktitle
            
            entry_info = {
                'index': i + 1,
                'title': pub.title,
                'authors': authors,
                'year': pub.year,
                'venue': venue_info,
                'pages': pub.pages,
                'dblp_key': pub.key,
                'url': pub.url
            }
            results.append(entry_info)
        
        return {
            'total_matches': search_results.total_matches,
            'results_shown': len(results),
            'results': results
        }
        
    except Exception as e:
        return {"error": f"DBLP query failed: {str(e)}"}


def callback_lookup_arxiv_by_id(arxiv_id: str) -> Dict[str, Any]:
    """Lookup a specific arXiv paper by its ID."""
    try:
        # Clean the arXiv ID
        arxiv_id = arxiv_id.replace('arXiv:', '').strip()
        
        search = arxiv.Search(id_list=[arxiv_id])
        results = list(search.results())
        
        if not results:
            return {"error": f"No arXiv paper found with ID: {arxiv_id}"}
        
        result = results[0]
        entry_info = {
            'title': result.title,
            'authors': ', '.join([author.name for author in result.authors]),
            'year': result.published.year,
            'arxiv_id': result.get_short_id(),
            'primary_category': result.primary_category,
            'url': result.entry_id,
            'published': result.published.strftime('%Y-%m-%d'),
            'summary': result.summary[:500] + "..." if len(result.summary) > 500 else result.summary
        }
        
        return {'result': entry_info}
        
    except Exception as e:
        return {"error": f"arXiv lookup failed: {str(e)}"}


def callback_lookup_eprint_by_id(eprint_id: str) -> Dict[str, Any]:
    """Lookup a specific IACR ePrint paper by its ID."""
    try:
        # Ensure proper format (year/number)
        if '/' not in eprint_id:
            return {"error": f"Invalid ePrint ID format: {eprint_id}. Expected format: year/number"}
        
        url = f"https://eprint.iacr.org/{eprint_id}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract title
        title_elem = soup.find('h3')
        title = title_elem.get_text().strip() if title_elem else "Unknown Title"
        
        # Extract authors
        authors_elem = soup.find('h4')
        authors = authors_elem.get_text().strip() if authors_elem else "Unknown Authors"
        
        # Try to extract BibTeX if available
        bibtex_elem = soup.find(id='bibtex')
        bibtex = bibtex_elem.get_text().strip() if bibtex_elem else None
        
        entry_info = {
            'title': title,
            'authors': authors,
            'eprint_id': eprint_id,
            'url': url,
            'bibtex': bibtex
        }
        
        return {'result': entry_info}
        
    except Exception as e:
        return {"error": f"IACR ePrint lookup failed: {str(e)}"}


def create_openai_client():
    """Create and return OpenAI client."""
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("OpenAI library not available. Install with: pip install openai")
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    return OpenAI(api_key=api_key)


def get_bibliographic_suggestions(bibtexid: str, entry_old=None) -> List[Union[DblpEntry, ArxivEntry, EprintEntry, RawBibtexEntry]]:
    """Use OpenAI with structured output to get bibliographic suggestions."""
    
    client = create_openai_client()
    
    # Prepare context - no user interaction, make educated guesses from citation key
    context = f"BibTeX ID: {bibtexid}\n"
    if entry_old:
        if 'title' in entry_old.fields:
            context += f"Current Title: {entry_old.fields['title']}\n"
        if 'author' in entry_old.persons:
            authors = ", ".join([str(author) for author in entry_old.persons['author']])
            context += f"Current Authors: {authors}\n"
        if 'year' in entry_old.fields:
            context += f"Current Year: {entry_old.fields['year']}\n"
        if 'booktitle' in entry_old.fields:
            context += f"Current Venue: {entry_old.fields['booktitle']}\n"
        if 'journal' in entry_old.fields:
            context += f"Current Journal: {entry_old.fields['journal']}\n"
        context += f"\nCurrent BibTeX entry:\n{entry_old.to_string('bibtex')}\n"
    else:
        context += "No existing entry data. Please make educated guesses based on the citation key.\n"
    
    # Tools available to the AI
    tools = [
        {
            "type": "function",
            "function": {
                "name": "callback_search",
                "description": "Search the web using Google Search via Serper API",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "callback_browse_html",
                "description": "Browse a website and return HTML content",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to browse"}
                    },
                    "required": ["url"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "callback_browse_text",
                "description": "Browse a website and return clean text content",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to browse"}
                    },
                    "required": ["url"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "callback_query_dblp",
                "description": "Query DBLP database for bibliographic entries",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search_query": {"type": "string", "description": "Search query for DBLP"},
                        "max_results": {"type": "integer", "description": "Maximum number of results", "default": 5}
                    },
                    "required": ["search_query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "callback_lookup_arxiv_by_id",
                "description": "Lookup a specific arXiv paper by its ID",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "arxiv_id": {"type": "string", "description": "arXiv ID (e.g., '2301.12345' or 'arXiv:2301.12345')"}
                    },
                    "required": ["arxiv_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "callback_lookup_eprint_by_id",
                "description": "Lookup a specific IACR ePrint paper by its ID",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "eprint_id": {"type": "string", "description": "ePrint ID in format 'year/number' (e.g., '2023/123')"}
                    },
                    "required": ["eprint_id"]
                }
            }
        }
    ]
    
    # System message with instructions
    system_message = """You are a bibliographic assistant helping to find the most appropriate bibliographic entries for academic references. 

Your task is to analyze the given bibliographic information and use the available tools to find up to 5 most pertinent entries that the user may want to add to their bibliography.

IMPORTANT PRIORITIZATION RULES:
1. For any preprint, try to find if the work has been "officially published" since the preprint's release. If so, prefer the officially published version (via DBLP) over the preprint.
2. If there is no officially published version of a preprint yet, prefer IACR ePrint or arXiv entries directly rather than DBLP entries that reference those preprint services.
3. Only resort to raw BibTeX entries if none of the specific entry types (DBLP, arXiv, IACR ePrint) can represent the reference.

If no existing entry is provided, make educated guesses based on the citation key to find relevant papers.

Use the tools to search for information systematically:
1. Start with web search to understand the citation key and find information about the work
2. Query DBLP using any discovered title and author information  
3. For arXiv papers, use the arXiv ID lookup if you can identify the ID
4. For IACR ePrint papers, use the ePrint ID lookup if you can identify the ID
5. Browse specific websites if you find promising leads

Entry types you can suggest:
- DblpEntryData: For papers in DBLP database (provide dblpid - the DBLP key)
- ArxivEntryData: For arXiv preprints (provide arxiv_id and version)
- EprintEntryData: For IACR ePrint papers (provide eprint_id in format year/number)
- RawBibtexEntryData: For papers not available in other databases (provide raw bibtex lines as list)

Return your suggestions in order of preference according to the prioritization rules."""
    
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": f"Please find the most appropriate bibliographic entries for:\n\n{context}"}
    ]
    
    print("---> Querying OpenAI for bibliographic suggestions...")
    
    # Make the API call with tools
    response = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=messages,
        tools=tools,
        response_format=BibliographicSuggestions
    )
    
    # Handle tool calls
    while response.choices[0].finish_reason == "tool_calls":
        messages.append(response.choices[0].message)
        
        for tool_call in response.choices[0].message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            print(f"---> Calling {function_name} with args: {function_args}")
            
            # Call the appropriate function
            if function_name == "callback_search":
                result = callback_search(**function_args)
            elif function_name == "callback_browse_html":
                result = callback_browse_html(**function_args)
            elif function_name == "callback_browse_text":
                result = callback_browse_text(**function_args)
            elif function_name == "callback_query_dblp":
                result = callback_query_dblp(**function_args) 
            elif function_name == "callback_lookup_arxiv_by_id":
                result = callback_lookup_arxiv_by_id(**function_args)
            elif function_name == "callback_lookup_eprint_by_id":
                result = callback_lookup_eprint_by_id(**function_args)
            else:
                result = {"error": f"Unknown function: {function_name}"}
            
            messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": function_name,
                "content": json.dumps(result)
            })
        
        # Get the next response
        response = client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=messages,
            tools=tools,
            response_format=BibliographicSuggestions
        )
    
    # Convert structured output to store entries
    if response.choices[0].finish_reason == "stop" and response.choices[0].message.parsed:
        suggestions_data = response.choices[0].message.parsed
        print(f"---> AI reasoning: {suggestions_data.reasoning}")
        
        entries = []
        for suggestion in suggestions_data.suggestions:
            try:
                if suggestion.entry_type == "dblp":
                    entry = DblpEntry(suggestion.bibtexid, suggestion.dblpid)
                elif suggestion.entry_type == "arxiv":
                    entry = ArxivEntry(suggestion.bibtexid, suggestion.arxivid, suggestion.version)
                elif suggestion.entry_type == "eprint":
                    entry = EprintEntry(suggestion.bibtexid, suggestion.eprintid)
                elif suggestion.entry_type == "raw":
                    entry = RawBibtexEntry(suggestion.bibtexid, suggestion.rawbibtex)
                else:
                    print(f"---> Unknown entry type: {suggestion.entry_type}")
                    continue
                
                entries.append(entry)
            except Exception as e:
                print(f"---> Error creating entry: {e}")
                continue
        
        return entries
    else:
        print("---> No suggestions received from AI")
        return []


def run():
    """Main function for regenbib-import-openai."""
    parser = argparse.ArgumentParser(
        description='AI-assisted bibliography import using OpenAI.')
    parser.add_argument('--bib', metavar='BIB_FILE', type=str,
                        default='references.bib', help='File name of .bib file')
    parser.add_argument('--aux', metavar='AUX_FILE', type=str,
                        default='_build/main.aux', help='File name of .aux file')
    parser.add_argument('--yaml', metavar='YAML_FILE', type=str,
                        default='references.yaml', help='File name of .yaml file')
    parser.add_argument('--laxpybteximport', action='store_true',
                        default=False, help='Disable strict mode of pybtex for .bib import')
    args = parser.parse_args()
    
    try:
        # Verify OpenAI setup
        create_openai_client()
        print("---> OpenAI client initialized successfully")
    except Exception as e:
        print(f"---> Error initializing OpenAI: {e}")
        return
    
    # Extract bibliography IDs from .aux file
    bibtexids_included = []
    with open(args.aux, 'r') as infile:
        for l in infile.readlines():
            l = l.strip()

            # BibLaTeX
            matches = re.findall(r"\\abx@aux@cite\{0\}\{(.*?)\}", l)
            assert len(matches) <= 1
            if matches:
                m = matches[0]
                if not m in bibtexids_included:
                    bibtexids_included.append(m)

            # BibTeX
            matches = re.findall(r"\\citation\{(.*?)\}", l)
            assert len(matches) <= 1
            if matches:
                for m in matches[0].split(','):
                    m = m.strip()
                    if not m in bibtexids_included:
                        bibtexids_included.append(m)

    store = Store.load_or_empty(args.yaml)

    if args.laxpybteximport:
        set_strict_mode(False)
    bibtex_entries = bibtex_dblp.database.load_from_file(args.bib)
    set_strict_mode()

    for bibtexid in bibtexids_included:
        if bibtexid in store.bibtexids:
            continue

        print(f"\n=== Importing entry: {bibtexid} ===")

        entry_old = None
        if bibtexid in bibtex_entries.entries.keys():
            entry_old = bibtex_entries.entries[bibtexid]
        else:
            for (tmp_entry_key, tmp_entry) in bibtex_entries.entries.items():
                tmp_ids = tmp_entry.fields.get('ids', '')
                if not tmp_ids:
                    tmp_ids = []
                else:
                    tmp_ids = [tmp_id.strip() for tmp_id in tmp_ids.split(',')]
                if bibtexid in tmp_ids:
                    entry_old = copy.deepcopy(tmp_entry)
                    entry_old.key = bibtexid
                    del entry_old.fields['ids']
                    break

        if entry_old:
            print(f"---> Found existing entry")

        try:
            # Get AI suggestions - now returns store entries directly
            entries = get_bibliographic_suggestions(bibtexid, entry_old)
            
            if not entries:
                print("---> No suggestions received from AI")
                continue
            
            print(f"\n---> AI found {len(entries)} suggestions:")
            for i, entry in enumerate(entries):
                entry_type = entry.__class__.__name__.replace('Entry', '').upper()
                print(f"({i+1}) [{entry_type}] {entry}")
            
            # Let user select
            choice = bibtex_dblp.io.get_user_number(
                f"---> Select suggestion [1-{len(entries)}, 0=skip]: ", 
                0, len(entries)
            )
            
            if choice == 0:
                print("---> Skipping entry")
                continue
            
            selected_entry = entries[choice - 1]
            # Update the bibtexid to match what we're importing
            selected_entry.bibtexid = bibtexid
            
            store.entries.append(selected_entry)
            store.dump(args.yaml)
            
            entry_type = selected_entry.__class__.__name__.replace('Entry', '').upper()
            print(f"---> Added {entry_type} entry for {bibtexid}")
                
        except Exception as e:
            print(f"---> Error processing {bibtexid}: {e}")
            continue

    print("\n=== Import completed ===")


if __name__ == '__main__':
    run()