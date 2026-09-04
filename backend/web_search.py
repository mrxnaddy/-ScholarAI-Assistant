import os
import re
from urllib.parse import urlparse
from tavily import TavilyClient

OFFICIAL_DOMAINS = [
    "hec.gov.pk",
    "usefp.org",
    "cscuk.fcdo.gov.pk",
    "peef.org.pk",
    "stipendiumhungaricum.hu",
    "daad.de",
    "turkiyeburslari.gov.tr"
]

def get_tavily_client():
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return None
    return TavilyClient(api_key=api_key)

def is_official_source(url: str) -> bool:
    if not url:
        return False
    try:
        parsed_url = urlparse(url.lower())
        hostname = parsed_url.netloc or parsed_url.path
        return any(domain in hostname for domain in OFFICIAL_DOMAINS)
    except Exception:
        return False

def clean_snippet(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'd=[\'"].*?[\'"]', '', text)
    text = re.sub(r'fill=[\'"].*?[\'"]', '', text)
    text = re.sub(r'clip-rule=[\'"].*?[\'"]', '', text)
    text = re.sub(r'class=[\'"].*?[\'"]', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[\[\]{}|\\^~]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    
    # Extra filtering to remove menu/navigation junk words
    junk_patterns = [
        r'Scholarships By.*?Browse Scholarships',
        r'Browse Scholarships',
        r'Deadline In.*?(?=Scholarships|\Z)',
        r'Fastweb',
        r'Share \s*\* \s*✏️ \s*📂'
    ]
    for pattern in junk_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
    return text.strip()

def search_web(query: str) -> list:
    client = get_tavily_client()
    if not client:
        return [{
            "title": "API Key Missing",
            "url": "",
            "content": "TAVILY_API_KEY environment variable is not set."
        }]

    try:
        response = client.search(
            query=query,
            search_depth="advanced",
            max_results=8
        )
        results = response.get("results", [])
        
        structured_results = []
        for res in results:
            title = res.get("title", "Untitled Opportunity")
            url = res.get("url", "#")
            raw_content = res.get("content", "")
            cleaned = clean_snippet(raw_content)
            
            # Skip empty or heavily corrupted snippets
            if len(cleaned) < 30:
                continue
                
            structured_results.append({
                "title": title,
                "url": url,
                "content": cleaned[:400] + "..." if len(cleaned) > 400 else cleaned
            })
            
        structured_results.sort(
            key=lambda result: is_official_source(result.get("url", "")),
            reverse=True
        )
        
        return structured_results if structured_results else [{
            "title": "No Clear Results Found",
            "url": "",
            "content": "Try searching with more specific keywords like 'HEC undergraduate scholarships' or 'BSCS scholarships Pakistan'."
        }]
    except Exception as e:
        return [{
            "title": "Search Failed",
            "url": "",
            "content": f"Web search execution error: {str(e)}"
        }]