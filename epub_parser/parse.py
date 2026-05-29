#!/usr/bin/env python3
"""
毛泽东年谱 EPUB → JSONL 时序数据库解析器

Usage:
    python parse.py
    python parse.py --epub 毛泽东年谱.epub --output data/mao-chronology.jsonl
"""

import json
import os
import sys
from typing import List, Dict, Any

from epub_reader import read_epub_structure, ChronFile
from html_parser import parse_html_file, RawEntry
from date_resolver import resolve_date
from text_cleaner import clean_content


def parse_chronology(epub_path: str) -> List[Dict[str, Any]]:
    snapshot = read_epub_structure(epub_path)
    all_entries: List[Dict[str, Any]] = []
    prev_resolved = None
    global_seq = 0

    for cf in snapshot.chron_groups:
        raw_entries = parse_html_file(
            cf.html_content, cf.year, cf.year_title,
            cf.source_files[0], cf.volume,
        )

        for raw in raw_entries:
            resolved = resolve_date(
                raw.date_raw, cf.year, prev_resolved,
            )
            clean_text = clean_content(raw.content_html)

            global_seq += 1
            entry = {
                "id": f"{cf.year}-{_slug(raw.date_raw)}-{global_seq:05d}",
                "year": cf.year,
                "year_title": cf.year_title,
                "date_raw": raw.date_raw,
                "date_display": resolved.get("date_display", f"{cf.year}年"),
                "date_type": resolved.get("date_type", "full"),
                "month": resolved.get("month"),
                "day": resolved.get("day"),
                "season": resolved.get("season"),
                "ten_day_period": resolved.get("ten_day_period"),
                "is_same_day": resolved.get("is_same_day", False),
                "is_approximate": resolved.get("is_approximate", False),
                "date_end": resolved.get("date_end"),
                "date_list": resolved.get("date_list"),
                "fuzzy_modifier": resolved.get("fuzzy_modifier"),
                "content": clean_text,
                "content_length": len(clean_text),
                "source_file": raw.source_file,
                "volume": raw.volume,
                "entry_index": raw.entry_index,
                "tags": [],
            }

            all_entries.append(entry)
            prev_resolved = resolved

    return all_entries


def _slug(text: str) -> str:
    return text.replace("日", "").replace("月", "-").replace(" ", "")


def write_jsonl(entries: List[Dict[str, Any]], output_path: str):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def main():
    epub_path = sys.argv[1] if len(sys.argv) > 1 else "../毛泽东年谱.epub"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "../data/mao-chronology.jsonl"

    if not os.path.exists(epub_path):
        print(f"Error: EPUB file not found: {epub_path}")
        sys.exit(1)

    print(f"Parsing: {epub_path}")
    print(f"Output: {output_path}")

    entries = parse_chronology(epub_path)

    write_jsonl(entries, output_path)

    total = len(entries)
    full_dates = sum(1 for e in entries if e["date_type"] == "full")
    relative = sum(1 for e in entries if e["date_type"] == "relative")
    seasons = sum(1 for e in entries if e["date_type"] == "season")
    ranges = sum(1 for e in entries if e["date_type"] == "range")
    years_span = f"{entries[0]['year']}-{entries[-1]['year']}" if entries else "none"

    print(f"\nDone. {total} entries ({years_span})")
    print(f"  Full dates: {full_dates}")
    print(f"  Relative (同日 etc.): {relative}")
    print(f"  Seasons: {seasons}")
    print(f"  Ranges: {ranges}")
    print(f"  Other: {total - full_dates - relative - seasons - ranges}")


if __name__ == "__main__":
    main()
