#!/usr/bin/env python3
"""Graph cleaning: fix typos, merge cross-type duplicates, normalize dates, consolidate edge types."""

import json
import os
import re
from collections import defaultdict, Counter
from typing import List, Dict, Tuple


def load_jsonl(path: str) -> List[dict]:
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def save_jsonl(path: str, items: List[dict]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def node_key(name: str, etype: str) -> str:
    return f"{etype}:{name.strip()}"


def parse_date(d: str) -> Tuple[int, int, int]:
    if not d:
        return (0, 0, 0)
    m = re.search(r'(\d{4})', d)
    year = int(m.group(1)) if m else 0
    m = re.search(r'(\d{1,2})月', d)
    month = int(m.group(1)) if m else 0
    m = re.search(r'(\d{1,2})日', d)
    day = int(m.group(1)) if m else 0
    return (year, month, day)


EDGE_CANONICAL = {
    'meet_with': 'met_with',
    'meets': 'met_with',
    'met': 'met_with',
    'discussed': 'discussed_with',
    'organised': 'organized',
    'organized_by': 'organized',
    'dated': 'has_date',
    'dated_on': 'has_date',
    'date': 'has_date',
    'date_of': 'has_date',
    'in_date': 'has_date',
    'occurred_on': 'has_date',
    'part_of': 'member_of',
    'belongs_to': 'member_of',
    'affiliated_with': 'member_of',
    'written_by': 'wrote',
    'delivered_speech': 'wrote',
    'travels_from': 'travels_to',
    'commanded_by': 'ordered',
    'initiated': 'presided',
    'formed': 'presided',
    'read': 'wrote',
    'about': 'mentioned_in',
    'performed': 'attended',
    'involved_in': 'attended',
    'held_on': 'located_in',
    'works_at': 'located_in',
}
TYPE_FIX = {'organisation': 'organization'}


def clean_graph(raw_nodes: str, raw_edges: str, out_nodes: str, out_edges: str):
    print("Cleaning graph...")
    nodes = load_jsonl(raw_nodes)
    edges = load_jsonl(raw_edges)
    print(f"  Raw: {len(nodes)} nodes, {len(edges)} edges")

    # Step 1: Fix type typos
    typo_fixed = 0
    for n in nodes:
        if n['type'] in TYPE_FIX:
            n['type'] = TYPE_FIX[n['type']]
            typo_fixed += 1
    if typo_fixed:
        print(f"  Fixed {typo_fixed} type typos (organisation→organization)")

    # Step 2: Merge same-name/different-type duplicates
    merged = defaultdict(list)
    for n in nodes:
        merged[n['name']].append(n)

    multi_type = {k: v for k, v in merged.items() if len(v) > 1}
    print(f"  Cross-type duplicates: {len(multi_type)} names")

    canonical_nodes: Dict[str, dict] = {}
    id_remap: Dict[str, str] = {}

    for name, group in merged.items():
        if len(group) == 1:
            n = group[0]
            canonical_id = node_key(n['name'], n['type'])
            canonical_nodes[canonical_id] = dict(n)
            canonical_nodes[canonical_id]['id'] = canonical_id
            id_remap[n['id']] = canonical_id
        else:
            types = sorted(set(n['type'] for n in group))
            primary_type = types[0]
            n0 = group[0]
            new_id = node_key(n0['name'], primary_type)
            canonical_nodes[new_id] = {
                'id': new_id,
                'type': primary_type,
                'name': n0['name'],
                'aliases': sorted(set(a for n in group for a in n.get('aliases', []))),
                'date': min((n.get('date', '') for n in group if n.get('date')), default=n0.get('date', '')),
            }
            for n in group:
                id_remap[n['id']] = new_id

    print(f"  Nodes after cross-type merge: {len(canonical_nodes)}")

    # Step 3: Normalize date fields
    for n in canonical_nodes.values():
        d = n.get('date', '')
        if d:
            y, m, day = parse_date(d)
            n['year'] = y if y else None
            n['month'] = m if m else None
            n['day'] = day if day else None

    # Step 4: Remap & consolidate edges
    for e in edges:
        e['source'] = id_remap.get(e['source'], e['source'])
        e['target'] = id_remap.get(e['target'], e['target'])
        if e['type'] in EDGE_CANONICAL:
            e['type'] = EDGE_CANONICAL[e['type']]

    node_ids = set(canonical_nodes.keys())
    edge_groups: Dict[Tuple, List[dict]] = defaultdict(list)
    dropped = 0
    for e in edges:
        if e['source'] not in node_ids or e['target'] not in node_ids:
            dropped += 1
            continue
        edge_groups[(e['source'], e['target'], e['type'])].append(e)

    cleaned_edges = []
    for (src, tgt, etype), group in edge_groups.items():
        evidence = [e['evidence'] for e in group if e.get('evidence')]
        cleaned_edges.append({
            'source': src, 'target': tgt, 'type': etype,
            'evidence': evidence[0] if len(evidence) == 1 else evidence,
            'weight': len(group),
        })

    print(f"  Edges: {len(edges)} → {len(cleaned_edges)} (dropped {dropped} dangling)")

    # Step 5: Add node metrics
    degree = Counter()
    for e in cleaned_edges:
        degree[e['source']] += 1
        degree[e['target']] += 1
    for n in canonical_nodes.values():
        n['degree'] = degree.get(n['id'], 0)

    cleaned_nodes = sorted(canonical_nodes.values(), key=lambda n: (-n['degree'], n['type'], n['name']))

    # Step 6: Add org hierarchy edges
    org_parents = [
        ("中共中央政治局", "中共中央"),
        ("中共中央书记处", "中共中央"),
        ("中共中央军委", "中共中央"),
        ("中央文革小组", "中共中央"),
    ]
    hierarchy_added = 0
    for child_name, parent_name in org_parents:
        cid = node_key(child_name, "organization")
        pid = node_key(parent_name, "organization")
        if cid in canonical_nodes and pid in canonical_nodes:
            if not any(e['source'] == cid and e['target'] == pid for e in cleaned_edges):
                cleaned_edges.append({
                    'source': cid, 'target': pid, 'type': 'part_of',
                    'evidence': '组织层级', 'weight': 1,
                })
                hierarchy_added += 1
    if hierarchy_added:
        print(f"  Added {hierarchy_added} org hierarchy edges")

    save_jsonl(out_nodes, cleaned_nodes)
    save_jsonl(out_edges, cleaned_edges)

    tc = Counter(n['type'] for n in cleaned_nodes)
    ec = Counter(e['type'] for e in cleaned_edges)
    print(f"\nCleaned: {len(cleaned_nodes)} nodes, {len(cleaned_edges)} edges")
    print(f"  Node types: {dict(tc)}")
    print(f"  Edge types: {dict(ec)}")

    top = sorted(cleaned_nodes, key=lambda n: n['degree'], reverse=True)[:10]
    print(f"\nTop nodes:")
    for n in top:
        print(f"  [{n['type']:15s}] degree={n['degree']:4d}  {n['name']}")


if __name__ == "__main__":
    clean_graph(
        "data/graph/nodes.jsonl", "data/graph/edges.jsonl",
        "data/cleaned_graph/nodes.jsonl", "data/cleaned_graph/edges.jsonl",
    )
