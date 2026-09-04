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

def extract_table_fields(content: str) -> dict:
    """Extracts deadline, amount, criteria, and requirements from text for table display."""
    deadline = "Not Specified"
    amount = "Varies / Check Link"
    criteria = "General Student Eligibility"
    requirements = "Standard Application"

    # Match common deadline patterns (e.g., May 15, 2026 or 10/30/26)
    date_match = re.search(r'(?:Deadline:?|by)\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{2,4})', content, re.IGNORECASE)
    if date_match:
        deadline = date_match.group(1)

    # Match amount patterns (e.g., $10,000 or 2,500 - 20,000)
    amount_match = re.search(r'(?:Amount:?|\$)\s*([\d,]+(?:\s*-\s*\$[\d,]+)?)', content, re.IGNORECASE)
    if amount_match:
        amount = "$" + amount_match.group(1).replace("$", "")

    # Extract snippet parts for criteria/requirements
    if len(content) > 50:
        criteria = content[:150] + "..."
        requirements = content[150:300] + "..." if len(content) > 150 else "See official portal for documents."

    return {
        "deadline": deadline,
        "amount": amount,
        "criteria": criteria,
        "requirements": requirements
    }

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
            
            if len(cleaned) < 30:
                continue
                
            fields = extract_table_fields(cleaned)
            
            structured_results.append({
                "title": title,
                "url": url,
                "deadline": fields["deadline"],
                "amount": fields["amount"],
                "criteria": fields["criteria"],
                "requirements": fields["requirements"],
                "content": cleaned
            })
            
        structured_results.sort(
            key=lambda result: is_official_source(result.get("url", "")),
            reverse=True
        )
        
        return structured_results if structured_results else [{
            "title": "No Clear Results Found",
            "url": "",
            "content": "Try searching with more specific keywords."
        }]
    except Exception as e:
        return [{
            "title": "Search Failed",
            "url": "",
            "content": f"Web search execution error: {str(e)}"
        }]