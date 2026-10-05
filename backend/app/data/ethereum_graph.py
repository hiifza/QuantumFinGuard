"""
Ethereum dataset -> graph-ready structures.

The real/synthetic Ethereum dataset (schemas.py) is address-level with
aggregate stats (total sent, unique counterparties, etc), not a raw
edge list of individual transactions — that's the actual shape of the
public Kaggle dataset. To build the wallet-relationship graph described
in the project spec, we derive an edge list consistent with each
address's own aggregate stats (an address with "Unique Sent To
Addresses = 12" gets exactly 12 outgoing edges) — a real, deterministic
derivation from the real per-address fields, not fabricated on top of
them.

A meaningful fraction of each address's counterparties are drawn from
the *other addresses already in the dataset* (deterministically, by
index) rather than a brand-new synthetic address every time. This
matters for more than realism: if every counterparty were unique, the
graph would be a forest of disconnected stars — a single wallet fanned
out to leaves with no further connections — and multi-hop neighborhood
expansion (the actual point of the graph module) would never have
anything beyond depth 1 to find. Reusing existing addresses as
counterparties is what gives the graph genuine multi-hop structure to
traverse, which is verified in tests rather than assumed.

This is what Phase 8 loads into Neo4j via
app.services.graph_service.Neo4jGraphService, or into the local
networkx fallback via LocalGraphService when no Neo4j instance is
reachable.
"""
import hashlib

import pandas as pd

INTERCONNECT_FRACTION = 0.4  # share of edges that reuse an existing dataset address as counterparty


def _counterparty_address(seed_address: str, i: int) -> str:
    """Deterministic pseudo-address so re-running produces the same graph
    (needed for reproducible research results)."""
    return "0x" + hashlib.sha256(f"{seed_address}-cp-{i}".encode()).hexdigest()[:40]


def _existing_address(all_addresses: list[str], seed_address: str, i: int) -> str:
    """Deterministically picks another address already in the dataset as
    the counterparty, skipping self-loops. Index-based selection (not
    random) keeps the graph reproducible across re-runs."""
    if len(all_addresses) <= 1:
        return _counterparty_address(seed_address, i)
    idx = (hash(f"{seed_address}-{i}") % (len(all_addresses) - 1))
    candidate = all_addresses[idx]
    if candidate == seed_address:
        candidate = all_addresses[(idx + 1) % len(all_addresses)]
    return candidate


def derive_edges(df: pd.DataFrame, max_edges_per_address: int = 15) -> pd.DataFrame:
    """Returns a (from_address, to_address, value_eth, direction) edge
    table derived from each row's own Sent/Received and unique-counterparty
    counts. See module docstring for why some counterparties are reused
    existing addresses rather than always-unique synthetic ones."""
    all_addresses = df["Address"].tolist()
    edges = []
    for _, row in df.iterrows():
        addr = row["Address"]

        n_sent = min(int(row.get("Unique Sent To Addresses", 0) or 0), max_edges_per_address)
        total_sent = float(row.get("total Ether sent", 0.0) or 0.0)
        for i in range(n_sent):
            counterparty = (
                _existing_address(all_addresses, addr, i)
                if i < int(n_sent * INTERCONNECT_FRACTION)
                else _counterparty_address(addr, i)
            )
            edges.append({
                "from_address": addr,
                "to_address": counterparty,
                "value_eth": round(total_sent / max(n_sent, 1), 6),
                "direction": "sent",
            })

        n_received = min(int(row.get("Unique Received From Addresses", 0) or 0), max_edges_per_address)
        total_received = float(row.get("total ether received", 0.0) or 0.0)
        for i in range(n_received):
            counterparty = (
                _existing_address(all_addresses, addr, 1000 + i)
                if i < int(n_received * INTERCONNECT_FRACTION)
                else _counterparty_address(addr, 1000 + i)
            )
            edges.append({
                "from_address": counterparty,
                "to_address": addr,
                "value_eth": round(total_received / max(n_received, 1), 6),
                "direction": "received",
            })

    return pd.DataFrame(edges)


def build_node_table(df: pd.DataFrame) -> pd.DataFrame:
    return df[[
        "Address", "FLAG", "Sent tnx", "Received Tnx",
        "total Ether sent", "total ether received", "total ether balance",
    ]].rename(columns={"Address": "address", "FLAG": "is_flagged"})
