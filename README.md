<div align="center">

# 毛泽东年谱数据库

**Mao Zedong Chronology — Structured Time-Series Database & Knowledge Graph**

[![GitHub Pages](https://img.shields.io/badge/demo-visualization-C41E3A?logo=github)](https://1998x-stack.github.io/mao-database/)
[![Python](https://img.shields.io/badge/python-3.8%2B-2E5090?logo=python)](https://www.python.org/)
[![DeepSeek](https://img.shields.io/badge/LLM-deepseek--v4--flash-6B3FA0)](https://api-docs.deepseek.com/)

</div>

---

## Overview

A two-stage pipeline that transforms the 9-volume, 1893—1976 biographical chronology of Mao Zedong into structured, queryable data:

1. **EPUB → JSONL** — regex-enhanced HTML parser extracting 12,271 date-anchored events with normalized temporal fields
2. **JSONL → Knowledge Graph** — LLM-powered entity and relation extraction producing a connected graph of persons, organizations, locations, events, and documents

▶ **[Live Knowledge Graph Visualization](https://1998x-stack.github.io/mao-database/)** — interactive D3.js force graph with time-range and type filters

## Project Structure

```
mao-database/
├── index.html                  # knowledge graph visualization (GitHub Pages)
├── base-dark.css               # design system
│
├── epub_parser/                # Project 1: EPUB → JSONL
│   ├── parse.py                #   main pipeline
│   ├── epub_reader.py          #   EPUB unzip + file classification
│   ├── html_parser.py          #   BS4 HTML extraction
│   ├── date_resolver.py        #   regex date normalization + 同日 state machine
│   ├── text_cleaner.py         #   footnote stripping + text cleaning
│   └── requirements.txt        #   beautifulsoup4, lxml
│
├── kg_extractor/               # Project 2: JSONL → Knowledge Graph
│   ├── kg_extractor.py         #   main pipeline (asyncio, resume)
│   ├── config.py               #   model config + system prompt
│   ├── llm_client.py           #   DeepSeek API wrapper (retry/timeout)
│   ├── graph_store.py          #   append-only node/edge store + checkpoint
│   └── requirements.txt        #   openai
│
├── data/
│   ├── mao-chronology.jsonl    #   parsed chronology (12,271 entries)
│   └── graph/
│       ├── nodes.jsonl         #   extracted entities (340+ nodes)
│       ├── edges.jsonl         #   extracted relations (616+ edges)
│       └── checkpoint.json     #   processing resume state
│
├── docs/                       # design specifications
├── CONTEXT.md                  # domain glossary
└── gotchas.md                  # parsing edge cases
```

## Quick Start

### Prerequisites

```bash
# Project 1 dependencies
pip install -r epub_parser/requirements.txt

# Project 2 dependencies
pip install -r kg_extractor/requirements.txt
```

### Parse EPUB → JSONL

```bash
cd epub_parser
python parse.py ../毛泽东年谱.epub ../data/mao-chronology.jsonl
```

### Extract Knowledge Graph

```bash
export DEEPSEEK_API_KEY=sk-...

cd kg_extractor
python kg_extractor.py                    # full dataset
python kg_extractor.py --limit 100        # test with 100 entries
```

The extractor resumes from the last checkpoint on restart — no duplicated API calls.

## Data Schema

### Chronology Entry

| Field | Type | Example |
|-------|------|---------|
| `id` | string | `"1918-04-14-00084"` |
| `year` | int | `1918` |
| `date_raw` | string | `"4月14日"` / `"同日"` / `"春"` |
| `date_type` | enum | `full` `relative` `season` `range` `list` `fuzzy` |
| `content` | string | Clean text, no HTML or footnotes |
| `is_same_day` | bool | `true` for `同日` entries (35% of dataset) |

### Knowledge Graph Node

| Field | Type | Example |
|-------|------|---------|
| `id` | string | `"person-毛泽东"` |
| `type` | enum | `person` `organization` `location` `event` `document` `date` |
| `name` | string | `"毛泽东"` |
| `date` | string | `"1918年春"` |

### Knowledge Graph Edge

| Field | Type | Example |
|-------|------|---------|
| `source` | string | `"person-毛泽东"` |
| `target` | string | `"event-新民学会成立大会"` |
| `type` | enum | `attended` `wrote` `met_with` `sent_to` `presided` `travels_to` … |
| `evidence` | string | Source text snippet |

## Statistics

| Metric | Value |
|--------|-------|
| Chronology entries | 12,271 (1893—1976) |
| Full dates | 7,365 (60%) |
| Same-day continuations (`同日`) | 3,934 (32%) |
| Knowledge graph nodes | 340+ |
| Knowledge graph edges | 616+ |
| Entity types | 6 (person, org, location, event, document, date) |
| Relation types | 10 (attended, wrote, met_with, sent_to, presided, discussed_with, ordered, approved, located_in, travels_to) |

## Edge Cases Handled

- **同日 chains**: state machine inherits previous date (3,808 entries correctly resolved)
- **5 footnote systems**: unified `<sup>` stripping across 83 years of evolving markup
- **2 HTML structures**: `div.chapter` (Vol 1) vs `div.calibre11` (Vol 2+) content containers
- **Split files**: 17 year-groups merged from multi-segment EPUB splits
- **Date variants**: 21 regex patterns covering seasons, ten-day periods, ranges, lists, fuzzy markers
- **Cross-volume years**: global sequential ID prevents collisions when years span volume boundaries
- **Resume**: checkpoint-based processing skips already-extracted entries on restart

## License

Data sourced from *毛泽东年谱* (中共中央文献研究室, 1993/2013). Code available for research and educational use.
