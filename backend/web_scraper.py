import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def fetch_page_content(url: str, timeout: int = 10) -> str:
    """
    Fetches a web page and returns its cleaned, readable text content.
    Returns an error message string (not an exception) on failure, since
    callers in tools.py check for specific error phrases in the return value.
    """
    if not url:
        return "Error scraping page content: no URL provided."

    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return f"Failed to retrieve page content: {str(e)}"

    try:
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove non-content elements
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        text = soup.get_text(separator=" ")
        text = " ".join(text.split())  # collapse whitespace
        return text if text else "Error scraping page content: no readable text found."
    except Exception as e:
        return f"Error scraping page content: {str(e)}"