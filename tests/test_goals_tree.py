from __future__ import annotations

import unittest

from app.goals import recompute_statuses


class RecomputeStatusesTests(unittest.TestCase):
    def test_root_open(self):
        nodes = [{"id": 1, "status": "locked", "title": "G"}]
        out = recompute_statuses(nodes, [])
        self.assertEqual(out[0]["status"], "open")

    def test_child_locked_until_parent_done(self):
        nodes = [
            {"id": 1, "status": "open", "title": "root"},
            {"id": 2, "status": "open", "title": "child"},
        ]
        edges = [{"parent_node_id": 1, "child_node_id": 2}]
        out = {n["id"]: n["status"] for n in recompute_statuses(nodes, edges)}
        self.assertEqual(out[1], "open")
        self.assertEqual(out[2], "locked")

    def test_child_opens_when_parent_done(self):
        nodes = [
            {"id": 1, "status": "done", "title": "root"},
            {"id": 2, "status": "locked", "title": "child"},
        ]
        edges = [{"parent_node_id": 1, "child_node_id": 2}]
        out = {n["id"]: n["status"] for n in recompute_statuses(nodes, edges)}
        self.assertEqual(out[2], "open")

    def test_all_parents_required(self):
        nodes = [
            {"id": 1, "status": "done", "title": "a"},
            {"id": 2, "status": "open", "title": "b"},
            {"id": 3, "status": "locked", "title": "child"},
        ]
        edges = [
            {"parent_node_id": 1, "child_node_id": 3},
            {"parent_node_id": 2, "child_node_id": 3},
        ]
        out = {n["id"]: n["status"] for n in recompute_statuses(nodes, edges)}
        self.assertEqual(out[3], "locked")
        nodes[1]["status"] = "done"
        out = {n["id"]: n["status"] for n in recompute_statuses(nodes, edges)}
        self.assertEqual(out[3], "open")

    def test_done_stays_done(self):
        nodes = [
            {"id": 1, "status": "open", "title": "root"},
            {"id": 2, "status": "done", "title": "child"},
        ]
        edges = [{"parent_node_id": 1, "child_node_id": 2}]
        out = {n["id"]: n["status"] for n in recompute_statuses(nodes, edges)}
        self.assertEqual(out[2], "done")


if __name__ == "__main__":
    unittest.main()
