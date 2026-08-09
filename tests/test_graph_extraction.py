import unittest

import torch


class GraphStageInvariantTests(unittest.TestCase):
    def test_reference_stage_invariants(self):
        activated = torch.tensor([[0.8, 0.4], [0.3, 0.7]])
        diagonal_removed = activated - torch.diag(torch.diag(activated))
        self.assertEqual(float(torch.diag(diagonal_removed).abs().max()), 0.0)
        topk_mask = torch.tensor([[0.0, 1.0], [1.0, 0.0]])
        topk_graph = topk_mask * diagonal_removed
        self_loop = topk_graph + torch.eye(2)
        normalized = self_loop / self_loop.sum(1).view(-1, 1)
        torch.testing.assert_close(normalized.sum(1), torch.ones(2))
        self.assertTrue(bool(torch.isfinite(normalized).all()))


if __name__ == "__main__":
    unittest.main()
