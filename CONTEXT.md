# CONTEXT.md — 毛泽东年谱数据库

Domain glossary for the Mao Chronology Database project. This document defines the canonical terms used when discussing the data model, parsing, and output.

---

## Domain Terms

### Source Material

| Term | Definition |
|------|------------|
| **年谱 (Chronology)** | A year-by-year, day-by-day biographical record of Mao Zedong's life (1893-1976), published by 中共中央文献研究室 |
| **条目 (Entry)** | A single date-anchored event record in the chronology. Each entry has a date marker and descriptive text |
| **日期标记 (Date Marker)** | Bold text inside `<span class="kindle-cn-bold">` indicating the event date (e.g. `4月14日`, `同日`, `春`) |
| **卷 (Volume)** | Physical book volume. The EPUB bundles 9 volumes (3 for 1893-1949, 6 for 1949-1976) |
| **分卷文件 (Split File)** | When a year's content exceeds the EPUB tool's file size limit, it's split into `partNNNN_split_SSS.html` segments |

### Date System

| Term | Definition |
|------|------------|
| **完整日期 (Full Date)** | Month + day specified: `4月14日` |
| **季节标记 (Season Marker)** | Seasonal label when exact date unknown: `春` `夏` `秋` `冬` |
| **旬标记 (Ten-Day Period)** | Approximate within-month period: `上旬` (1st-10th), `中旬` (11th-20th), `下旬` (21st-end) |
| **月初/月底 (Month Boundary)** | `初` = early in month, `底` = end of month |
| **同日 (Same Day)** | Continuation marker — this entry shares the previous entry's date. Most frequent marker (5,657 occurrences) |
| **同月 (Same Month)** | Entry shares the previous entry's month |
| **同旬 (Same Period)** | Entry shares the previous entry's ten-day period |
| **日期范围 (Date Range)** | Event spanning multiple days/months, separated by `—` (em-dash) or `一` (CJK one) |
| **日期列表 (Date List)** | Multiple dates for one event, separated by `、` |
| **模糊日期 (Fuzzy Date)** | Date with uncertainty markers: `前后`, `左右`, `或` |

### Data Model

| Term | Definition |
|------|------------|
| **date_raw** | The original date text exactly as extracted from the EPUB bold span |
| **date_display** | Human-readable resolved date string (e.g. `"1918年4月14日"`) |
| **date_type** | Classification: `full` `month` `season` `period` `range` `list` `fuzzy` `relative` `year_only` |
| **date_resolution** | The process of parsing `date_raw` into structured `year/month/day/season` fields |
| **is_same_day** | Flag set true when the current entry's date was inherited from the previous entry via `同日` |

### Parsing

| Term | Definition |
|------|------------|
| **META files** | Non-chronological content: covers, TOC, publication notes, afterwords — skipped during parsing |
| **CHRON files** | Chronological year entries containing date-anchored events — the parsing target |
| **注脚 (Footnote)** | Annotation/reference markers in the text. Five styles evolved across the chronology |
| **尾注段 (Endnote Segment)** | The final split file in a group, containing only footnote definitions (0 date entries) |
| **干净文本 (Clean Text)** | Content after stripping: HTML tags, footnote markers, page anchors, and normalizing whitespace |

---

## File Naming Conventions

```
text/partNNNN.html              — Non-split chronological file
text/partNNNN_split_SSS.html    — Split file segment
  NNNN = 4-digit part number (0000-0121)
  SSS = 3-digit split index (000-004)
```

## Output

```
data/mao-chronology.jsonl       — Single JSONL file with all parsed entries
gotchas.md                       — Edge cases discovered during parsing
```

---

*Last updated: 2026-05-29*
