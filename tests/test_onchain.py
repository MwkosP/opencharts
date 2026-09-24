import unittest

import numpy as np

from chartist.core.onchain import (
    buildIndicators,
    buildKpis,
    buildTransfers,
    buildWalletGraph,
)


class OnChainHelpersTests(unittest.TestCase):
    def test_btc_kpis(self):
        kpis = buildKpis("BTC", pulse=1)
        self.assertEqual(kpis.network, "BTC")
        self.assertGreater(kpis.active_addresses, 0)
        self.assertGreater(kpis.hash_or_stake, 0)

    def test_indicators_per_network(self):
        btc = buildIndicators("BTC", pulse=0, days=40)
        eth = buildIndicators("ETH", pulse=0, days=40)
        self.assertTrue(any(s.key == "hash" for s in btc))
        self.assertTrue(any(s.key == "stable" for s in eth))
        self.assertEqual(len(btc[0].values), 40)

    def test_transfers_and_graph(self):
        xfers = buildTransfers("SOL", pulse=2, count=20)
        self.assertEqual(len(xfers), 20)
        graph = buildWalletGraph("BTC", pulse=0)
        self.assertGreater(len(graph.nodes), 10)
        self.assertGreater(len(graph.edges), 10)
        self.assertEqual(graph.correlation.shape[0], len(graph.clusters))
        np.testing.assert_allclose(np.diag(graph.correlation), 1.0, atol=1e-6)


if __name__ == "__main__":
    unittest.main()
