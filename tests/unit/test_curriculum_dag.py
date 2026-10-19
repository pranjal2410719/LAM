"""Unit test suite for curriculum prerequisite DAG validator and chain resolver (M2-01)."""

import pytest

from lam.domain.curriculum.models import (
    ConceptNode,
    CurriculumGraph,
    PrerequisiteEdge,
)
from lam.domain.curriculum.validator import (
    CurriculumGraphValidator,
    CyclicDependencyError,
    DuplicateEdgeError,
    UnknownConceptReferenceError,
)


@pytest.fixture
def validator() -> CurriculumGraphValidator:
    return CurriculumGraphValidator()


def _node(concept_id: str, display_name: str | None = None) -> ConceptNode:
    return ConceptNode(
        concept_id=concept_id,
        display_name=display_name or concept_id,
        domain="math",
    )


def test_empty_graph(validator: CurriculumGraphValidator) -> None:
    graph = CurriculumGraph(graph_id="empty_graph", version="1.0.0")
    report = validator.validate_graph(graph)
    assert report.is_valid is True
    assert report.total_nodes == 0
    assert report.total_edges == 0
    assert report.topological_order == []


def test_single_concept_graph(validator: CurriculumGraphValidator) -> None:
    n1 = _node("math.numbers.integers")
    graph = CurriculumGraph(
        graph_id="single_concept",
        version="1.0.0",
        nodes={n1.concept_id: n1},
    )
    report = validator.validate_graph(graph)
    assert report.is_valid is True
    assert report.total_nodes == 1
    assert report.topological_order == ["math.numbers.integers"]


def test_valid_linear_chain(validator: CurriculumGraphValidator) -> None:
    n1 = _node("math.fractions.basic")
    n2 = _node("math.fractions.addition_like")
    n3 = _node("math.fractions.addition_unlike")

    edges = [
        PrerequisiteEdge("math.fractions.basic", "math.fractions.addition_like"),
        PrerequisiteEdge("math.fractions.addition_like", "math.fractions.addition_unlike"),
    ]

    graph = CurriculumGraph(
        graph_id="linear_chain",
        version="1.0.0",
        nodes={n.concept_id: n for n in [n1, n2, n3]},
        edges=edges,
    )
    report = validator.validate_graph(graph)
    assert report.is_valid is True
    assert report.topological_order == [
        "math.fractions.basic",
        "math.fractions.addition_like",
        "math.fractions.addition_unlike",
    ]


def test_multiple_prerequisites_convergence(validator: CurriculumGraphValidator) -> None:
    # A -> C, B -> C
    nA = _node("math.algebra.variables")
    nB = _node("math.algebra.arithmetic")
    nC = _node("math.algebra.linear_equations")

    edges = [
        PrerequisiteEdge("math.algebra.variables", "math.algebra.linear_equations"),
        PrerequisiteEdge("math.algebra.arithmetic", "math.algebra.linear_equations"),
    ]

    graph = CurriculumGraph(
        graph_id="convergence",
        version="1.0.0",
        nodes={n.concept_id: n for n in [nA, nB, nC]},
        edges=edges,
    )
    report = validator.validate_graph(graph)
    assert report.is_valid is True
    idx_var = report.topological_order.index("math.algebra.variables")
    idx_arith = report.topological_order.index("math.algebra.arithmetic")
    idx_eq = report.topological_order.index("math.algebra.linear_equations")
    assert idx_var < idx_eq
    assert idx_arith < idx_eq


def test_disconnected_components(validator: CurriculumGraphValidator) -> None:
    nA = _node("math.algebra.basics")
    nB = _node("science.physics.motion")
    graph = CurriculumGraph(
        graph_id="disconnected",
        version="1.0.0",
        nodes={n.concept_id: n for n in [nA, nB]},
        edges=[],
    )
    report = validator.validate_graph(graph)
    assert report.is_valid is True
    assert len(report.topological_order) == 2
    # Lexicographical tie-breaking
    assert report.topological_order == ["math.algebra.basics", "science.physics.motion"]


def test_duplicate_edge_detection(validator: CurriculumGraphValidator) -> None:
    nA = _node("math.geometry.angles")
    nB = _node("math.geometry.triangles")
    edges = [
        PrerequisiteEdge("math.geometry.angles", "math.geometry.triangles"),
        PrerequisiteEdge("math.geometry.angles", "math.geometry.triangles"),
    ]
    graph = CurriculumGraph(
        graph_id="duplicate_edge",
        version="1.0.0",
        nodes={n.concept_id: n for n in [nA, nB]},
        edges=edges,
    )
    with pytest.raises(DuplicateEdgeError) as exc_info:
        validator.validate_graph(graph)
    assert "Duplicate edge detected" in str(exc_info.value)


def test_unknown_source_concept_reference(validator: CurriculumGraphValidator) -> None:
    nB = _node("math.geometry.triangles")
    edges = [PrerequisiteEdge("math.unknown.concept", "math.geometry.triangles")]
    graph = CurriculumGraph(
        graph_id="unknown_source",
        version="1.0.0",
        nodes={nB.concept_id: nB},
        edges=edges,
    )
    with pytest.raises(UnknownConceptReferenceError) as exc_info:
        validator.validate_graph(graph)
    assert "unknown source concept" in str(exc_info.value)


