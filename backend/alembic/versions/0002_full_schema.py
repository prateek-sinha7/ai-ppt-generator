"""Full schema migration

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-02 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enums ────────────────────────────────────────────────────────────────
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE presentation_status AS ENUM (
                'queued', 'processing', 'completed', 'failed', 'cancelled'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE provider_type AS ENUM (
                'claude', 'openai', 'groq', 'local'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    # ── users ────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("role", sa.String(50), nullable=False, server_default="member"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_email", "users", ["email"])

    # ── refresh_tokens ───────────────────────────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index(
        "ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True
    )

    # ── templates ────────────────────────────────────────────────────────────
    op.create_table(
        "templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("industry", sa.String(255), nullable=False),
        sa.Column("sub_sector", sa.String(255), nullable=True),
        sa.Column(
            "slide_structure",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("usage_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_templates_tenant_id", "templates", ["tenant_id"])
    op.create_index("ix_templates_industry", "templates", ["industry"])
    op.create_index("ix_templates_is_system", "templates", ["is_system"])

    # ── presentations ────────────────────────────────────────────────────────
    op.create_table(
        "presentations",
        sa.Column(
            "presentation_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("topic", sa.String(500), nullable=False),
        # Auto-detected fields
        sa.Column("detected_industry", sa.String(255), nullable=True),
        sa.Column("detection_confidence", sa.Float, nullable=True),
        sa.Column("detected_sub_sector", sa.String(255), nullable=True),
        sa.Column("inferred_audience", sa.String(100), nullable=True),
        sa.Column(
            "selected_template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("selected_theme", sa.String(100), nullable=True),
        sa.Column(
            "compliance_context",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        # Generated content
        sa.Column("schema_version", sa.String(20), nullable=False, server_default="1.0.0"),
        sa.Column("total_slides", sa.Integer, nullable=True),
        sa.Column(
            "slides",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "queued", "processing", "completed", "failed", "cancelled",
                name="presentation_status",
                create_type=False,
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("quality_score", sa.Float, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_presentations_user_id", "presentations", ["user_id"])
    op.create_index("ix_presentations_tenant_id", "presentations", ["tenant_id"])
    op.create_index("ix_presentations_status", "presentations", ["status"])
    op.create_index("ix_presentations_created_at", "presentations", ["created_at"])
    op.create_index(
        "ix_presentations_selected_template_id",
        "presentations",
        ["selected_template_id"],
    )

    # ── presentation_versions ────────────────────────────────────────────────
    op.create_table(
        "presentation_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "presentation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("presentations.presentation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column(
            "slides",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Branching support (2.6)
        sa.Column("parent_version", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("merge_source", postgresql.UUID(as_uuid=True), nullable=True),
        sa.UniqueConstraint(
            "presentation_id", "version_number", name="uq_pv_presentation_version"
        ),
    )
    op.create_index(
        "ix_presentation_versions_presentation_id",
        "presentation_versions",
        ["presentation_id"],
    )
    op.create_index(
        "ix_presentation_versions_created_by",
        "presentation_versions",
        ["created_by"],
    )

    # ── slide_locks ──────────────────────────────────────────────────────────
    op.create_table(
        "slide_locks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "presentation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("presentations.presentation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slide_id", sa.String(255), nullable=False),
        sa.Column(
            "locked_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "locked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_slide_locks_presentation_id", "slide_locks", ["presentation_id"])
    op.create_index("ix_slide_locks_locked_by", "slide_locks", ["locked_by"])
    op.create_index("ix_slide_locks_expires_at", "slide_locks", ["expires_at"])

    # ── pipeline_executions ──────────────────────────────────────────────────
    op.create_table(
        "pipeline_executions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "presentation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("presentations.presentation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(50), nullable=False, server_default="queued"),
        sa.Column("current_agent", sa.String(100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_pipeline_executions_presentation_id",
        "pipeline_executions",
        ["presentation_id"],
    )
    op.create_index(
        "ix_pipeline_executions_status", "pipeline_executions", ["status"]
    )

    # ── agent_states ─────────────────────────────────────────────────────────
    op.create_table(
        "agent_states",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "execution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column(
            "state",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_agent_states_execution_id", "agent_states", ["execution_id"])
    op.create_index("ix_agent_states_agent_name", "agent_states", ["agent_name"])

    # ── provider_configs ─────────────────────────────────────────────────────
    op.create_table(
        "provider_configs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "provider_type",
            postgresql.ENUM(
                "claude", "openai", "groq", "local",
                name="provider_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("max_tokens", sa.Integer, nullable=False, server_default="4096"),
        sa.Column("temperature", sa.Float, nullable=False, server_default="0.7"),
        sa.Column("rate_limit_per_min", sa.Integer, nullable=False, server_default="60"),
        sa.Column("cost_per_1k_tokens", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_provider_configs_provider_type", "provider_configs", ["provider_type"]
    )
    op.create_index(
        "ix_provider_configs_is_active", "provider_configs", ["is_active"]
    )

    # ── provider_health_logs ─────────────────────────────────────────────────
    op.create_table(
        "provider_health_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "provider_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("provider_configs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("success_rate", sa.Float, nullable=False),
        sa.Column("avg_response_ms", sa.Float, nullable=False),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_provider_health_logs_provider_id", "provider_health_logs", ["provider_id"]
    )
    op.create_index(
        "ix_provider_health_logs_checked_at", "provider_health_logs", ["checked_at"]
    )

    # ── provider_usage ───────────────────────────────────────────────────────
    op.create_table(
        "provider_usage",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "execution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "provider_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("provider_configs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("prompt_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float, nullable=False, server_default="0.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_provider_usage_execution_id", "provider_usage", ["execution_id"]
    )
    op.create_index(
        "ix_provider_usage_provider_id", "provider_usage", ["provider_id"]
    )

    # ── prompts ──────────────────────────────────────────────────────────────
    op.create_table(
        "prompts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "provider_type",
            postgresql.ENUM(
                "claude", "openai", "groq", "local",
                name="provider_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("template", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "name", "version", "provider_type", name="uq_prompts_name_version_provider"
        ),
    )
    op.create_index("ix_prompts_provider_type", "prompts", ["provider_type"])
    op.create_index("ix_prompts_is_active", "prompts", ["is_active"])

    # ── quality_scores ───────────────────────────────────────────────────────
    op.create_table(
        "quality_scores",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "presentation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("presentations.presentation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "execution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_executions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("content_depth", sa.Float, nullable=False),
        sa.Column("visual_appeal", sa.Float, nullable=False),
        sa.Column("structure_coherence", sa.Float, nullable=False),
        sa.Column("data_accuracy", sa.Float, nullable=False),
        sa.Column("clarity", sa.Float, nullable=False),
        sa.Column("composite_score", sa.Float, nullable=False),
        sa.Column(
            "recommendations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_quality_scores_presentation_id", "quality_scores", ["presentation_id"]
    )
    op.create_index(
        "ix_quality_scores_execution_id", "quality_scores", ["execution_id"]
    )

    # ── audit_logs ───────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_resource_type", "audit_logs", ["resource_type"])

    # ── Row-Level Security policies ──────────────────────────────────────────
    # Enable RLS on multi-tenant tables
    op.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE presentations ENABLE ROW LEVEL SECURITY")

    # tenants: each row visible only to members of that tenant
    op.execute(
        """
        CREATE POLICY tenant_isolation ON tenants
            USING (id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )

    # users: visible only within the same tenant
    op.execute(
        """
        CREATE POLICY tenant_isolation ON users
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )

    # presentations: visible only within the same tenant
    op.execute(
        """
        CREATE POLICY tenant_isolation ON presentations
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )


def downgrade() -> None:
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON presentations")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON users")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenants")

    op.execute("ALTER TABLE presentations DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenants DISABLE ROW LEVEL SECURITY")

    # Drop tables in reverse dependency order
    op.drop_table("audit_logs")
    op.drop_table("quality_scores")
    op.drop_table("prompts")
    op.drop_table("provider_usage")
    op.drop_table("provider_health_logs")
    op.drop_table("provider_configs")
    op.drop_table("agent_states")
    op.drop_table("pipeline_executions")
    op.drop_table("slide_locks")
    op.drop_table("presentation_versions")
    op.drop_table("presentations")
    op.drop_table("templates")
    op.drop_table("refresh_tokens")
    op.drop_table("users")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS presentation_status")
    op.execute("DROP TYPE IF EXISTS provider_type")
