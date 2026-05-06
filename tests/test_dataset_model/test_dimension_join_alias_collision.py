from __future__ import annotations

from foggy.dataset_model.definitions.base import DbColumnDef
from foggy.dataset_model.impl.model import (
    DbTableModelImpl,
    DimensionJoinDef,
)
from foggy.dataset_model.semantic import SemanticQueryService
from foggy.mcp_spi.semantic import SemanticQueryRequest


def _service_with_colliding_join_aliases() -> SemanticQueryService:
    model = DbTableModelImpl(
        name="AccountMoveLikeModel",
        source_table="account_move",
        dimension_joins=[
            DimensionJoinDef(
                name="company",
                table_name="res_company",
                foreign_key="company_id",
                primary_key="id",
                caption_column="name",
            ),
            DimensionJoinDef(
                name="currency",
                table_name="res_currency",
                foreign_key="currency_id",
                primary_key="id",
                caption_column="name",
            ),
        ],
        columns={
            "name": DbColumnDef(name="name", alias="Number"),
        },
    )
    service = SemanticQueryService()
    service.register_model(model)
    return service


def test_dimension_join_alias_collision_uses_unique_runtime_aliases() -> None:
    service = _service_with_colliding_join_aliases()
    request = SemanticQueryRequest(
        columns=["name", "currency$caption"],
        slice=[
            {
                "field": "company$id",
                "op": "in",
                "value": [2, 1],
            }
        ],
    )

    response = service.query_model("AccountMoveLikeModel", request, mode="validate")

    assert response.error is None, response.error
    assert response.sql is not None
    assert "LEFT JOIN res_company AS rc ON t.company_id = rc.id" in response.sql
    assert (
        "LEFT JOIN res_currency AS j_currency "
        "ON t.currency_id = j_currency.id"
    ) in response.sql
    assert "j_currency.name" in response.sql
    assert "rc.id IN (?, ?)" in response.sql
    assert response.sql.count(" AS rc ") == 1
