"""
SQLAlchemy ORM models — full schema (Task 2).
"""
import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PresentationStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class ProviderType(str, enum.Enum):
    claude = "claude"
    openai = "openai"
    groq = "groq"
    local = "local"


# ---------------------------------------------------------------------------
# Mixins
# ---------------------------------------------------------------------------


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ---------------------------------------------------------------------------
# Tenant
# ---------------------------------------------------------------------------


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    users: Mapped[list["User"]] = relationship("User", back_populates="tenant")
    presentations: Mapped[list["Presentation"]] = relationship(
        "Presentation", back_populates="tenant"
    )
    templates: Mapped[list["Template"]] = relationship(
        "Template", back_populates="tenant"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="tenant"
    )


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="member")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user"
    )
    presentations: Mapped[list["Presentation"]] = relationship(
        "Presentation", back_populates="user"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="user"
    )

    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),)


# ---------------------------------------------------------------------------
# RefreshToken
# ---------------------------------------------------------------------------


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------


class Presentation(Base):
    __tablename__ = "presentations"

    presentation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic: Mapped[str] = mapped_column(String(5000), nullable=False)

    # Auto-detected by Industry_Classifier_Agent
    detected_industry: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    detection_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    detected_sub_sector: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    inferred_audience: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    selected_template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    selected_theme: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    compliance_context: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

    # Generated content
    schema_version: Mapped[str] = mapped_column(
        String(20), nullable=False, default="1.0.0"
    )
    total_slides: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    slides: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    design_spec: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)  # DesignAgent output
    status: Mapped[PresentationStatus] = mapped_column(
        Enum(PresentationStatus, name="presentation_status"),
        nullable=False,
        default=PresentationStatus.queued,
        index=True,
    )
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="presentations")
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="presentations")
    template: Mapped[Optional["Template"]] = relationship(
        "Template", back_populates="presentations"
    )
    versions: Mapped[list["PresentationVersion"]] = relationship(
        "PresentationVersion", back_populates="presentation"
    )
    slide_locks: Mapped[list["SlideLock"]] = relationship(
        "SlideLock", back_populates="presentation"
    )
    pipeline_executions: Mapped[list["PipelineExecution"]] = relationship(
        "PipelineExecution", back_populates="presentation"
    )
    quality_scores: Mapped[list["QualityScore"]] = relationship(
        "QualityScore", back_populates="presentation"
    )


# ---------------------------------------------------------------------------
# PresentationVersion
# ---------------------------------------------------------------------------


class PresentationVersion(Base):
    __tablename__ = "presentation_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    presentation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("presentations.presentation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    slides: Mapped[Any] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Branching support (2.6)
    parent_version: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    merge_source: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    presentation: Mapped["Presentation"] = relationship(
        "Presentation", back_populates="versions"
    )

    __table_args__ = (
        UniqueConstraint(
            "presentation_id", "version_number", name="uq_pv_presentation_version"
        ),
    )


# ---------------------------------------------------------------------------
# SlideLock
# ---------------------------------------------------------------------------


class SlideLock(Base):
    __tablename__ = "slide_locks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    presentation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("presentations.presentation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    slide_id: Mapped[str] = mapped_column(String(255), nullable=False)
    locked_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    locked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    presentation: Mapped["Presentation"] = relationship(
        "Presentation", back_populates="slide_locks"
    )


# ---------------------------------------------------------------------------
# PipelineExecution
# ---------------------------------------------------------------------------


class PipelineExecution(Base):
    __tablename__ = "pipeline_executions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    presentation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("presentations.presentation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    current_agent: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Prompt versioning fields (Task 11.5)
    prompt_id: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, index=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    prompt_metadata: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

    presentation: Mapped["Presentation"] = relationship(
        "Presentation", back_populates="pipeline_executions"
    )
    agent_states: Mapped[list["AgentState"]] = relationship(
        "AgentState", back_populates="execution"
    )
    provider_usage: Mapped[list["ProviderUsage"]] = relationship(
        "ProviderUsage", back_populates="execution"
    )
    quality_scores: Mapped[list["QualityScore"]] = relationship(
        "QualityScore", back_populates="execution"
    )


