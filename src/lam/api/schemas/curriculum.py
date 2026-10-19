"""API Schemas for Curriculum Graph DAG validation and prerequisite resolution."""

from pydantic import AliasChoices, BaseModel, Field

from lam.domain.curriculum.models import EdgeType


class ConceptNodeSchema(BaseModel):
    concept_id: str = Field(..., min_length=3, max_length=128)
    display_name: str = Field(
        ...,
        min_length=1,
        validation_alias=AliasChoices("display_name", "title"),
    )
    domain: str = Field(
        ...,
        min_length=1,
        validation_alias=AliasChoices("domain", "subject"),
    )
    grade_level: int | None = Field(default=None, ge=1, le=12)


class PrerequisiteEdgeSchema(BaseModel):
    source_concept_id: str = Field(..., min_length=3, max_length=128)
    target_concept_id: str = Field(..., min_length=3, max_length=128)
    edge_type: EdgeType = EdgeType.STRICT_PREREQUISITE
    weight: float = Field(default=1.0, ge=0.0, le=1.0)


class CurriculumValidationRequest(BaseModel):
    graph_id: str = Field(default="graph_v1", min_length=1)
    version: str = Field(default="1.0.0", min_length=1)
    nodes: list[ConceptNodeSchema] = Field(..., min_length=1)
    edges: list[PrerequisiteEdgeSchema] = Field(default_factory=list)


class CurriculumValidationResponse(BaseModel):
    valid: bool
    is_dag: bool
    topological_order: list[str]
    total_nodes: int
    total_edges: int
    message: str


class PrerequisiteCheckRequest(BaseModel):
    graph_id: str = Field(default="graph_v1", min_length=1)
    version: str = Field(default="1.0.0", min_length=1)
    nodes: list[ConceptNodeSchema] = Field(..., min_length=1)
    edges: list[PrerequisiteEdgeSchema] = Field(default_factory=list)
    target_concept_id: str = Field(..., min_length=3, max_length=128)
    mastery_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    mastery_map: dict[str, float] = Field(default_factory=dict)


class PrerequisiteCheckResponse(BaseModel):
    target_concept_id: str
    is_ready: bool
    blocking_direct_prerequisites: list[str]
    ancestor_chain: list[str]
    mastery_threshold: float
