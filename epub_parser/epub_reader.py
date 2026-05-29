import zipfile
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class ChronFile:
    year: int
    year_title: str
    volume: int
    source_files: List[str]
    html_content: str = ""


@dataclass
class EPUBSnapshot:
    epub_path: str
    meta_files: List[str] = field(default_factory=list)
    chron_groups: List[ChronFile] = field(default_factory=list)
    total_html_files: int = 0


_VOLUME_MAP = {
    (0, 40): 1, (41, 52): 2, (53, 63): 3,
    (64, 72): 4, (73, 80): 5, (81, 88): 6,
    (89, 95): 7, (96, 105): 8, (106, 121): 9,
}

_META_KEYWORDS = [
    '出版说明', '目录', '版权', '编委会', '封面', '书名',
    '后记', '修订后记', '参加本卷编写', 'Table of Contents', 'Unknown',
]


def _volume_for(part_num: int) -> int:
    for (lo, hi), vol in _VOLUME_MAP.items():
        if lo <= part_num <= hi:
            return vol
    return 0


def _is_meta(part_num: int, html: str, title: Optional[str]) -> bool:
    if part_num <= 5:
        return True
    if part_num in (41, 53, 64, 73, 81, 89, 96, 106):
        return True
    if title and any(kw in title for kw in _META_KEYWORDS):
        return True
    h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
    if h1_match:
        h1_text = re.sub(r'<[^>]+>', '', h1_match.group(1)).strip()
        if any(kw in h1_text for kw in _META_KEYWORDS):
            return True
    body_text = re.sub(r'<[^>]+>', '', html).strip()
    return len(body_text) < 50


def _extract_year(text: str) -> Optional[int]:
    clean = re.sub(r'<[^>]+>', '', text).replace('\u3000', ' ').strip()
    m = re.match(r'(\d{4})', clean)
    return int(m.group(1)) if m else None


def read_epub_structure(epub_path: str) -> EPUBSnapshot:
    z = zipfile.ZipFile(epub_path)
    all_html = sorted(f for f in z.namelist() if f.endswith('.html'))

    split_groups: Dict[str, List[str]] = {}
    standalone: List[str] = []
    meta_files: List[str] = []

    for fname in all_html:
        m = re.match(r'text/part(\d{4})(?:_split_(\d{3}))?\.html', fname)
        if not m:
            continue
        part_base, split_idx = m.group(1), m.group(2)
        if split_idx is not None:
            split_groups.setdefault(part_base, []).append(fname)
        else:
            standalone.append(fname)

    chron_groups: List[ChronFile] = []

    def read_file(fname: str) -> str:
        return z.read(fname).decode('utf-8', errors='replace')

    for fname in standalone:
        m2 = re.match(r'text/part(\d{4})\.html', fname)
        if not m2:
            continue
        part_num = int(m2.group(1))
        html = read_file(fname)
        title_match = re.search(r'<title>(.*?)</title>', html)
        title = title_match.group(1) if title_match else None

        if _is_meta(part_num, html, title):
            meta_files.append(fname)
            continue

        h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
        h1_text = ""
        year = None
        if h1_match:
            h1_text = re.sub(r'<[^>]+>', '', h1_match.group(1)).strip()
            year = _extract_year(h1_text)

        if year is not None:
            chron_groups.append(ChronFile(
                year=year, year_title=h1_text,
                volume=_volume_for(part_num),
                source_files=[fname], html_content=html,
            ))

    for part_base in sorted(split_groups):
        file_list = sorted(split_groups[part_base])
        part_num = int(part_base)

        first_html = read_file(file_list[0])
        h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', first_html, re.DOTALL)
        h1_text = ""
        year = None
        if h1_match:
            h1_text = re.sub(r'<[^>]+>', '', h1_match.group(1)).strip()
            year = _extract_year(h1_text)
        if year is None:
            title_match = re.search(r'<title>(.*?)</title>', first_html)
            if title_match:
                year = _extract_year(title_match.group(1))
                h1_text = title_match.group(1)
        if year is None:
            continue

        merged = ""
        for fname in file_list:
            merged += read_file(fname) + "\n"
        chron_groups.append(ChronFile(
            year=year, year_title=h1_text,
            volume=_volume_for(part_num),
            source_files=file_list, html_content=merged,
        ))

    z.close()
    chron_groups.sort(key=lambda c: c.year)
    return EPUBSnapshot(
        epub_path=epub_path,
        meta_files=sorted(set(meta_files)),
        chron_groups=chron_groups,
        total_html_files=len(all_html),
    )
