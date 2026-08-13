import unittest

import torch

from dgraudit.adapters import MSGNetAdapter


class _Graph(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.nodevec1 = torch.nn.Parameter(torch.tensor([[1.0, 0.0], [0.0, 1.0]]))
        self.nodevec2 = torch.nn.Parameter(torch.tensor([[1.0, 0.0], [0.0, 1.0]]))


class MSGNetGraphTests(unittest.TestCase):
    def test_graph_stages_match_mixhop_normalization(self):
        stages = MSGNetAdapter._graph_stages(_Graph())
        torch.testing.assert_close(stages["adaptive"].sum(1), torch.ones(2))
        torch.testing.assert_close(stages["effective"].sum(1), torch.ones(2))
        expected = (stages["adaptive"] + torch.eye(2)) / 2
        torch.testing.assert_close(stages["effective"], expected)


if __name__ == "__main__":
    unittest.main()
