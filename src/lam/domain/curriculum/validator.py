"""Curriculum DAG validation, cycle detection, and topological sorting (M2-01)."""

from collections import defaultdict, deque
from dataclasses import dataclass, field

from lam.domain.curriculum.models import (
    CurriculumGraph,
    EdgeType,
)


class CurriculumValidationError(Exception):
    """Base exception for curriculum graph validation failures."""

    pass


class CyclicDependencyError(CurriculumValidationError):
    """Raised when the curriculum graph contains a cycle."""

    def __init__(self, message: str, cycle_path: list[str]) -> None:
        super().__init__(message)
        self.cycle_path = cycle_path


class UnknownConceptReferenceError(CurriculumValidationError):
    """Raised when an edge references a concept ID not present in nodes."""

    pass


class DuplicateEdgeError(CurriculumValidationError):
    """Raised when multiple identical edges exist between concepts."""

    pass


class MalformedConceptIdError(CurriculumValidationError):
    """Raised when a concept ID fails format validation."""

    pass


@dataclass(frozen=True)
class PrerequisiteChainResult:
    """Result of analyzing prerequisite readiness for a target concept."""

    target_concept_id: str
    is_ready: bool
    direct_prerequisites: list[str]
    transitive_prerequisites_ordered: list[str]
    blocking_prerequisites: list[str]
    immediate_blocking_concept: str | None
    unmastered_ancestors: list[str]


@dataclass
class GraphValidationReport:
    """Report detailing graph validity and structure."""

    is_valid: bool
    total_nodes: int
    total_edges: int
    topological_order: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class CurriculumGraphValidator:
    """Validates curriculum prerequisite DAGs for acyclicity and integrity."""

    def validate_graph(self, graph: CurriculumGraph) -> GraphValidationReport:
        """Validates graph integrity, rejecting cycles, unknown nodes, and duplicate edges.

        Returns a GraphValidationReport. Raises CurriculumValidationError on failure.
        """
        # 1. Check for empty node set
        if not graph.nodes:
            return GraphValidationReport(
                is_valid=True,
                total_nodes=0,
                total_edges=0,
                topological_order=[],
            )

        # 2. Check for unknown concept references and duplicate edges
        seen_edges: set[tuple[str, str]] = set()
        for edge in graph.edges:
            if edge.source_concept_id not in graph.nodes:
                raise UnknownConceptReferenceError(
                    f"Edge references unknown source concept: '{edge.source_concept_id}'"
                )
            if edge.target_concept_id not in graph.nodes:
                raise UnknownConceptReferenceError(
                    f"Edge references unknown target concept: '{edge.target_concept_id}'"
                )
            edge_key = (edge.source_concept_id, edge.target_concept_id)
            if edge_key in seen_edges:
                raise DuplicateEdgeError(
                    f"Duplicate edge detected from '{edge.source_concept_id}' "
                    f"to '{edge.target_concept_id}'"
                )
            seen_edges.add(edge_key)

        # 3. Detect cycles using DFS with 3-color marking
        # 0 = unvisited, 1 = visiting (in recursion stack), 2 = visited
        color: dict[str, int] = {node_id: 0 for node_id in graph.nodes}
        adj: dict[str, list[str]] = defaultdict(list)
        for edge in graph.edges:
            adj[edge.source_concept_id].append(edge.target_concept_id)

        parent: dict[str, str | None] = {node_id: None for node_id in graph.nodes}

        def _dfs_cycle(node: str, path: list[str]) -> list[str] | None:
            color[node] = 1
            path.append(node)
            for neighbor in adj[node]:
                if color[neighbor] == 1:
                    # Cycle detected: backtrack path from neighbor to node
                    cycle_start_idx = path.index(neighbor)
                    return path[cycle_start_idx:] + [neighbor]
                if color[neighbor] == 0:
                    parent[neighbor] = node
                    cycle = _dfs_cycle(neighbor, path)
                    if cycle:
                        return cycle
            path.pop()
            color[node] = 2
            return None

        for node_id in sorted(graph.nodes.keys()):
            if color[node_id] == 0:
                cycle_found = _dfs_cycle(node_id, [])
                if cycle_found:
                    raise CyclicDependencyError(
                        f"Cycle detected in prerequisite graph: {' -> '.join(cycle_found)}",
                        cycle_path=cycle_found,
                    )

        # 4. Compute deterministic topological sort using Kahn's algorithm
        in_degree: dict[str, int] = {node_id: 0 for node_id in graph.nodes}
        for edge in graph.edges:
            in_degree[edge.target_concept_id] += 1

        # Use sorted queue for deterministic tie-breaking (lexicographical)
        zero_in_degree: list[str] = sorted(
            [node_id for node_id, deg in in_degree.items() if deg == 0]
        )
        topo_order: list[str] = []

        queue = deque(zero_in_degree)
        while queue:
            # Sort current level to maintain strict determinism
            curr = queue.popleft()
            topo_order.append(curr)

            next_candidates: list[str] = []
            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    next_candidates.append(neighbor)

            # Insert candidates sorted to preserve determinism
            for cand in sorted(next_candidates):
                queue.append(cand)

        return GraphValidationReport(
            is_valid=True,
            total_nodes=len(graph.nodes),
            total_edges=len(graph.edges),
            topological_order=topo_order,
        )

    def resolve_prerequisite_chain(
        self,
        graph: CurriculumGraph,
        target_concept_id: str,
        mastery_map: dict[str, float],
        mastery_threshold: float = 0.85,
    ) -> PrerequisiteChainResult:
        """Resolves transitive prerequisites and evaluates blocking gaps against student mastery."""
        if target_concept_id not in graph.nodes:
            raise UnknownConceptReferenceError(
                f"Target concept '{target_concept_id}' not found in curriculum graph"
            )

        # Validate graph integrity first
        report = self.validate_graph(graph)
        topo_index = {node_id: idx for idx, node_id in enumerate(report.topological_order)}

        # Direct strict prerequisites
        direct_prereqs = graph.get_prerequisites(target_concept_id, strict_only=True)

        # Find all ancestors via reverse BFS/DFS
        ancestors: set[str] = set()
        queue = deque(direct_prereqs)
        while queue:
            curr = queue.popleft()
            if curr not in ancestors:
                ancestors.add(curr)
                for edge in graph.edges:
                    if (
                        edge.target_concept_id == curr
                        and edge.edge_type == EdgeType.STRICT_PREREQUISITE
                    ):
                        if edge.source_concept_id not in ancestors:
                            queue.append(edge.source_concept_id)

        # Order ancestors topologically
        transitive_ordered = sorted(ancestors, key=lambda nid: topo_index.get(nid, 0))

        # Identify unmastered ancestors
        unmastered: list[str] = []
        for prereq_id in transitive_ordered:
            mastery = mastery_map.get(prereq_id, 0.0)
            if mastery < mastery_threshold:
                unmastered.append(prereq_id)

        # Direct blocking prerequisites
        blocking_direct = [p for p in direct_prereqs if mastery_map.get(p, 0.0) < mastery_threshold]

        # Immediate blocking concept is the earliest unmastered concept in topological chain
        immediate_blocking = unmastered[0] if unmastered else None

        is_ready = len(unmastered) == 0

        return PrerequisiteChainResult(
            target_concept_id=target_concept_id,
            is_ready=is_ready,
            direct_prerequisites=direct_prereqs,
            transitive_prerequisites_ordered=transitive_ordered,
            blocking_prerequisites=blocking_direct,
            immediate_blocking_concept=immediate_blocking,
            unmastered_ancestors=unmastered,
        )
