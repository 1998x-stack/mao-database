"""Regression tests for graph normalization (no LLM or external data needed)."""

import json
import tempfile
import unittest
from pathlib import Path

from kg_extractor.graph_cleaner import clean_graph, normalize_graph, parse_date


class DateParsingTests(unittest.TestCase):
    def test_iso_and_chinese_dates(self):
        self.assertEqual(parse_date("1918-04-14"), (1918, 4, 14))
        self.assertEqual(parse_date("1918年4月14日"), (1918, 4, 14))
        self.assertEqual(parse_date("1918年春"), (1918, 0, 0))
        self.assertEqual(parse_date("unknown"), (0, 0, 0))

    def test_no_invented_precision(self):
        self.assertEqual(parse_date("1918-04"), (1918, 4, 0))
        self.assertEqual(parse_date("1918-13-01"), (0, 0, 0))


class GraphCleaningTests(unittest.TestCase):
    def test_cross_type_homonyms_do_not_merge(self):
        nodes = [
            {"id": "a", "name": "同名", "type": "person"},
            {"id": "b", "name": "同名", "type": "organization"},
        ]
        result, edges = normalize_graph(nodes, [])
        self.assertEqual({n["id"] for n in result}, {"person:同名", "organization:同名"})
        self.assertEqual(edges, [])

    def test_inverse_edges_swap_endpoints_and_keep_evidence(self):
        nodes = [
            {"id": "a", "name": "作者", "type": "person"},
            {"id": "b", "name": "作品", "type": "document"},
        ]
        edges = [
            {"source": "b", "target": "a", "type": "written_by", "evidence": "文献证据一"},
            {"source": "a", "target": "b", "type": "wrote", "evidence": "文献证据二"},
        ]
        _, result = normalize_graph(nodes, edges)
        self.assertEqual(len(result), 1)
        self.assertEqual((result[0]["source"], result[0]["target"], result[0]["type"]),
                         ("person:作者", "document:作品", "wrote"))
        self.assertEqual(result[0]["weight"], 2)
        self.assertEqual(result[0]["evidence"], ["文献证据一", "文献证据二"])

    def test_ambiguous_relations_are_not_misrepresented(self):
        nodes = [{"id": "a", "name": "甲", "type": "person"},
                 {"id": "b", "name": "乙", "type": "document"}]
        _, edges = normalize_graph(nodes, [
            {"source": "a", "target": "b", "type": "read", "evidence": "阅读"}])
        self.assertEqual(edges[0]["type"], "read")

    def test_empty_graph_and_dangling_edge(self):
        self.assertEqual(normalize_graph([], []), ([], []))
        with self.assertRaisesRegex(ValueError, "Dangling"):
            normalize_graph([{"id": "a", "name": "甲", "type": "person"}],
                            [{"source": "a", "target": "missing", "type": "met"}])

    def test_clean_graph_round_trip_and_repeatability(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_nodes, raw_edges = root / "raw-n.jsonl", root / "raw-e.jsonl"
            out_nodes, out_edges = root / "output" / "n.jsonl", root / "output" / "e.jsonl"
            raw_nodes.write_text(json.dumps({"id": "p", "name": "甲", "type": "person", "date": "1918-04-14"}) + "\n", encoding="utf-8")
            raw_edges.write_text("", encoding="utf-8")
            clean_graph(raw_nodes, raw_edges, out_nodes, out_edges)
            first = out_nodes.read_bytes(), out_edges.read_bytes()
            clean_graph(raw_nodes, raw_edges, out_nodes, out_edges)
            self.assertEqual(first, (out_nodes.read_bytes(), out_edges.read_bytes()))
            self.assertEqual(json.loads(out_nodes.read_text(encoding="utf-8"))["month"], 4)


if __name__ == "__main__":
    unittest.main()
