import uuid
from datetime import datetime, timezone
from typing import Optional, List, Any
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Index,
    JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator
from app.db.session import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None


class VectorType(TypeDecorator):
    """Custom Vector type that maps to pgvector Vector(384) on PostgreSQL and JSON elsewhere."""
    impl = String
    cache_ok = True

    def __init__(self, dim: int = 384, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dim = dim

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and Vector is not None:
            return dialect.type_descriptor(Vector(self.dim))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        return value

    def process_result_value(self, value, dialect):
        return value


class TSVectorType(TypeDecorator):
    """Custom TSVector type that maps to TSVECTOR on PostgreSQL and Text elsewhere."""
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import TSVECTOR
            return dialect.type_descriptor(TSVECTOR())
        return dialect.type_descriptor(Text())


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    teams = relationship("Team", back_populates="organization", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="member", nullable=False)  # 'admin' / 'member'
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    organization = relationship("Organization", back_populates="users")
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="owner")
    team_memberships = relationship("TeamMember", back_populates="user", cascade="all, delete-orphan")


class Team(Base):
    __tablename__ = "teams"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)

    organization = relationship("Organization", back_populates="teams")
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="team")


class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    team_id = Column(String(36), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    team = relationship("Team", back_populates="members")
    user = relationship("User", back_populates="team_memberships")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    key_hash = Column(String(255), nullable=False, index=True)
    prefix = Column(String(16), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="api_keys")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    team_id = Column(String(36), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=False)
    visibility = Column(String(50), default="private", nullable=False)  # 'private' / 'team' / 'org'
    status = Column(String(50), default="processed", nullable=False)    # 'processing' / 'processed' / 'error'
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    organization = relationship("Organization", back_populates="documents")
    owner = relationship("User", back_populates="documents")
    team = relationship("Team", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    page = Column(Integer, nullable=True)
    text = Column(Text, nullable=False)
    embedding = Column(VectorType(384), nullable=True)
    tsv = Column(TSVectorType, nullable=True)

    document = relationship("Document", back_populates="chunks")


class QueryLog(Base):
    __tablename__ = "query_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    retrieved_chunk_ids = Column(JSON, default=list)
    scores = Column(JSON, default=list)
    latency_ms = Column(Float, nullable=False, default=0.0)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    provider = Column(String(50), default="groq")
    cache_hit = Column(Boolean, default=False)
    mode = Column(String(50), default="standard")  # 'standard' / 'agentic'
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    feedback = relationship("Feedback", back_populates="query_log", cascade="all, delete-orphan")


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    query_log_id = Column(String(36), ForeignKey("query_logs.id", ondelete="CASCADE"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)  # +1 / -1
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    query_log = relationship("QueryLog", back_populates="feedback")


class EvalCase(Base):
    __tablename__ = "eval_cases"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    question = Column(Text, nullable=False)
    expected_doc_id = Column(String(36), nullable=True)
    expected_answer = Column(Text, nullable=True)
    source = Column(String(50), default="manual")  # 'manual' / 'feedback'
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    label = Column(String(255), nullable=False)
    config = Column(JSON, default=dict)
    hit_at_k = Column(Float, default=0.0)
    mrr = Column(Float, default=0.0)
    faithfulness = Column(Float, default=0.0)
    p50_ms = Column(Float, default=0.0)
    p95_ms = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    results = relationship("EvalResult", back_populates="run", cascade="all, delete-orphan")


class EvalResult(Base):
    __tablename__ = "eval_results"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = Column(String(36), ForeignKey("eval_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    hit = Column(Boolean, default=False)
    rank = Column(Integer, nullable=True)
    faithfulness = Column(Float, default=0.0)
    latency_ms = Column(Float, default=0.0)
    answer = Column(Text, nullable=True)

    run = relationship("EvalRun", back_populates="results")


class ResponseCache(Base):
    __tablename__ = "response_cache"

    key = Column(String(64), primary_key=True)  # sha256
    user_id = Column(String(36), nullable=False, index=True)
    answer = Column(Text, nullable=False)
    citations = Column(JSON, default=list)
    corpus_version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
