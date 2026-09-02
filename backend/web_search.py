python -c "
code = '''import os
import re
from urllib.parse import urlparse
from tavily import TavilyClient

OFFICIAL_DOMAINS = [
    \"hec.gov.pk\",
    \"usefp.org\",
    \"cscuk.fcdo.gov.uk\",
    \"peef.org.pk\",
    \"stipendiumhungaricum.hu\",
    \"daad.de\",
    \"turkiyeburslari.gov.tr\"
]

def get_tavily_client():
    api_key = os.getenv(\"TAVILY_API_KEY\")
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
        return \"\"
    text = re.sub(r'd=[\'\\"].*?[\'\"]', '', text)
    text = re.sub(r'fill=[\'\\"].*?[\'\"]', '', text)
    text = re.sub(r'clip-rule=[\'\\"].*?[\'\"]', '', text)
    text = re.sub(r'class=[\'\\"].*?[\'\"]', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[\[\]{}|\\^~]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def search_web(query: str) -> list:
    client = get_tavily_client()
    if not client:
        return [{
            \"title\": \"API Key Missing\",
            \"url\": \"\",
            \"content\": \"TAVILY_API_KEY environment variable is not set.\"
        }]

    try:
        response = client.search(
            query=query,
            search_depth=\"advanced\",
            max_results=10
        )
        results = response.get(\"results\", [])
        for res in results:
            if \"content\" in res:
                res[\"content\"] = clean_snippet(res[\"content\"])
        results.sort(
            key=lambda result: is_official_source(result.get(\"url\", \"\")),
            reverse=True
        )
        return results
    except Exception as e:
        return [{
            \"title\": \"Search Failed\",
            \"url\": \"\",
            \"content\": f\"Web search execution error: {str(e)}\"
        }]
'''
with open('backend/web_search.py', 'w', encoding='utf-8') as f:
    f.write(code)
"