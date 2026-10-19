"""Integration tests for Curriculum DAG API endpoints."""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_validate_valid_dag(async_client: AsyncClient) -> None:
    headers = auth_headers()
    payload = {
        "nodes": [
            {"concept_id": "math.arithmetic.addition", "title": "Addition", "subject": "math"},
            {
                "concept_id": "math.arithmetic.multiplication",
                "title": "Multiplication",
                "subject": "math",
            },
            {"concept_id": "math.algebra.expressions", "title": "Expressions", "subject": "math"},
        ],
        "edges": [
            {
                "source_concept_id": "math.arithmetic.addition",
                "target_concept_id": "math.arithmetic.multiplication",
            },
            {
                "source_concept_id": "math.arithmetic.multiplication",
                "target_concept_id": "math.algebra.expressions",
            },
        ],
    }
    response = await async_client.post("/v1/curriculum/validate", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["is_dag"] is True
    assert data["topological_order"] == [
        "math.arithmetic.addition",
        "math.arithmetic.multiplication",
        "math.algebra.expressions",
    ]


@pytest.mark.asyncio
async def test_validate_rejects_cycle_with_422(async_client: AsyncClient) -> None:
    headers = auth_headers()
    payload = {
        "nodes": [
            {"concept_id": "math.node.a", "title": "Node A", "subject": "math"},
            {"concept_id": "math.node.b", "title": "Node B", "subject": "math"},
        ],
        "edges": [
            {"source_concept_id": "math.node.a", "target_concept_id": "math.node.b"},
            {"source_concept_id": "math.node.b", "target_concept_id": "math.node.a"},
        ],
    }
    response = await async_client.post("/v1/curriculum/validate", json=payload, headers=headers)
    assert response.status_code == 422
    data = response.json()
    assert "cycle" in data["detail"].lower()


@pytest.mark.asyncio
async def test_check_prerequisites_blocking(async_client: AsyncClient) -> None:
    headers = auth_headers()
    payload = {
        "nodes": [
            {"concept_id": "math.fractions.basic", "title": "Basic Fractions", "subject": "math"},
            {"concept_id": "math.fractions.addition", "title": "Addition", "subject": "math"},
        ],
        "edges": [
            {
                "source_concept_id": "math.fractions.basic",
                "target_concept_id": "math.fractions.addition",
            }
        ],
        "target_concept_id": "math.fractions.addition",
        "mastery_threshold": 0.85,
        "mastery_map": {"math.fractions.basic": 0.50},
    }
    response = await async_client.post(
        "/v1/curriculum/check-prerequisites", json=payload, headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_ready"] is False
    assert data["blocking_direct_prerequisites"] == ["math.fractions.basic"]
    assert "math.fractions.basic" in data["ancestor_chain"]


@pytest.mark.asyncio
async def test_curriculum_unauthorized_rejected(async_client: AsyncClient) -> None:
    payload = {
        "nodes": [{"concept_id": "math.basic", "title": "Basic", "subject": "math"}],
        "edges": [],
    }
    response = await async_client.post("/v1/curriculum/validate", json=payload)
    assert response.status_code == 401
