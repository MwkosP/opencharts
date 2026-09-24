"""Synthetic on-chain analytics for BTC and other networks.

Demo approximations only — replace with real indexers / explorers when available.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


NETWORKS = (
    ("BTC", "Bitcoin"),
    ("ETH", "Ethereum"),
    ("SOL", "Solana"),
    ("BASE", "Base"),
    ("ARB", "Arbitrum"),
)

LIVE_MS = 10_000


@dataclass(frozen=True)
class NetworkKpis:
    network: str
    active_addresses: float
    tx_count: float
    fees_native: float
    exchange_netflow: float  # negative = outflow (bullish bias)
    whale_ratio: float
    hash_or_stake: float  # BTC hashrate EH/s or ETH staked %


@dataclass(frozen=True)
class OnchainSeries:
    key: str
    title: str
    dates: np.ndarray
    values: np.ndarray
    secondary: np.ndarray | None = None
    secondary_title: str | None = None


@dataclass(frozen=True)
class WhaleTransfer:
    time_label: str
    network: str
    from_label: str
    to_label: str
    amount: float
    usd: float
    kind: str  # exchange_in | exchange_out | whale | bridge | dex


@dataclass(frozen=True)
class WalletNode:
    wallet_id: str
    label: str
    cluster: str
    size: float  # relative
    x: float
    y: float


@dataclass(frozen=True)
class WalletEdge:
    source: str
    target: str
    weight: float
    kind: str


@dataclass(frozen=True)
class WalletGraph:
    nodes: tuple[WalletNode, ...]
    edges: tuple[WalletEdge, ...]
    correlation: np.ndarray  # cluster correlation matrix
    clusters: tuple[str, ...]


def _profile(network: str) -> dict:
    return {
        "BTC": {"scale": 1.0, "fee": 12.0, "hash": 620.0, "unit": "BTC"},
        "ETH": {"scale": 0.85, "fee": 0.004, "hash": 28.0, "unit": "ETH"},
        "SOL": {"scale": 0.55, "fee": 0.0002, "hash": 0.0, "unit": "SOL"},
        "BASE": {"scale": 0.35, "fee": 0.0004, "hash": 0.0, "unit": "ETH"},
        "ARB": {"scale": 0.30, "fee": 0.0003, "hash": 0.0, "unit": "ETH"},
    }.get(network, {"scale": 0.5, "fee": 1.0, "hash": 0.0, "unit": "TOKEN"})


def buildKpis(network: str = "BTC", pulse: int = 0) -> NetworkKpis:
    rng = np.random.default_rng((abs(hash(network)) + pulse * 97) % (2**32))
    p = _profile(network)
    wave = 1.0 + 0.04 * np.sin(pulse * 0.15)
    return NetworkKpis(
        network=network,
        active_addresses=float(820_000 * p["scale"] * wave * (1 + rng.normal(0, 0.02))),
        tx_count=float(340_000 * p["scale"] * wave * (1 + rng.normal(0, 0.03))),
        fees_native=float(p["fee"] * wave * (1 + rng.normal(0, 0.05))),
        exchange_netflow=float(rng.normal(-420 * p["scale"], 180 * p["scale"])),
        whale_ratio=float(np.clip(0.42 + rng.normal(0, 0.03), 0.2, 0.75)),
        hash_or_stake=float(p["hash"] * (1 + 0.01 * np.sin(pulse * 0.1) + rng.normal(0, 0.005))),
    )


def buildIndicators(network: str = "BTC", pulse: int = 0, days: int = 120) -> list[OnchainSeries]:
    rng = np.random.default_rng((abs(hash((network, "ind"))) + pulse * 31) % (2**32))
    dates = np.arange(days, dtype=float)
    p = _profile(network)
    scale = p["scale"]

    def s(base, amp, speed, noise, lo=None, hi=None):
        vals = (
            base * scale
            + amp * scale * np.sin((dates + pulse) * speed)
            + rng.normal(0, noise * scale, size=days)
        )
        if lo is not None or hi is not None:
            vals = np.clip(vals, lo if lo is not None else -1e18, hi if hi is not None else 1e18)
        return vals.astype(float)

    active = s(800_000, 90_000, 0.06, 20_000, 100_000, None)
    tx = s(320_000, 60_000, 0.08, 15_000, 50_000, None)
    fees = s(p["fee"] * 80, p["fee"] * 30, 0.09, p["fee"] * 8)
    inflow = s(2_400, 900, 0.11, 220)
    outflow = s(2_700, 850, 0.10, 200)
    sopr = s(1.02, 0.08, 0.07, 0.02, 0.85, 1.25) / max(scale, 0.3) * 0.3 + 0.7
    mvrv = s(1.6, 0.45, 0.05, 0.08, 0.6, 3.2)
    nupl = s(0.35, 0.25, 0.06, 0.04, -0.2, 0.8)
    dormancy = s(40, 12, 0.04, 3, 10, 90)
    stable_supply = s(120, 18, 0.05, 4)  # bn USD proxy on L2/ETH
    dex_vol = s(4.5, 1.8, 0.12, 0.4)

    series = [
        OnchainSeries("active", "Active addresses", dates, active),
        OnchainSeries("tx", "Transaction count", dates, tx),
        OnchainSeries("fees", "Fees (native)", dates, fees),
        OnchainSeries(
            "flows",
            "Exchange inflow",
            dates,
            inflow,
            secondary=outflow,
            secondary_title="Outflow",
        ),
        OnchainSeries("sopr", "SOPR / realized ratio", dates, sopr),
        OnchainSeries("mvrv", "MVRV", dates, mvrv),
        OnchainSeries("nupl", "NUPL", dates, nupl),
        OnchainSeries("dormancy", "Average dormancy", dates, dormancy),
        OnchainSeries("dex", "DEX volume ($B)", dates, dex_vol),
    ]
    if network in ("ETH", "BASE", "ARB", "SOL"):
        series.append(OnchainSeries("stable", "Stablecoin supply ($B)", dates, stable_supply))
    if network == "BTC":
        hashrate = s(600, 40, 0.03, 8, 400, 800)
        series.append(OnchainSeries("hash", "Hashrate (EH/s)", dates, hashrate))
        series.append(
            OnchainSeries(
                "miner",
                "Miner to exchange",
                dates,
                s(180, 70, 0.09, 20),
            )
        )
    return series


def buildTransfers(network: str = "BTC", pulse: int = 0, count: int = 80) -> list[WhaleTransfer]:
    rng = np.random.default_rng((abs(hash((network, "xfer"))) + pulse * 53) % (2**32))
    p = _profile(network)
    unit = p["unit"]
    exchanges = ("Binance", "Coinbase", "OKX", "Bybit", "Kraken")
    whales = ("Whale-A", "Whale-B", "Whale-C", "Fund-X", "OTC-Desk", "Miner-Pool")
    kinds = ("exchange_in", "exchange_out", "whale", "bridge", "dex")
    out: list[WhaleTransfer] = []
    seconds = 10 * 3600 + pulse
    for i in range(count):
        kind = kinds[int(rng.integers(0, len(kinds)))]
        if kind == "exchange_in":
            src, dst = whales[int(rng.integers(0, len(whales)))], exchanges[int(rng.integers(0, len(exchanges)))]
        elif kind == "exchange_out":
            src, dst = exchanges[int(rng.integers(0, len(exchanges)))], whales[int(rng.integers(0, len(whales)))]
        else:
            src = whales[int(rng.integers(0, len(whales)))]
            dst = whales[int(rng.integers(0, len(whales)))]
            while dst == src:
                dst = whales[int(rng.integers(0, len(whales)))]
        amount = float(rng.lognormal(mean=4.2 if network == "BTC" else 5.5, sigma=0.7) * p["scale"])
        px = {"BTC": 64_000, "ETH": 3_400, "SOL": 148, "BASE": 3_400, "ARB": 3_400}.get(network, 100)
        seconds += int(rng.integers(30, 180))
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        out.append(
            WhaleTransfer(
                time_label=f"{h:02d}:{m:02d}:{s:02d}",
                network=network,
                from_label=src,
                to_label=dst,
                amount=round(amount, 4),
                usd=round(amount * px, 0),
                kind=kind,
            )
        )
    out.reverse()
    return out


def buildWalletGraph(network: str = "BTC", pulse: int = 0) -> WalletGraph:
    """Wallet relationship graph + cluster correlation matrix."""
    rng = np.random.default_rng((abs(hash((network, "graph"))) + pulse * 19) % (2**32))
    clusters = ("Exchanges", "Whales", "Miners/Validators", "DeFi", "OTC", "Retail hubs")
    nodes: list[WalletNode] = []
    # Place clusters around a ring, nodes jittered inside.
    for ci, cluster in enumerate(clusters):
        angle = 2 * np.pi * ci / len(clusters)
        cx, cy = np.cos(angle) * 0.62, np.sin(angle) * 0.62
        n_local = 5 if cluster != "Retail hubs" else 7
        for j in range(n_local):
            jx, jy = rng.normal(0, 0.11), rng.normal(0, 0.11)
            wid = f"{network[:3]}-{cluster[:3]}-{j}"
            nodes.append(
                WalletNode(
                    wallet_id=wid,
                    label=f"{cluster[:3]}-{j}",
                    cluster=cluster,
                    size=float(rng.uniform(0.45, 1.4)),
                    x=float(cx + jx),
                    y=float(cy + jy),
                )
            )

    id_by_cluster = {c: [n.wallet_id for n in nodes if n.cluster == c] for c in clusters}
    edges: list[WalletEdge] = []
    kinds = ("transfer", "bridge", "dex", "otc")
    # Intra-cluster + some cross-cluster links.
    for cluster, ids in id_by_cluster.items():
        for _ in range(max(3, len(ids))):
            a, b = rng.choice(ids, size=2, replace=False)
            edges.append(
                WalletEdge(
                    source=str(a),
                    target=str(b),
                    weight=float(rng.uniform(0.2, 1.0)),
                    kind=kinds[int(rng.integers(0, len(kinds)))],
                )
            )
    for _ in range(18):
        c1, c2 = rng.choice(clusters, size=2, replace=False)
        a = str(rng.choice(id_by_cluster[str(c1)]))
        b = str(rng.choice(id_by_cluster[str(c2)]))
        edges.append(
            WalletEdge(
                source=a,
                target=b,
                weight=float(rng.uniform(0.15, 0.9)),
                kind=kinds[int(rng.integers(0, len(kinds)))],
            )
        )

    # Correlation between clusters from shared edge weights.
    n = len(clusters)
    corr = np.eye(n)
    idx = {c: i for i, c in enumerate(clusters)}
    node_cluster = {n.wallet_id: n.cluster for n in nodes}
    for edge in edges:
        i = idx[node_cluster[edge.source]]
        j = idx[node_cluster[edge.target]]
        if i != j:
            corr[i, j] += edge.weight * 0.15
            corr[j, i] = corr[i, j]
    # Normalize off-diagonals into [-1, 1]-ish display range.
    off = corr - np.eye(n)
    if off.max() > 0:
        off = off / off.max()
    corr = np.clip(off + np.eye(n), -1, 1)
    # Subtle pulse drift
    corr = np.clip(corr + rng.normal(0, 0.02, size=corr.shape), -1, 1)
    np.fill_diagonal(corr, 1.0)

    return WalletGraph(
        nodes=tuple(nodes),
        edges=tuple(edges),
        correlation=corr.astype(float),
        clusters=clusters,
    )


__all__ = [
    "LIVE_MS",
    "NETWORKS",
    "NetworkKpis",
    "OnchainSeries",
    "WalletEdge",
    "WalletGraph",
    "WalletNode",
    "WhaleTransfer",
    "buildIndicators",
    "buildKpis",
    "buildTransfers",
    "buildWalletGraph",
]
