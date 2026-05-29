import warnings
from typing import List, Optional
from dataclasses import dataclass
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


def _get_parser():
    try:
        import lxml  # noqa: F401
        return "lxml"
    except ImportError:
        return "html.parser"


@dataclass
class RawEntry:
    year: int
    year_title: str
    date_raw: str
    content_html: str
    source_file: str
    entry_index: int
    volume: int = 0


def parse_html_file(html_content: str, year: int, year_title: str,
                    source_file: str, volume: int) -> List[RawEntry]:
    soup = BeautifulSoup(html_content, _get_parser())
    body = soup.find('body')
    if not body:
        return []

    content_paras = _resolve_paragraphs(body)
    if not content_paras:
        return []

    entries: List[RawEntry] = []
    entry_index = 0
    current_date: Optional[str] = None
    current_parts: List[str] = []

    def flush():
        nonlocal entry_index
        if current_date and current_parts:
            entries.append(RawEntry(
                year=year, year_title=year_title,
                date_raw=current_date,
                content_html=' '.join(current_parts),
                source_file=source_file,
                entry_index=entry_index, volume=volume,
            ))
            entry_index += 1

    for para in content_paras:
        bold = para.find('span', class_='kindle-cn-bold')
        if bold:
            flush()
            current_date = bold.get_text(strip=True)
            bold.extract()
            current_parts = [para.get_text(separator='', strip=False)]
        elif current_date:
            text = para.get_text(separator='', strip=False).strip()
            if text:
                current_parts.append(text)

    flush()
    return entries


def _resolve_paragraphs(body):
    chapter_div = body.find('div', class_='chapter')
    if chapter_div:
        paras = chapter_div.find_all('p', class_='calibre5')
        if paras:
            return paras

    return body.find_all('p', class_='calibre5')
