# Design Spec: 毛泽东年谱 EPUB → JSONL Time-Series Parser

**Date**: 2026-05-29
**Status**: Approved
**Scope**: Parse `毛泽东年谱.epub` into structured JSONL time-series data using regex-enhanced HTML parsing.

---

## 1. Goal

Convert the 9-volume, 1893-1976 chronological biography (毛泽东年谱) from EPUB format into a single JSONL file (`data/mao-chronology.jsonl`) with complete date normalization and clean text extraction. Primary use case: full-text semantic search with time-series query support.

## 2. Source Data

- **File**: `毛泽东年谱.epub` (15.3 MB compressed, 159 HTML files)
- **Structure**: 9 physical volumes bundled in one EPUB:
  - 《毛泽东年谱（1893—1949）》上/中/下卷 (Vol 1-3)
  - 《毛泽东年谱（1949—1976）》第一至第六卷 (Vol 4-9)
- **Span**: 1893-1976 (83 years)
- **Entries**: ~16,000 date-anchored events
- **HTML patterns**: Two structural variants (Vol 1 vs Vol 2+), five footnote styles

## 3. Architecture

```
毛年谱.epub (ZIP)
    │
    ├─ Phase 1: EPUB Extraction
    │   └─ zipfile → list HTML files, filter META, group splits
    │
    ├─ Phase 2: HTML Parsing (per file)
    │   └─ BeautifulSoup → extract h1 (year), p.calibre5 (content), span.kindle-cn-bold (dates)
    │
    ├─ Phase 3: Date Resolution (state machine)
    │   └─ Regex → normalize date_raw → year/month/day/season
    │   └─ State machine → resolve 同日/同月/同旬/同季
    │
    ├─ Phase 4: Clean Text
    │   └─ Strip <sup> footnote markers, <a> links, HTML tags
    │
    └─ Phase 5: Output
        └─ JSONL → data/mao-chronology.jsonl
        └─ Gotchas → gotchas.md
```

### Components

| Component | File | Responsibility |
|-----------|------|----------------|
| EPUB reader | `epub_reader.py` | Unzip EPUB, enumerate HTML files, classify META vs CHRON, group split files |
| HTML parser | `html_parser.py` | BS4 parse each file, extract h1 + bold spans + p.calibre5 paragraphs |
| Date resolver | `date_resolver.py` | Regex patterns for all date formats, state machine for relative dates |
| Text cleaner | `text_cleaner.py` | Remove footnote markers, HTML tags, page anchors, normalize whitespace |
| JSONL writer | `jsonl_writer.py` | Serialize to JSONL with idempotent dedup |
| Main pipeline | `parse.py` | Orchestrate phases, log errors, track progress |

## 4. JSONL Schema

```json
{
  "id": "1918-04-14-004",
  "year": 1918,
  "year_title": "1918年 二十五岁",

  "date_raw": "4月14日",
  "date_display": "1918年4月14日",
  "date_type": "full",
  "month": 4,
  "day": 14,
  "season": null,
  "ten_day_period": null,
  "is_same_day": false,
  "is_approximate": false,

  "date_end": null,
  "date_list": null,
  "fuzzy_modifier": null,

  "content": "出席在长沙岳麓山刘家台子蔡和森家召开的新民学会成立大会...",
  "content_length": 156,

  "source_file": "text/part0021.html",
  "volume": 1,
  "entry_index": 4,

  "tags": []
}
```

### Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | `{year}-{date_raw_slug}-{entry_index}` |
| `year` | int | Year from h1 heading |
| `year_title` | string | Raw h1 text (e.g. `"1904年 十一岁"`) |
| `date_raw` | string | Original bold-span text (`"同日"`, `"4月14日"`, `"春"`) |
| `date_display` | string | Human-readable resolved date |
| `date_type` | enum | `full` `month` `season` `period` `range` `list` `fuzzy` `relative` `year_only` |
| `month` | int\|null | 1–12, null for non-specific |
| `day` | int\|null | 1–31, null for non-specific |
| `season` | string\|null | `"春"` `"夏"` `"秋"` `"冬"` |
| `ten_day_period` | string\|null | `"上旬"` `"中旬"` `"下旬"` `"初"` `"底"` |
| `is_same_day` | bool | true when `date_raw == "同日"` |
| `is_approximate` | bool | true for `前后` `左右` `或` etc. |
| `date_end` | object\|null | `{year, month, day}` for ranges |
| `date_list` | array\|null | `["1918-11-29", "1918-11-30"]` for comma-separated dates |
| `fuzzy_modifier` | string\|null | `"前后"` `"或"` `"左右"` |
| `content` | string | Clean text: no HTML, footnotes, or page markers |
| `content_length` | int | Character count |
| `source_file` | string | Source HTML path(s) in EPUB |
| `volume` | int\|null | Physical volume number (1-9) |
| `entry_index` | int | Sequential position within source |
| `tags` | string[] | Reserved for future NLP extraction |