def test_unknown_target_concept_reference(validator: CurriculumGraphValidator) -> None:
    nA = _node("math.geometry.angles")
    edges = [PrerequisiteEdge("math.geometry.angles", "math.unknown.target")]
    graph = CurriculumGraph(
        graph_id="unknown_target",
        version="1.0.0",
        nodes={nA.concept_id: nA},
        edges=edges,
    )
    with pytest.raises(UnknownConceptReferenceError) as exc_info:
        validator.validate_graph(graph)
    assert "unknown target concept" in str(exc_info.value)


def test_direct_cycle_self_loop(validator: CurriculumGraphValidator) -> None:
    nA = _node("math.logic.propositions")
    edges = [PrerequisiteEdge("math.logic.propositions", "math.logic.propositions")]
    graph = CurriculumGraph(
        graph_id="self_loop",
        version="1.0.0",
        nodes={nA.concept_id: nA},
        edges=edges,
    )
    with pytest.raises(CyclicDependencyError) as exc_info:
        validator.validate_graph(graph)
    assert "Cycle detected" in str(exc_info.value)


def test_two_node_direct_cycle(validator: CurriculumGraphValidator) -> None:
    nA = _node("math.algebra.monomials")
    nB = _node("math.algebra.polynomials")
    edges = [
        PrerequisiteEdge("math.algebra.monomials", "math.algebra.polynomials"),
        PrerequisiteEdge("math.algebra.polynomials", "math.algebra.monomials"),
    ]
    graph = CurriculumGraph(
        graph_id="two_node_cycle",
        version="1.0.0",
        nodes={n.concept_id: n for n in [nA, nB]},
        edges=edges,
    )
    with pytest.raises(CyclicDependencyError) as exc_info:
        validator.validate_graph(graph)
    assert "Cycle detected" in str(exc_info.value)


def test_indirect_multi_hop_cycle(validator: CurriculumGraphValidator) -> None:
    # A -> B -> C -> D -> B (Cycle: B -> C -> D -> B)
    nA = _node("math.domain.node_a")
    nB = _node("math.domain.node_b")
    nC = _node("math.domain.node_c")
    nD = _node("math.domain.node_d")

    edges = [
        PrerequisiteEdge("math.domain.node_a", "math.domain.node_b"),
        PrerequisiteEdge("math.domain.node_b", "math.domain.node_c"),
        PrerequisiteEdge("math.domain.node_c", "math.domain.node_d"),
        PrerequisiteEdge("math.domain.node_d", "math.domain.node_b"),
    ]

    graph = CurriculumGraph(
        graph_id="multi_hop_cycle",
        version="1.0.0",
        nodes={n.concept_id: n for n in [nA, nB, nC, nD]},
        edges=edges,
    )
    with pytest.raises(CyclicDependencyError) as exc_info:
        validator.validate_graph(graph)
    assert "Cycle detected" in str(exc_info.value)


def test_malformed_concept_id_rejected() -> None:
    with pytest.raises(ValueError) as exc_info:
        ConceptNode(concept_id="INVALID_FORMAT", display_name="Bad", domain="math")
    assert "Invalid concept_id format" in str(exc_info.value)


def test_prerequisite_chain_resolution(validator: CurriculumGraphValidator) -> None:
    # A -> B -> C -> Target D
    nA = _node("math.fractions.numbers")
    nB = _node("math.fractions.multiplication")
    nC = _node("math.fractions.division")
    nD = _node("math.fractions.complex_fractions")

    edges = [
        PrerequisiteEdge("math.fractions.numbers", "math.fractions.multiplication"),
        PrerequisiteEdge("math.fractions.multiplication", "math.fractions.division"),
        PrerequisiteEdge("math.fractions.division", "math.fractions.complex_fractions"),
    ]

    graph = CurriculumGraph(
        graph_id="frac_chain",
        version="1.0.0",
        nodes={n.concept_id: n for n in [nA, nB, nC, nD]},
        edges=edges,
    )

    # 1. Learner has mastered numbers (0.95), but multiplication is unmastered (0.30)
    mastery = {
        "math.fractions.numbers": 0.95,
        "math.fractions.multiplication": 0.30,
        "math.fractions.division": 0.10,
    }

    chain = validator.resolve_prerequisite_chain(
        graph=graph,
        target_concept_id="math.fractions.complex_fractions",
        mastery_map=mastery,
        mastery_threshold=0.85,
    )

    assert chain.is_ready is False
    assert chain.direct_prerequisites == ["math.fractions.division"]
    assert chain.transitive_prerequisites_ordered == [
        "math.fractions.numbers",
        "math.fractions.multiplication",
        "math.fractions.division",
    ]
    assert chain.unmastered_ancestors == [
        "math.fractions.multiplication",
        "math.fractions.division",
    ]
    # Earliest unmastered concept in chain is multiplication
    assert chain.immediate_blocking_concept == "math.fractions.multiplication"

    # 2. When all prerequisites are mastered
    mastery_all = {
        "math.fractions.numbers": 0.95,
        "math.fractions.multiplication": 0.92,
        "math.fractions.division": 0.88,
    }
    chain_ready = validator.resolve_prerequisite_chain(
        graph=graph,
        target_concept_id="math.fractions.complex_fractions",
        mastery_map=mastery_all,
        mastery_threshold=0.85,
    )
    assert chain_ready.is_ready is True
    assert chain_ready.unmastered_ancestors == []
    assert chain_ready.immediate_blocking_concept is None
