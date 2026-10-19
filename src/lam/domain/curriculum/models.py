"""Curriculum prerequisite graph domain models (Milestone M2-01)."""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

# Format: <subject>.<domain>.<topic>[.<subtopic>]
# e.g., math.fractions.addition_unlike_denominators
CONCEPT_ID_PATTERN = re.compile(r"^[a-z0-9]+(\.[a-z0-9_]+){2,4}$")


class EdgeType(StrEnum):
    STRICT_PREREQUISITE = "strict_prerequisite"  # Target requires source mastery
    SOFT_CO_REQUISITE = "soft_co_requisite"  # Recommended prior or parallel
    ENRICHMENT = "enrichment"  # Optional extension


@dataclass(frozen=True)
class ConceptNode:
    """Represents a discrete learning objective/concept in the curriculum graph."""

    concept_id: str
    display_name: str
    domain: str
    grade_level: int | None = None
    description: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.concept_id or not CONCEPT_ID_PATTERN.match(self.concept_id):
            raise ValueError(
                f"Invalid concept_id format: '{self.concept_id}'. "
                "Must follow dot-separated pattern: <subject>.<domain>.<topic>[.<subtopic>]"
            )


@dataclass(frozen=True)
class PrerequisiteEdge:
    """Directed prerequisite relationship: source_concept must precede target_concept."""

    source_concept_id: str
    target_concept_id: str
    edge_type: EdgeType = EdgeType.STRICT_PREREQUISITE
    weight: float = 1.0


@dataclass
class CurriculumGraph:
    """A versioned Directed Acyclic Graph (DAG) of curriculum concepts."""

    graph_id: str
    version: str
    nodes: dict[str, ConceptNode] = field(default_factory=dict)
    edges: list[PrerequisiteEdge] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def get_prerequisites(self, concept_id: str, strict_only: bool = True) -> list[str]:
        """Returns direct prerequisites for the given concept."""
        prereqs: list[str] = []
        for edge in self.edges:
            if edge.target_concept_id == concept_id:
                if not strict_only or edge.edge_type == EdgeType.STRICT_PREREQUISITE:
                    prereqs.append(edge.source_concept_id)
        return sorted(prereqs)

    def get_dependents(self, concept_id: str) -> list[str]:
        """Returns direct concepts that depend on the given concept."""
        deps: list[str] = []
        for edge in self.edges:
            if edge.source_concept_id == concept_id:
                deps.append(edge.target_concept_id)
        return sorted(deps)
