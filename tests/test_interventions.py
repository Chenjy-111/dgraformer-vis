import unittest

import torch

from dgraudit.adapters import apply_graph_intervention


class InterventionTests(unittest.TestCase):
    def setUp(self):
        self.graph = torch.tensor([[0.6, 0.4], [0.2, 0.8]])

    def test_structural_removal_renormalizes(self):
        result = apply_graph_intervention(self.graph, {"type": "structural_edge_removal", "source": 0, "target": 1})
        self.assertEqual(float(result[0, 1]), 0.0)
        torch.testing.assert_close(result.sum(1), torch.ones(2))

    def test_channel_mask_does_not_renormalize(self):
        result = apply_graph_intervention(self.graph, {"type": "normalized_channel_mask", "source": 0, "target": 1})
        self.assertAlmostEqual(float(result[0].sum()), 0.6, places=6)

    def test_variable_incoming_removal(self):
        result = apply_graph_intervention(self.graph, {"type": "variable_incoming_removal", "variable": 1})
        self.assertEqual(float(result[0, 1]), 0.0)
        torch.testing.assert_close(result.sum(1), torch.ones(2))


if __name__ == "__main__":
    unittest.main()
