#! /usr/bin/env python3

import argparse
import json
import os
import re
import copy
from typing import List, Optional, Union, Dict, Any
from dataclasses import dataclass
from pybtex.errors import set_strict_mode
import bibtex_dblp.dblp_data
import bibtex_dblp.dblp_api
import bibtex_dblp.io
import bibtex_dblp.database
import requests
from bs4 import BeautifulSoup
import arxiv
from .store import Store, DblpEntry, ArxivEntry, EprintEntry, RawBibtexEntry


@dataclass
class BibliographicSuggestion:
    """A single bibliographic suggestion with metadata."""
    title: str
    authors: str
    year: Optional[str]
    venue: Optional[str]
    entry_type: str  # 'dblp', 'arxiv', 'eprint', 'raw'
    entry_data: Dict[str, Any]  # Contains the specific data needed to create the entry
    reasoning: str  # Why this entry was suggested
    priority: int  # 1-5, where 1 is highest priority


def search_web(query: str, num_results: int = 5) -> str:
    """Search the web for information. Returns a summary of results."""
    # For now, we'll use a simple approach - in a real implementation,
    # you might want to use Google Custom Search API or similar
    try:
        # Use DuckDuckGo or similar service for basic web search
        # This is a placeholder - real implementation would need proper web search
        return f"Web search for '{query}' - This is a placeholder. In production, this would perform actual web search and return relevant results."
    except Exception as e:
        return f"Web search failed: {str(e)}"


def read_website(url: str) -> str:
    """Read content from a website URL."""
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
        
        # Limit text length to avoid token limits
        return text[:5000] + "..." if len(text) > 5000 else text
        
    except Exception as e:
        return f"Failed to read website {url}: {str(e)}"


def query_dblp(search_query: str, max_results: int = 5) -> str:
    """Query DBLP and return bibliographic information."""
    try:
        search_results = bibtex_dblp.dblp_api.search_publication(
            search_query, max_search_results=max_results)
        
        if search_results.total_matches == 0:
            return f"No DBLP results found for query: {search_query}"
        
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
        
        return json.dumps({
            'total_matches': search_results.total_matches,
            'results_shown': len(results),
            'results': results
        }, indent=2)
        
    except Exception as e:
        return f"DBLP query failed: {str(e)}"


def query_arxiv(search_query: str, max_results: int = 5) -> str:
    """Query arXiv and return bibliographic information."""
    try:
        search = arxiv.Search(
            query=search_query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance
        )
        
        results = []
        for i, result in enumerate(search.results()):
            entry_info = {
                'index': i + 1,
                'title': result.title,
                'authors': ', '.join([author.name for author in result.authors]),
                'year': result.published.year,
                'arxiv_id': result.get_short_id(),
                'primary_category': result.primary_category,
                'url': result.entry_id,
                'summary': result.summary[:500] + "..." if len(result.summary) > 500 else result.summary
            }
            results.append(entry_info)
        
        return json.dumps({
            'results_count': len(results),
            'results': results
        }, indent=2)
        
    except Exception as e:
        return f"arXiv query failed: {str(e)}"


def query_iacr_eprint(search_query: str) -> str:
    """Query IACR ePrint and return bibliographic information."""
    try:
        # IACR ePrint doesn't have a direct API, so we'll search their website
        base_url = "https://eprint.iacr.org"
        search_url = f"{base_url}/search?q={requests.utils.quote(search_query)}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for search results (this is a simplified parser)
        results = []
        result_divs = soup.find_all('div', class_='result') or soup.find_all('tr', class_='result')
        
        for i, div in enumerate(result_divs[:5]):  # Limit to 5 results
            title_elem = div.find('a') or div.find('td', class_='title')
            if title_elem:
                title = title_elem.get_text().strip()
                link = title_elem.get('href', '')
                if link and not link.startswith('http'):
                    link = base_url + link
                
                # Extract eprint ID from link
                eprint_id = ""
                if '/eprint/' in link:
                    eprint_id = link.split('/eprint/')[-1].split('/')[0]
                
                results.append({
                    'index': i + 1,
                    'title': title,
                    'eprint_id': eprint_id,
                    'url': link
                })
        
        if not results:
            return f"No IACR ePrint results found for query: {search_query}"
        
        return json.dumps({
            'results_count': len(results),
            'results': results
        }, indent=2)
        
    except Exception as e:
        return f"IACR ePrint query failed: {str(e)}"


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


