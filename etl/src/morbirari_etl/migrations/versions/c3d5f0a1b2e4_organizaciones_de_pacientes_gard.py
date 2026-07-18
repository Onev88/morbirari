"""organizaciones de pacientes (GARD)

Revision ID: c3d5f0a1b2e4
Revises: 194f5c3a69c6
Create Date: 2026-07-17

Fundaciones y asociaciones de pacientes por enfermedad, de GARD (NCATS/NIH, dominio
público). Es apoyo e información, no atención médica (ADR 0006, regla 17).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d5f0a1b2e4"
down_revision: Union[str, None] = "194f5c3a69c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organization",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_ns", sa.String(length=16), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("website", sa.Text(), nullable=True),
        sa.Column("country", sa.String(length=64), nullable=True),
        sa.Column("patient_registry_url", sa.Text(), nullable=True),
        sa.Column("expert_directory_url", sa.Text(), nullable=True),
        sa.Column("record_type", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("provenance_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["provenance_id"], ["provenance.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_ns", "source_id", name="uq_organization"),
    )
    op.create_index(op.f("ix_organization_source_ns"), "organization", ["source_ns"], unique=False)

    op.create_table(
        "disease_organization",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("disease_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("match_method", sa.String(length=32), nullable=False),
        sa.Column("provenance_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["disease_id"], ["disease.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provenance_id"], ["provenance.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("disease_id", "organization_id", name="uq_disease_organization"),
    )
    op.create_index(
        op.f("ix_disease_organization_disease_id"),
        "disease_organization",
        ["disease_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_disease_organization_disease_id"), table_name="disease_organization")
    op.drop_table("disease_organization")
    op.drop_index(op.f("ix_organization_source_ns"), table_name="organization")
    op.drop_table("organization")
