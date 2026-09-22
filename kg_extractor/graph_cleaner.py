"""Normalize knowledge graph without changing relation semantics or inventing links."""
import json
import os
import re
import tempfile
from collections import Counter
from pathlib import Path

ALIASES = {"meet_with": "met_with", "meets": "met_with", "met": "met_with"}
INVERSE = {"written_by": "wrote"}
ISO = re.compile(r"^(\d{4})-(\d{1,2})(?:-(\d{1,2}))?(?:$|T)")
CHINESE = re.compile(r"(\d{4})年(?:(\d{1,2})月)?(?:(\d{1,2})日)?")


def parse_date(value):
    if not isinstance(value, str):
        return (0, 0, 0)
    match = ISO.match(value.strip()) or CHINESE.search(value)
    if not match:
        return (0, 0, 0)
    year, month, day = (int(p) if p else 0 for p in match.groups())
    return (year, month, day) if month <= 12 and day <= 31 else (0, 0, 0)


def _evidence(value):
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [part for part in value if isinstance(part, str) and part]
    return []


def normalize_graph(nodes, edges):
    """Keep differently typed names separate; retain every distinct evidence text."""
    normalized = {}
    remap = {}
    for node in nodes:
        name, kind, old_id = node.get("name"), node.get("type"), node.get("id")
        if not all(isinstance(x, str) and x.strip() for x in (name, kind, old_id)):
            raise ValueError(f"Invalid node: {node!r}")
        kind = {"organisation": "organization"}.get(kind, kind)
        key = f"{kind}:{name.strip()}"
        if old_id in remap and remap[old_id] != key:
            raise ValueError(f"Conflicting node ID: {old_id}")
        remap[old_id] = key
        if key not in normalized:
            normalized[key] = dict(node, id=key, name=name.strip(), type=kind)
        else:
            previous = normalized[key]
            previous["aliases"] = list(dict.fromkeys(
                (previous.get("aliases") or []) + (node.get("aliases") or [])))
    grouped = {}
    for edge in edges:
        src, dst = remap.get(edge.get("source")), remap.get(edge.get("target"))
        kind = edge.get("type")
        if src is None or dst is None:
            raise ValueError(f"Dangling edge: {edge!r}")
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError(f"Invalid edge type: {edge!r}")
        if kind in INVERSE:
            src, dst, kind = dst, src, INVERSE[kind]
        else:
            kind = ALIASES.get(kind, kind)
        key = (src, dst, kind)
        if key not in grouped:
            grouped[key] = dict(edge, source=src, target=dst, type=kind,
                                weight=0, evidence=[])
        result = grouped[key]
        result["weight"] += max(1, int(edge.get("weight") or 1))
        result["evidence"].extend(_evidence(edge.get("evidence")))
    cleaned_edges = []
    for key in sorted(grouped):
        result = grouped[key]
        evidence = list(dict.fromkeys(result["evidence"]))
        result["evidence"] = evidence[0] if len(evidence) == 1 else evidence
        cleaned_edges.append(result)
    degree = Counter()
    for edge in cleaned_edges:
        degree[edge["source"]] += 1
        degree[edge["target"]] += 1
    for node in normalized.values():
        node["degree"] = degree[node["id"]]
        year, month, day = parse_date(node.get("date"))
        node.update(year=year or None, month=month or None, day=day or None)
    return sorted(normalized.values(),
                  key=lambda node: (-node["degree"], node["type"], node["name"])), cleaned_edges


def _load(path):
    with open(path, encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _save(path, items):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         dir=destination.parent, delete=False) as stream:
            temp_name = stream.name
            for item in items:
                stream.write(json.dumps(item, ensure_ascii=False) + "\n")
        os.replace(temp_name, destination)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def clean_graph(raw_nodes, raw_edges, out_nodes, out_edges):
    nodes, edges = normalize_graph(_load(raw_nodes), _load(raw_edges))
    _save(out_nodes, nodes)
    _save(out_edges, edges)
    print(f"Cleaned graph: {len(nodes)} nodes, {len(edges)} edges")
    return nodes, edges


if __name__ == "__main__":
    clean_graph("data/graph/nodes.jsonl", "data/graph/edges.jsonl",
                "data/cleaned_graph/nodes.jsonl", "data/cleaned_graph/edges.jsonl")