def get_bibliographic_suggestions(bibtexid: str, entry_old=None) -> List[BibliographicSuggestion]:
    """Use OpenAI with structured output to get bibliographic suggestions."""
    
    client = create_openai_client()
    
    # Prepare context
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
        # Get basic info from user
        title = bibtex_dblp.io.get_user_input("---> Title [<empty>=abort]: ")
        if not title:
            return []
        context += f"Title: {title}\n"
        
        authors = bibtex_dblp.io.get_user_input("---> Authors (optional): ")
        if authors:
            context += f"Authors: {authors}\n"
        
        year = bibtex_dblp.io.get_user_input("---> Year (optional): ")
        if year:
            context += f"Year: {year}\n"
        
        venue = bibtex_dblp.io.get_user_input("---> Venue/Conference/Journal (optional): ")
        if venue:
            context += f"Venue: {venue}\n"
    
    # Tools available to the AI
    tools = [
        {
            "type": "function",
            "function": {
                "name": "search_web",
                "description": "Search the web for general information about a paper or topic",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "num_results": {"type": "integer", "description": "Number of results to return", "default": 5}
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_website",
                "description": "Read content from a specific website URL",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to read"}
                    },
                    "required": ["url"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "query_dblp",
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
                "name": "query_arxiv",
                "description": "Query arXiv preprint server for papers",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search_query": {"type": "string", "description": "Search query for arXiv"},
                        "max_results": {"type": "integer", "description": "Maximum number of results", "default": 5}
                    },
                    "required": ["search_query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "query_iacr_eprint",
                "description": "Query IACR ePrint archive for cryptography papers",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search_query": {"type": "string", "description": "Search query for IACR ePrint"}
                    },
                    "required": ["search_query"]
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

Use the tools to search for information systematically:
1. Start with DBLP queries using title and author information
2. Search arXiv if the work might be a preprint or if DBLP doesn't have good matches
3. Search IACR ePrint if the work appears to be related to cryptography
4. Use web search for additional context or to find official publication information
5. Read specific websites if you find promising leads

After gathering information, provide your recommendations as a structured response with exactly the information needed to create the bibliography entries."""
    
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": f"Please find the most appropriate bibliographic entries for:\n\n{context}"}
    ]
    
    print("---> Querying OpenAI for bibliographic suggestions...")
    
    # Make the API call with tools
    response = client.chat.completions.create(
        model="gpt-4o",  # Use GPT-4 for better tool usage
        messages=messages,
        tools=tools,
        tool_choice="auto",
        max_tokens=4000,
        temperature=0.3
    )
    
    # Handle tool calls
    while response.choices[0].message.tool_calls:
        messages.append(response.choices[0].message)
        
        for tool_call in response.choices[0].message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            print(f"---> Calling {function_name} with args: {function_args}")
            
            # Call the appropriate function
            if function_name == "search_web":
                result = search_web(**function_args)
            elif function_name == "read_website":
                result = read_website(**function_args)
            elif function_name == "query_dblp":
                result = query_dblp(**function_args)
            elif function_name == "query_arxiv":
                result = query_arxiv(**function_args)
            elif function_name == "query_iacr_eprint":
                result = query_iacr_eprint(**function_args)
            else:
                result = f"Unknown function: {function_name}"
            
            messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": function_name,
                "content": result
            })
        
        # Get the next response
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=4000,
            temperature=0.3
        )
    
    # Now ask for structured recommendations
    final_prompt = """Based on your research, please provide up to 5 bibliographic suggestions in the following JSON format:

{
  "suggestions": [
    {
      "title": "Paper title",
      "authors": "Author1, Author2",
      "year": "2023",
      "venue": "Conference/Journal name",
      "entry_type": "dblp|arxiv|eprint|raw",
      "entry_data": {
        // Specific data needed to create the entry:
        // For "dblp": {"dblp_key": "key"}
        // For "arxiv": {"arxiv_id": "2301.12345", "version": "v1"}
        // For "eprint": {"eprint_id": "2023/123"}
        // For "raw": {"bibtex": "raw bibtex string"}
      },
      "reasoning": "Why this entry was selected",
      "priority": 1
    }
  ]
}

Ensure entries are ranked by priority (1=highest, 5=lowest) according to the prioritization rules given earlier."""
    
    messages.append({"role": "user", "content": final_prompt})
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=2000,
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    
    try:
        result_json = json.loads(response.choices[0].message.content)
        suggestions = []
        
        for item in result_json.get("suggestions", []):
            suggestion = BibliographicSuggestion(
                title=item.get("title", ""),
                authors=item.get("authors", ""),
                year=item.get("year"),
                venue=item.get("venue"),
                entry_type=item.get("entry_type", "raw"),
                entry_data=item.get("entry_data", {}),
                reasoning=item.get("reasoning", ""),
                priority=item.get("priority", 5)
            )
            suggestions.append(suggestion)
        
        return suggestions
        
    except Exception as e:
        print(f"---> Error parsing AI response: {e}")
        return []


def create_entry_from_suggestion(bibtexid: str, suggestion: BibliographicSuggestion):
    """Create a Store entry from a BibliographicSuggestion."""
    try:
        if suggestion.entry_type == "dblp":
            dblp_key = suggestion.entry_data.get("dblp_key")
            if not dblp_key:
                raise ValueError("Missing dblp_key for DBLP entry")
            return DblpEntry(bibtexid, dblp_key)
        
        elif suggestion.entry_type == "arxiv":
            arxiv_id = suggestion.entry_data.get("arxiv_id")
            version = suggestion.entry_data.get("version", "")
            if not arxiv_id:
                raise ValueError("Missing arxiv_id for arXiv entry")
            entry = ArxivEntry(bibtexid, arxiv_id, version)
            return entry
        
        elif suggestion.entry_type == "eprint":
            eprint_id = suggestion.entry_data.get("eprint_id")
            if not eprint_id:
                raise ValueError("Missing eprint_id for ePrint entry")
            entry = EprintEntry(bibtexid, eprint_id)
            return entry
        
        elif suggestion.entry_type == "raw":
            bibtex_content = suggestion.entry_data.get("bibtex")
            if not bibtex_content:
                raise ValueError("Missing bibtex content for raw entry")
            # Parse the raw bibtex to create RawBibtexEntry
            rawbibtex_lines = bibtex_content.split('\n')
            return RawBibtexEntry(bibtexid, rawbibtex_lines)
        
        else:
            raise ValueError(f"Unknown entry type: {suggestion.entry_type}")
    
    except Exception as e:
        print(f"---> Error creating entry from suggestion: {e}")
        return None


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
            print(f"---> Found existing entry: {entry_old}")

        try:
            # Get AI suggestions
            suggestions = get_bibliographic_suggestions(bibtexid, entry_old)
            
            if not suggestions:
                print("---> No suggestions received from AI")
                continue
            
            print(f"\n---> AI found {len(suggestions)} suggestions:")
            for i, suggestion in enumerate(suggestions):
                print(f"({i+1}) [{suggestion.entry_type.upper()}] {suggestion.title}")
                print(f"    Authors: {suggestion.authors}")
                if suggestion.year:
                    print(f"    Year: {suggestion.year}")
                if suggestion.venue:
                    print(f"    Venue: {suggestion.venue}")
                print(f"    Priority: {suggestion.priority}")
                print(f"    Reasoning: {suggestion.reasoning}")
                print()
            
            # Let user select
            choice = bibtex_dblp.io.get_user_number(
                f"---> Select suggestion [1-{len(suggestions)}, 0=skip]: ", 
                0, len(suggestions)
            )
            
            if choice == 0:
                print("---> Skipping entry")
                continue
            
            selected_suggestion = suggestions[choice - 1]
            entry = create_entry_from_suggestion(bibtexid, selected_suggestion)
            
            if entry:
                store.entries.append(entry)
                store.dump(args.yaml)
                print(f"---> Added {selected_suggestion.entry_type.upper()} entry for {bibtexid}")
            else:
                print("---> Failed to create entry from suggestion")
                
        except Exception as e:
            print(f"---> Error processing {bibtexid}: {e}")
            continue

    print("\n=== Import completed ===")


if __name__ == '__main__':
    run()