# ---------------------------------------------------------------------------
# AgentState
# ---------------------------------------------------------------------------


class AgentState(Base):
    __tablename__ = "agent_states"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[Any] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    execution: Mapped["PipelineExecution"] = relationship(
        "PipelineExecution", back_populates="agent_states"
    )


# ---------------------------------------------------------------------------
# ProviderConfig
# ---------------------------------------------------------------------------


class ProviderConfig(Base):
    __tablename__ = "provider_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    provider_type: Mapped[ProviderType] = mapped_column(
        Enum(ProviderType, name="provider_type"),
        nullable=False,
        index=True,
    )
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=4096)
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    rate_limit_per_min: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    cost_per_1k_tokens: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    health_logs: Mapped[list["ProviderHealthLog"]] = relationship(
        "ProviderHealthLog", back_populates="provider"
    )
    usage: Mapped[list["ProviderUsage"]] = relationship(
        "ProviderUsage", back_populates="provider"
    )


# ---------------------------------------------------------------------------
# ProviderHealthLog
# ---------------------------------------------------------------------------


class ProviderHealthLog(Base):
    __tablename__ = "provider_health_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("provider_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    success_rate: Mapped[float] = mapped_column(Float, nullable=False)
    avg_response_ms: Mapped[float] = mapped_column(Float, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    provider: Mapped["ProviderConfig"] = relationship(
        "ProviderConfig", back_populates="health_logs"
    )


# ---------------------------------------------------------------------------
# ProviderUsage
# ---------------------------------------------------------------------------


class ProviderUsage(Base):
    __tablename__ = "provider_usage"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("provider_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    execution: Mapped["PipelineExecution"] = relationship(
        "PipelineExecution", back_populates="provider_usage"
    )
    provider: Mapped["ProviderConfig"] = relationship(
        "ProviderConfig", back_populates="usage"
    )


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------


class Prompt(Base):
    __tablename__ = "prompts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    provider_type: Mapped[ProviderType] = mapped_column(
        Enum(ProviderType, name="provider_type"),
        nullable=False,
        index=True,
    )
    template: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("name", "version", "provider_type", name="uq_prompts_name_version_provider"),
    )


# ---------------------------------------------------------------------------
# QualityScore
# ---------------------------------------------------------------------------


class QualityScore(Base):
    __tablename__ = "quality_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    presentation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("presentations.presentation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    execution_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_executions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    content_depth: Mapped[float] = mapped_column(Float, nullable=False)
    visual_appeal: Mapped[float] = mapped_column(Float, nullable=False)
    structure_coherence: Mapped[float] = mapped_column(Float, nullable=False)
    data_accuracy: Mapped[float] = mapped_column(Float, nullable=False)
    clarity: Mapped[float] = mapped_column(Float, nullable=False)
    composite_score: Mapped[float] = mapped_column(Float, nullable=False)
    recommendations: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    presentation: Mapped["Presentation"] = relationship(
        "Presentation", back_populates="quality_scores"
    )
    execution: Mapped[Optional["PipelineExecution"]] = relationship(
        "PipelineExecution", back_populates="quality_scores"
    )


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sub_sector: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    slide_structure: Mapped[Any] = mapped_column(JSONB, nullable=False, default=dict)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tenant: Mapped[Optional["Tenant"]] = relationship(
        "Tenant", back_populates="templates"
    )
    presentations: Mapped[list["Presentation"]] = relationship(
        "Presentation", back_populates="template"
    )


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    extra_metadata: Mapped[Optional[Any]] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    tenant: Mapped[Optional["Tenant"]] = relationship(
        "Tenant", back_populates="audit_logs"
    )
    user: Mapped[Optional["User"]] = relationship(
        "User", back_populates="audit_logs"
    )
