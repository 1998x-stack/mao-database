import json
import os
import re
from typing import Set, Dict, List, Tuple


def _make_key(name: str, etype: str) -> str:
    return f"{etype}-{_slug(name)}"


def _slug(text: str) -> str:
    return re.sub(r'[^\w\u4e00-\u9fff]', '', text).lower()


class GraphStore:
    def __init__(self, nodes_path: str, edges_path: str, checkpoint_path: str):
        self.nodes_path = nodes_path
        self.edges_path = edges_path
        self.checkpoint_path = checkpoint_path
        self._node_cache: Dict[str, dict] = {}
        self._edge_keys: Set[Tuple[str, str, str]] = set()
        self._loaded = False

    def _ensure_loaded(self):
        if self._loaded:
            return
        self._loaded = True
        if os.path.exists(self.nodes_path):
            with open(self.nodes_path) as f:
                for line in f:
                    node = json.loads(line)
                    nid = node.get("id", "")
                    if nid:
                        self._node_cache[nid] = node
        if os.path.exists(self.edges_path):
            with open(self.edges_path) as f:
                for line in f:
                    edge = json.loads(line)
                    self._edge_keys.add((
                        edge.get("source", ""),
                        edge.get("target", ""),
                        edge.get("type", ""),
                    ))

    def load_checkpoint(self) -> Set[str]:
        if os.path.exists(self.checkpoint_path):
            with open(self.checkpoint_path) as f:
                data = json.load(f)
            return set(data.get("processed_ids", []))
        return set()

    def save_checkpoint(self, processed_ids: Set[str]):
        self._ensure_loaded()
        os.makedirs(os.path.dirname(self.checkpoint_path), exist_ok=True)
        tmp = self.checkpoint_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({
                "processed_ids": sorted(processed_ids),
                "count": len(processed_ids),
            }, f, ensure_ascii=False)
        os.replace(tmp, self.checkpoint_path)

    def add_node(self, name: str, etype: str, aliases: List[str] = None,
                 date: str = None, extra: dict = None) -> str:
        self._ensure_loaded()
        canonical_id = _make_key(name, etype)
        if canonical_id in self._node_cache:
            return canonical_id

        node = {"id": canonical_id, "type": etype, "name": name}
        if aliases:
            node["aliases"] = aliases
        if date:
            node["date"] = date
        if extra:
            node.update(extra)

        os.makedirs(os.path.dirname(self.nodes_path), exist_ok=True)
        with open(self.nodes_path, "a") as f:
            f.write(json.dumps(node, ensure_ascii=False) + "\n")

        self._node_cache[canonical_id] = node
        return canonical_id

    def add_edge(self, source: str, target: str, etype: str,
                 evidence: str = "") -> bool:
        self._ensure_loaded()
        key = (source, target, etype)
        if key in self._edge_keys:
            return False

        edge = {"source": source, "target": target, "type": etype}
        if evidence:
            edge["evidence"] = evidence

        os.makedirs(os.path.dirname(self.edges_path), exist_ok=True)
        with open(self.edges_path, "a") as f:
            f.write(json.dumps(edge, ensure_ascii=False) + "\n")

        self._edge_keys.add(key)
        return True

    def node_count(self) -> int:
        self._ensure_loaded()
        return len(self._node_cache)

    def edge_count(self) -> int:
        self._ensure_loaded()
        return len(self._edge_keys)
