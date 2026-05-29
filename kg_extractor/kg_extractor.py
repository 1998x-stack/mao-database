#!/usr/bin/env python3
"""
Knowledge graph extraction pipeline for 毛泽东年谱 chronology.
Uses asyncio with configurable concurrency (default: 3).

Usage:
    python kg_extractor.py                          # process all entries
    python kg_extractor.py --limit 100              # process first 100 entries
    python kg_extractor.py --limit 100 --offset 50  # start from entry 50
"""

import json
import os
import sys
import signal
import asyncio
import argparse
from typing import List, Set, Dict

from config import INPUT_JSONL, NODES_FILE, EDGES_FILE, CHECKPOINT_FILE, CONCURRENCY
from llm_client import extract_knowledge_graph_async
from graph_store import GraphStore


_store: GraphStore = None
_processed_ids: Set[str] = set()


def _handle_interrupt(signum, frame):
    if _store and _processed_ids:
        _store.save_checkpoint(_processed_ids)
        print(f"\nInterrupted. Checkpoint saved ({len(_processed_ids)} entries).")
    sys.exit(1)


def load_entries(input_path: str, limit: int = 0, offset: int = 0) -> List[dict]:
    entries = []
    with open(input_path) as f:
        for line in f:
            entries.append(json.loads(line))
    if offset:
        entries = entries[offset:]
    if limit:
        entries = entries[:limit]
    return entries


def _remap_ids(llm_nodes: List[dict], llm_edges: List[dict],
               store: GraphStore, date_display: str = "") -> Dict[str, int]:
    id_map: Dict[str, str] = {}
    new_nodes = set()
    new_edges = 0

    for node in llm_nodes:
        name = node.get("name", "")
        etype = node.get("type", "")
        if not name or not etype:
            continue
        canonical_id = store.add_node(
            name=name, etype=etype,
            aliases=node.get("aliases"),
            date=node.get("date") or date_display,
        )
        id_map[node.get("id", "")] = canonical_id
        new_nodes.add(canonical_id)

    for edge in llm_edges:
        src = id_map.get(edge.get("source", ""))
        tgt = id_map.get(edge.get("target", ""))
        etype = edge.get("type", "")
        if not src or not tgt or not etype:
            continue
        added = store.add_edge(src, tgt, etype, edge.get("evidence", ""))
        if added:
            new_edges += 1

    return {"nodes_added": len(new_nodes), "edges_added": new_edges}


async def process_one(entry: dict, store: GraphStore, semaphore: asyncio.Semaphore,
                      stats: dict, idx: int, total: int):
    date_display = entry.get("date_display", f"{entry['year']}年")
    content = entry.get("content", "")

    if len(content) < 10:
        return

    result = await extract_knowledge_graph_async(date_display, content, semaphore)
    nodes = result.get("nodes", [])
    edges = result.get("edges", [])

    if nodes or edges:
        stats["entries_with_relations"] += 1

    remapped = _remap_ids(nodes, edges, store, date_display)
    stats["new_nodes"] += remapped["nodes_added"]
    stats["new_edges"] += remapped["edges_added"]


async def process_entries_async(
    entries: List[dict],
    store: GraphStore,
    processed_ids: Set[str],
    concurrency: int,
) -> dict:
    semaphore = asyncio.Semaphore(concurrency)
    stats = {
        "new_nodes": 0, "new_edges": 0,
        "entries_with_relations": 0,
        "skipped": 0, "skipped_short": 0, "processed": 0,
    }

    pending = []
    for i, entry in enumerate(entries):
        eid = entry["id"]

        if eid in processed_ids:
            stats["skipped"] += 1
            continue

        content = entry.get("content", "")
        if len(content) < 10:
            processed_ids.add(eid)
            stats["skipped_short"] += 1
            continue

        task = asyncio.create_task(
            process_one(entry, store, semaphore, stats, i, len(entries))
        )
        pending.append((eid, i, task))

        if len(pending) >= concurrency * 2:
            await _drain_batch(pending, processed_ids, store, stats, len(entries))

    await _drain_batch(pending, processed_ids, store, stats, len(entries))
    store.save_checkpoint(processed_ids)
    return stats


async def _drain_batch(pending, processed_ids, store, stats, total):
    while pending:
        eid, i, task = pending.pop(0)
        await task
        processed_ids.add(eid)
        stats["processed"] += 1

        if stats["processed"] % 20 == 0:
            store.save_checkpoint(processed_ids)
            print(f"  [{stats['processed']}] "
                  f"nodes={store.node_count()} edges={store.edge_count()} "
                  f"skipped={stats['skipped']}(+{stats['skipped_short']} short)")


async def main_async(args):
    store = GraphStore(NODES_FILE, EDGES_FILE, CHECKPOINT_FILE)
    processed_ids = store.load_checkpoint()

    global _store, _processed_ids
    _store = store
    _processed_ids = processed_ids

    entries = load_entries(INPUT_JSONL, args.limit, args.offset)
    total = len(entries)

    if processed_ids:
        remaining = sum(1 for e in entries if e["id"] not in processed_ids)
        print(f"Resuming: {len(processed_ids)} already processed, "
              f"{remaining} remaining out of {total} total")
    else:
        print(f"Starting fresh: {total} entries to process")

    print(f"Concurrency: {CONCURRENCY}")

    stats = await process_entries_async(entries, store, processed_ids, CONCURRENCY)

    print(f"\nDone.")
    print(f"  Processed: {stats['processed']}")
    print(f"  Skipped (already done): {stats['skipped']}")
    print(f"  Skipped (short content): {stats['skipped_short']}")
    print(f"  Entries with relations: {stats['entries_with_relations']}")
    print(f"  Total nodes: {store.node_count()}")
    print(f"  Total edges: {store.edge_count()}")
    print(f"  New nodes this run: {stats['new_nodes']}")
    print(f"  New edges this run: {stats['new_edges']}")


def main():
    parser = argparse.ArgumentParser(description="Extract knowledge graph")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()

    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("Error: DEEPSEEK_API_KEY environment variable not set.")
        sys.exit(1)

    signal.signal(signal.SIGINT, _handle_interrupt)
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
