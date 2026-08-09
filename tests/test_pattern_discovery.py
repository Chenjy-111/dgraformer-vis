import unittest

from dgraudit.cli.discover_patterns import candidate, edge_id


class PatternDiscoveryTests(unittest.TestCase):
    def test_candidate_label_is_mandatory(self):
        item = candidate("persistent_edge", edge_id="0->1")
        self.assertEqual(item["label"], "Candidate Pattern")
        self.assertEqual(item["pattern_type"], "persistent_edge")

    def test_edge_id_is_directed(self):
        self.assertEqual(edge_id(2, 5), "2->5")
        self.assertNotEqual(edge_id(2, 5), edge_id(5, 2))


if __name__ == "__main__":
    unittest.main()
