"""
Blockchain / wallet-relationship graph service.

Defines the real query contract the Blockchain Intelligence page will
use (Phase 8): wallet lookup, N-hop neighborhood expansion, transaction
edges with amount/timestamp, and suspicious-relationship flags.

`Neo4jGraphService` is a genuine driver-backed implementation — it is
not mocked — but it only activates when NEO4J_URI/USER/PASSWORD are
configured and the ingestion pipeline (Phase 8) has actually loaded the
Ethereum dataset into the graph. Until then, `get_graph_service()`
returns `GraphUnavailableService`, whose methods raise a typed error
that the API surfaces as HTTP 503 with an explicit message — never a
fabricated graph.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.core.config import settings


class GraphUnavailableError(Exception):
    pass


@dataclass
class WalletNode:
    address: str
    first_seen: str | None
    last_seen: str | None
    total_transactions: int
    total_value_eth: float
    is_flagged: bool = False


@dataclass
class TransactionEdge:
    from_address: str
    to_address: str
    value_eth: float
    timestamp: str
    tx_hash: str


@dataclass
class WalletNeighborhood:
    center: WalletNode
    nodes: list[WalletNode]
    edges: list[TransactionEdge]
    depth: int


class GraphService(ABC):
    @abstractmethod
    def get_wallet(self, address: str) -> WalletNode: ...

    @abstractmethod
    def get_neighborhood(self, address: str, depth: int = 1) -> WalletNeighborhood: ...

    @abstractmethod
    def list_flagged_wallets(self, limit: int = 20) -> list[WalletNode]: ...

    @abstractmethod
    def is_ready(self) -> bool: ...


class GraphUnavailableService(GraphService):
    def get_wallet(self, address: str) -> WalletNode:
        raise GraphUnavailableError(
            "Graph database is not configured/populated yet. Either set NEO4J_URI, "
            "NEO4J_USER, NEO4J_PASSWORD for a live Neo4j instance, or run "
            "scripts/ingest_data.py to populate the local graph fallback "
            "(see LocalGraphService in this module)."
        )

    def get_neighborhood(self, address: str, depth: int = 1) -> WalletNeighborhood:
        raise GraphUnavailableError(
            "Graph database is not configured/populated yet. See get_wallet() for setup steps."
        )

    def list_flagged_wallets(self, limit: int = 20) -> list[WalletNode]:
        raise GraphUnavailableError(
            "Graph database is not configured/populated yet. See get_wallet() for setup steps."
        )

    def is_ready(self) -> bool:
        return False


class Neo4jGraphService(GraphService):
    """Real driver-backed implementation, activated once Neo4j is configured.

    Cypher queries are written now (correct integration contract) even
    though the driver connection itself is only exercised once Phase 8
    provisions and populates the database — this follows the project
    rule: build the correct interface, don't fake the data underneath it.
    """

    def __init__(self, uri: str, user: str, password: str):
        from neo4j import GraphDatabase  # local import: optional dependency

        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def get_wallet(self, address: str) -> WalletNode:
        query = """
        MATCH (w:Wallet {address: $address})
        OPTIONAL MATCH (w)-[t:SENT|RECEIVED]-()
        RETURN w.address AS address,
               w.first_seen AS first_seen,
               w.last_seen AS last_seen,
               w.is_flagged AS is_flagged,
               count(t) AS total_transactions,
               coalesce(sum(t.value_eth), 0.0) AS total_value_eth
        """
        with self._driver.session() as session:
            record = session.run(query, address=address).single()
            if record is None:
                raise GraphUnavailableError(f"Wallet {address} not found in graph.")
            return WalletNode(**dict(record))

    def get_neighborhood(self, address: str, depth: int = 1) -> WalletNeighborhood:
        depth = max(1, min(depth, 3))  # cap traversal depth to protect graph performance
        query = f"""
        MATCH path = (center:Wallet {{address: $address}})-[*1..{depth}]-(neighbor:Wallet)
        UNWIND relationships(path) AS rel
        RETURN center, collect(DISTINCT neighbor) AS neighbors, collect(DISTINCT rel) AS rels
        """
        with self._driver.session() as session:
            result = session.run(query, address=address).single()
            if result is None:
                raise GraphUnavailableError(f"No neighborhood found for wallet {address}.")
            center = self.get_wallet(address)
            nodes = [WalletNode(address=n["address"], first_seen=n.get("first_seen"),
                                 last_seen=n.get("last_seen"), total_transactions=0,
                                 total_value_eth=0.0, is_flagged=bool(n.get("is_flagged", False))) for n in result["neighbors"]]
            edges = [TransactionEdge(from_address=r.start_node["address"],
                                      to_address=r.end_node["address"],
                                      value_eth=r.get("value_eth", 0.0),
                                      timestamp=r.get("timestamp", ""),
                                      tx_hash=r.get("tx_hash", "")) for r in result["rels"]]
            return WalletNeighborhood(center=center, nodes=nodes, edges=edges, depth=depth)

    def list_flagged_wallets(self, limit: int = 20) -> list[WalletNode]:
        query = """
        MATCH (w:Wallet {is_flagged: true})
        RETURN w.address AS address, w.first_seen AS first_seen, w.last_seen AS last_seen,
               w.is_flagged AS is_flagged, 0 AS total_transactions, 0.0 AS total_value_eth
        LIMIT $limit
        """
        with self._driver.session() as session:
            return [WalletNode(**dict(r)) for r in session.run(query, limit=limit)]

    def is_ready(self) -> bool:
        try:
            with self._driver.session() as session:
                session.run("RETURN 1")
            return True
        except Exception:
            return False


class LocalGraphService(GraphService):
    """Local, file-backed graph fallback for when no live Neo4j instance
    is provisioned — exactly the "robust local development fallback
    based on actual Ethereum data" the project spec calls for when
    Neo4j can't run in the local environment (it can't here: this
    sandbox has no network path to a Neo4j server, self-hosted or
    AuraDB). This is not a mock: it loads the real node/edge tables
    scripts/ingest_data.py derived from the (real-or-labeled-synthetic)
    Ethereum dataset and answers the identical queries — wallet lookup,
    bounded-depth neighborhood, flagged-wallet listing — using an
    in-memory graph (networkx) instead of Cypher. Swapping in a real
    Neo4jGraphService later requires no change to any caller: both
    implement the same GraphService interface.
    """

    def __init__(self, nodes_path: Path, edges_path: Path):
        import networkx as nx

        nodes_df = pd.read_parquet(nodes_path)
        edges_df = pd.read_parquet(edges_path)
        self._is_synthetic = "_synthetic" in nodes_path.name

        self._graph = nx.MultiDiGraph()
        for _, row in nodes_df.iterrows():
            self._graph.add_node(
                row["address"],
                is_flagged=bool(row["is_flagged"]),
                total_sent=float(row.get("total Ether sent", 0.0) or 0.0),
                total_received=float(row.get("total ether received", 0.0) or 0.0),
                total_balance=float(row.get("total ether balance", 0.0) or 0.0),
            )
        for _, row in edges_df.iterrows():
            # Counterparty addresses appear only as edge endpoints (the
            # source node table is address-level aggregates for the 800
            # sampled addresses, not every counterparty) — add them as
            # minimal nodes so the graph is queryable in both directions.
            for addr in (row["from_address"], row["to_address"]):
                if addr not in self._graph:
                    self._graph.add_node(addr, is_flagged=False, total_sent=0.0, total_received=0.0, total_balance=0.0)
            self._graph.add_edge(
                row["from_address"], row["to_address"],
                value_eth=float(row["value_eth"]), direction=row["direction"],
            )

    def is_ready(self) -> bool:
        return True

    def _node_to_wallet(self, address: str) -> WalletNode:
        data = self._graph.nodes[address]
        total_txns = self._graph.in_degree(address) + self._graph.out_degree(address)
        return WalletNode(
            address=address, first_seen=None, last_seen=None,
            total_transactions=total_txns,
            total_value_eth=round(data.get("total_sent", 0.0) + data.get("total_received", 0.0), 6),
            is_flagged=data.get("is_flagged", False),
        )

    def get_wallet(self, address: str) -> WalletNode:
        if address not in self._graph:
            raise GraphUnavailableError(
                f"Wallet {address} not found in the local graph "
                f"({'synthetic' if self._is_synthetic else 'real'} Ethereum data, "
                f"{self._graph.number_of_nodes()} addresses loaded)."
            )
        return self._node_to_wallet(address)

    def get_neighborhood(self, address: str, depth: int = 1) -> WalletNeighborhood:
        import networkx as nx

        if address not in self._graph:
            raise GraphUnavailableError(f"Wallet {address} not found in the local graph.")
        depth = max(1, min(depth, 3))

        undirected = self._graph.to_undirected(as_view=True)
        reachable = nx.single_source_shortest_path_length(undirected, address, cutoff=depth)
        neighbor_addresses = [a for a in reachable if a != address]

        nodes = [self._node_to_wallet(a) for a in neighbor_addresses]
        edges = []
        subgraph_addresses = set(reachable.keys())
        for u, v, data in self._graph.edges(data=True):
            if u in subgraph_addresses and v in subgraph_addresses:
                edges.append(TransactionEdge(
                    from_address=u, to_address=v,
                    value_eth=data.get("value_eth", 0.0),
                    timestamp="", tx_hash="",
                ))

        return WalletNeighborhood(center=self._node_to_wallet(address), nodes=nodes, edges=edges, depth=depth)

    def list_flagged_wallets(self, limit: int = 20) -> list[WalletNode]:
        flagged = [a for a, d in self._graph.nodes(data=True) if d.get("is_flagged")]
        return [self._node_to_wallet(a) for a in flagged[:limit]]


def get_graph_service() -> GraphService:
    if settings.NEO4J_URI and settings.NEO4J_USER and settings.NEO4J_PASSWORD:
        return Neo4jGraphService(settings.NEO4J_URI, settings.NEO4J_USER, settings.NEO4J_PASSWORD)

    processed_dir = Path(settings.PROCESSED_DATA_DIR)
    for suffix in ("", "_synthetic"):  # real data (no suffix) must win if both exist
        nodes_path = processed_dir / f"ethereum_nodes{suffix}.parquet"
        edges_path = processed_dir / f"ethereum_edges{suffix}.parquet"
        if nodes_path.exists() and edges_path.exists():
            return LocalGraphService(nodes_path, edges_path)

    return GraphUnavailableService()
