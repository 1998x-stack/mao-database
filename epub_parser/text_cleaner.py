"""
Text cleaner module for 毛泽东年谱.epub

Handles:
- Removing footnote markers (all 5 styles)
- Removing page anchors
- Stripping HTML tags
- Normalizing whitespace
- Cleaning CJK fullwidth spaces
"""

import re
import warnings
from typing import Optional
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


def _get_parser():
    try:
        import lxml  # noqa: F401
        return "lxml"
    except ImportError:
        return "html.parser"


def clean_content(html_content: str) -> str:
    soup = BeautifulSoup(html_content, _get_parser())

    _remove_footnotes(soup)

    for anchor in soup.find_all('a', id=re.compile(r'^page\d+')):
        anchor.decompose()

    text = soup.get_text(separator='')

    text = _strip_plain_footnotes(text)
    text = _normalize_whitespace(text)

    return text.strip()


def _strip_plain_footnotes(text: str) -> str:
    text = re.sub(r'〔\d+〕', '', text)
    text = re.sub(r'\[\d+\]', '', text)
    text = re.sub(r'（\d+）', '', text)
    text = re.sub(r'\(\d+\)', '', text)
    return text


def _remove_footnotes(soup: BeautifulSoup):
    footnote_id_patterns = [
        re.compile(r'^fn\d+$'),           # fn1, fn2, ...
        re.compile(r'^fn_\d+$'),          # fn_1, fn_2, ...
        re.compile(r'^ch\d+$'),           # ch1, ch2, ...
        re.compile(r'^ch\d+-back$'),      # ch1-back, ch2-back, ...
        re.compile(r'^ft\d+$'),           # ft1, ft2, ...
    ]

    def is_footnote_id(id_val: Optional[str]) -> bool:
        if not id_val:
            return False
        return any(pat.match(id_val) for pat in footnote_id_patterns)

    # Find all <sup> tags (they always contain footnote markers)
    for sup in soup.find_all('sup'):
        sup_text = sup.get_text(strip=True)
        if _is_footnote_marker(sup_text):
            sup.decompose()

    # Find footnote <a> tags by ID pattern
    for a_tag in soup.find_all('a'):
        a_id = a_tag.get('id', '') or ''
        if is_footnote_id(a_id):
            a_tag.decompose()

    # Also find <a> tags with href pointing to footnote IDs
    for a_tag in soup.find_all('a', href=True):
        href = a_tag.get('href', '')
        if re.search(r'#(?:fn|ch|ft)\d+', href):
            a_tag.decompose()


def _is_footnote_marker(text: str) -> bool:
    """Check if text is a footnote marker: [1], 〔2〕, (3), etc."""
    text = text.strip()
    if not text:
        return False

    # Square brackets: [1], [23]
    if re.match(r'^\[\d+\]$', text):
        return True

    # Corner brackets: 〔1〕, 〔23〕
    if re.match(r'^〔\d+〕$', text):
        return True

    # Parentheses: (1), (23)
    if re.match(r'^\(\d+\)$', text):
        return True

    return False


def _normalize_whitespace(text: str) -> str:
    """Normalize whitespace in CJK text."""
    # Remove zero-width spaces
    text = text.replace('\u200b', '')

    # Replace fullwidth spaces with nothing (they're decorative separators)
    text = text.replace('\u3000', '  ')

    # Collapse multiple spaces
    text = re.sub(r' {3,}', '  ', text)
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'[ \t]+\n', '\n', text)

    return text.strip()


def strip_html_tags(html: str) -> str:
    """Simple regex-based HTML tag stripping (fallback for non-BS4 contexts)."""
    # Remove scripts and styles
    clean = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL)
    # Remove HTML comments
    clean = re.sub(r'<!--.*?-->', '', clean, flags=re.DOTALL)
    # Remove tags
    clean = re.sub(r'<[^>]+>', '', clean)
    # Decode HTML entities
    clean = clean.replace('&nbsp;', ' ')
    clean = clean.replace('&amp;', '&')
    clean = clean.replace('&lt;', '<')
    clean = clean.replace('&gt;', '>')
    return clean
