"""API Routes for Curriculum Knowledge Graph DAG validation and prerequisite resolution."""

from fastapi import APIRouter, Depends, HTTPException, status

from lam.api.schemas.curriculum import (
    ConceptNodeSchema,
    CurriculumValidationRequest,
    CurriculumValidationResponse,
    PrerequisiteCheckRequest,
    PrerequisiteCheckResponse,
    PrerequisiteEdgeSchema,
)
from lam.domain.curriculum.models import (
    ConceptNode,
    CurriculumGraph,
    PrerequisiteEdge,
)
from lam.domain.curriculum.validator import (
    CurriculumGraphValidator,
    CurriculumValidationError,
    CyclicDependencyError,
)
from lam.infrastructure.authentication.middleware import (
    SecurityContext,
    authorize_access,
    get_security_context,
)

router = APIRouter(prefix="/v1/curriculum", tags=["Curriculum DAG"])


def _build_graph(
    graph_id: str,
    version: str,
    nodes_schema: list[ConceptNodeSchema],
    edges_schema: list[PrerequisiteEdgeSchema],
) -> CurriculumGraph:
    nodes = {
        n.concept_id: ConceptNode(
            concept_id=n.concept_id,
            display_name=n.display_name,
            domain=n.domain,
            grade_level=n.grade_level,
        )
        for n in nodes_schema
    }
    edges = [
        PrerequisiteEdge(
            source_concept_id=e.source_concept_id,
            target_concept_id=e.target_concept_id,
            edge_type=e.edge_type,
            weight=e.weight,
        )
        for e in edges_schema
    ]
    return CurriculumGraph(graph_id=graph_id, version=version, nodes=nodes, edges=edges)


@router.post(
    "/validate",
    response_model=CurriculumValidationResponse,
    summary="Validate curriculum knowledge graph for cycles and compute topological sort",
)
async def validate_curriculum(
    request: CurriculumValidationRequest,
    sec: SecurityContext = Depends(get_security_context),
) -> CurriculumValidationResponse:
    authorize_access(sec, resource="curriculum")
    graph = _build_graph(request.graph_id, request.version, request.nodes, request.edges)
    validator = CurriculumGraphValidator()

    try:
        report = validator.validate_graph(graph)
        return CurriculumValidationResponse(
            valid=report.is_valid,
            is_dag=report.is_valid,
            topological_order=report.topological_order,
            total_nodes=report.total_nodes,
            total_edges=report.total_edges,
            message="Curriculum graph is a valid Directed Acyclic Graph (DAG).",
        )
    except CyclicDependencyError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Curriculum graph contains a cycle: {e.cycle_path}",
        )
    except CurriculumValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        )


@router.post(
    "/check-prerequisites",
    response_model=PrerequisiteCheckResponse,
    summary="Check prerequisite readiness and ancestor chains for a concept",
)
async def check_prerequisites(
    request: PrerequisiteCheckRequest,
    sec: SecurityContext = Depends(get_security_context),
) -> PrerequisiteCheckResponse:
    authorize_access(sec, resource="curriculum")
    graph = _build_graph(request.graph_id, request.version, request.nodes, request.edges)
    validator = CurriculumGraphValidator()

    try:
        chain_result = validator.resolve_prerequisite_chain(
            graph=graph,
            target_concept_id=request.target_concept_id,
            mastery_map=request.mastery_map,
            mastery_threshold=request.mastery_threshold,
        )
        return PrerequisiteCheckResponse(
            target_concept_id=chain_result.target_concept_id,
            is_ready=chain_result.is_ready,
            blocking_direct_prerequisites=chain_result.blocking_prerequisites,
            ancestor_chain=chain_result.transitive_prerequisites_ordered,
            mastery_threshold=request.mastery_threshold,
        )
    except CurriculumValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        )