## 5. Date Resolution Rules

### 5.1 Regex Patterns (in priority order)

| Pattern | Regex | Example | Output |
|---------|-------|---------|--------|
| Relative | `同日` `同月` `同旬` `同季` | `同日` | Copy prev date, set `is_same_day` |
| Full date | `(\d{1,2})月(\d{1,2})日` | `4月14日` | month=4, day=14 |
| Month-only | `(\d{1,2})月` | `6月` | month=6, day=null |
| Period | `(\d{1,2})月(上旬\|中旬\|下旬)` | `6月下旬` | month=6, ten_day_period=下旬 |
| Boundary | `(\d{1,2})月(初\|底)` | `7月初` | month=7, ten_day_period=初 |
| Season | `(春\|夏\|秋\|冬)` | `秋` | season=秋 |
| Year-marker | `本年` | `本年` | year=file_year, date_type=year_only |

### 5.2 Date Range Patterns

| Pattern | Example | Handling |
|---------|---------|----------|
| Same-month range | `1月11日—22日` | Start=1/11, End=1/22 |
| Cross-month range | `2月27日—3月1日` | Start=2/27, End=3/1 |
| Comma list | `11月29日、30日` | date_list=[11/29, 11/30] |
| Dash variants | `—` (U+2014) or `一` (U+4E00) | Both treated as range separator |
| Fuzzy | `8月13日或14日` | set is_approximate=true |

### 5.3 State Machine for Relative Dates

```
prev_date = None
for each entry:
    if date_raw in ('同日', '同月', '同旬', '同季'):
        copy prev_date resolution
        mark accordingly
    else:
        resolve date_raw
        update prev_date
```

## 6. Text Cleaning Rules

1. **Remove footnote markers**: All `<sup>` and `<a>` tags containing `[N]`, `〔N〕`, `(N)`
2. **Remove page anchors**: `<a id="pageN">` spans
3. **Strip HTML tags**: All remaining HTML, preserve text content
4. **Normalize whitespace**: Collapse multiple spaces, trim
5. **Handle cross-file splits**: Concatenate p.calibre5 paragraphs across split segments

## 7. File Classification

### Files to SKIP (40 files)

Front matter per volume: cover pages, title pages, TOC, publication notes, editorial boards, afterwords.

### Files to PARSE (82+ files)

Chronological year entries identified by `h1` matching `\d{4}年`.

### Split File Groups (17 groups)

Group `part{NNNN}_split_{SSS}.html` by base number. Merge all non-final segments (those with date entries). Skip final segment (footnotes-only, 0 date spans).

## 8. Gotchas (Documented in gotchas.md)

Expected edge cases to document during implementation:

1. **`一` vs `—`**: CJK numeral one used as range dash — regex must handle both
2. **Empty split tails**: Final split segment has 0 date spans (footnotes only)
3. **CSS class variability**: `kindle-cn-heading` vs `kindle-cn-heading1` across volumes
4. **Container divergence**: `div.chapter` (Vol 1) vs `div.calibre11` (Vol 2+)
5. **Footnote system evolution**: 5 distinct styles over 83 years
6. **Season-year compounds**: `1937年冬` where year prefixes season
7. **Triple comma lists**: `6月3日、8日、25日` — non-consecutive, same month
8. **Page breaks mid-sentence**: Content split across HTML files at arbitrary byte boundaries
9. **Non-standard ten-day**: `3月上中旬`, `10月中下旬` — blends of two periods
10. **Encoding**: Full-width space `\u3000` used as separator

## 9. Dependencies

- Python 3.10+
- `beautifulsoup4` — HTML parsing
- `lxml` — fast HTML parser backend

## 10. Output

```
data/
└── mao-chronology.jsonl    (~16,000 lines, ~32 MB)

gotchas.md                   (parsing edge cases discovered during implementation)
```

## 11. Non-Goals

- Person/location/organization extraction (NLP, future phase)
- Semantic tagging (future phase)
- Cross-referencing with external sources
- Web UI or search interface
- Footnote content extraction (markers only are stripped; definitions discarded)
