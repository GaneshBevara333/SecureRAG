from typing import List, Dict, Any, Tuple
from sqlalchemy import and_, or_, false
from app.db.models import Document, Chunk


def build_acl_condition(
    user_id: str,
    org_id: str,
    is_admin: bool,
    team_ids: List[str],
):
    """
    Build SQLAlchemy filter clause for Document queries.
    Rule: same org AND (admin OR owner OR visibility='org' OR (visibility='team' AND team_id in user's teams)).
    """
    if is_admin:
        return Document.org_id == org_id

    team_condition = (
        and_(Document.visibility == "team", Document.team_id.in_(team_ids))
        if team_ids
        else false()
    )

    return and_(
        Document.org_id == org_id,
        or_(
            Document.owner_id == user_id,
            Document.visibility == "org",
            team_condition,
        ),
    )


def build_chunk_acl_condition(
    user_id: str,
    org_id: str,
    is_admin: bool,
    team_ids: List[str],
):
    """
    Build SQLAlchemy filter clause for Chunk joined with Document.
    Applied directly inside the SQL query, never filtered after retrieval.
    """
    if is_admin:
        return Chunk.org_id == org_id

    team_condition = (
        and_(Document.visibility == "team", Document.team_id.in_(team_ids))
        if team_ids
        else false()
    )

    return and_(
        Chunk.org_id == org_id,
        or_(
            Document.owner_id == user_id,
            Document.visibility == "org",
            team_condition,
        ),
    )


def build_acl_sql(
    user_id: str,
    org_id: str,
    is_admin: bool,
    team_ids: List[str],
) -> Tuple[str, Dict[str, Any]]:
    """
    Build raw SQL WHERE clause predicate and parameters for PostgreSQL.
    Applied directly inside dense (pgvector) and sparse (tsvector) SQL queries.
    """
    if is_admin:
        sql = "c.org_id = :org_id"
        params = {"org_id": org_id}
        return sql, params

    if team_ids:
        sql = """(
            c.org_id = :org_id
            AND (
                d.owner_id = :user_id
                OR d.visibility = 'org'
                OR (d.visibility = 'team' AND d.team_id = ANY(:team_ids))
            )
        )"""
        params = {
            "org_id": org_id,
            "user_id": user_id,
            "team_ids": team_ids,
        }
    else:
        sql = """(
            c.org_id = :org_id
            AND (
                d.owner_id = :user_id
                OR d.visibility = 'org'
            )
        )"""
        params = {
            "org_id": org_id,
            "user_id": user_id,
        }

    return sql, params
