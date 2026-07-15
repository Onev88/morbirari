"""esquema inicial fase 1

Revision ID: f9df89f2c6c2
Revises: 
Create Date: 2026-07-15 17:27:01.891334
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f9df89f2c6c2'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pg_trgm y unaccent sostienen el fallback de búsqueda cuando Meilisearch no está
    # disponible. Sin unaccent, "fibrosis quistica" no encuentra "fibrosis quística".
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")

    # unaccent() no es IMMUTABLE (depende del diccionario del search_path), así que
    # Postgres la rechaza en una expresión de índice. El wrapper fija el diccionario
    # explícitamente, lo que sí la hace inmutable. Es la solución canónica.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION mr_unaccent(text) RETURNS text AS
        $$ SELECT public.unaccent('public.unaccent'::regdictionary, $1) $$
        LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
        """
    )

    op.create_table('disease',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('slug', sa.String(length=255), nullable=False),
    sa.Column('orpha_code', sa.String(length=16), nullable=False),
    sa.Column('mondo_id', sa.String(length=32), nullable=True),
    sa.Column('disease_type', sa.String(length=64), nullable=True),
    sa.Column('classification_level', sa.String(length=64), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('expert_link', sa.Text(), nullable=True),
    sa.Column('first_seen', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_seen', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('orpha_code'),
    sa.UniqueConstraint('slug')
    )
    op.create_index('ix_disease_status', 'disease', ['status'], unique=False)
    op.create_table('source',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('license_spdx', sa.String(length=64), nullable=True),
    sa.Column('attribution_text', sa.Text(), nullable=True),
    sa.Column('homepage', sa.Text(), nullable=True),
    sa.Column('redistributable', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('ingest_run',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('source_id', sa.Integer(), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('artifact_sha256', sa.String(length=64), nullable=True),
    sa.Column('source_version', sa.String(length=128), nullable=True),
    sa.Column('record_counts', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['source_id'], ['source.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('provenance',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('source_id', sa.Integer(), nullable=False),
    sa.Column('ingest_run_id', sa.Integer(), nullable=True),
    sa.Column('source_version', sa.String(length=128), nullable=True),
    sa.Column('retrieved_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('source_url', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['ingest_run_id'], ['ingest_run.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['source_id'], ['source.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('disease_content',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('disease_id', sa.UUID(), nullable=False),
    sa.Column('lang', sa.String(length=8), nullable=False),
    sa.Column('audience', sa.String(length=16), nullable=False),
    sa.Column('block_type', sa.String(length=32), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('provenance_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['disease_id'], ['disease.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['provenance_id'], ['provenance.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('disease_id', 'lang', 'block_type', name='uq_content')
    )
    op.create_index(op.f('ix_disease_content_disease_id'), 'disease_content', ['disease_id'], unique=False)
    op.create_index(op.f('ix_disease_content_lang'), 'disease_content', ['lang'], unique=False)
    op.create_table('disease_label',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('disease_id', sa.UUID(), nullable=False),
    sa.Column('lang', sa.String(length=8), nullable=False),
    sa.Column('label', sa.Text(), nullable=False),
    sa.Column('label_type', sa.String(length=16), nullable=False),
    sa.Column('provenance_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['disease_id'], ['disease.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['provenance_id'], ['provenance.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('disease_id', 'lang', 'label', 'label_type', name='uq_label')
    )
    op.create_index(op.f('ix_disease_label_disease_id'), 'disease_label', ['disease_id'], unique=False)
    op.create_index(op.f('ix_disease_label_lang'), 'disease_label', ['lang'], unique=False)
    op.create_index('ix_disease_label_lang_type', 'disease_label', ['lang', 'label_type'], unique=False)
    # Índice trigram sobre la etiqueta sin acentos: es lo que hace que el fallback
    # a pg_trgm sea utilizable y no un escaneo secuencial de 100k filas.
    op.execute(
        "CREATE INDEX ix_disease_label_trgm ON disease_label "
        "USING gin (mr_unaccent(lower(label)) gin_trgm_ops)"
    )
    op.create_table('disease_xref',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('disease_id', sa.UUID(), nullable=False),
    sa.Column('source_ns', sa.String(length=16), nullable=False),
    sa.Column('source_id', sa.String(length=64), nullable=False),
    sa.Column('relation', sa.String(length=16), nullable=False),
    sa.Column('validated', sa.Boolean(), nullable=False),
    sa.Column('provenance_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['disease_id'], ['disease.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['provenance_id'], ['provenance.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('disease_id', 'source_ns', 'source_id', name='uq_xref')
    )
    op.create_index(op.f('ix_disease_xref_disease_id'), 'disease_xref', ['disease_id'], unique=False)
    op.create_index(op.f('ix_disease_xref_source_ns'), 'disease_xref', ['source_ns'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_disease_xref_source_ns'), table_name='disease_xref')
    op.drop_index(op.f('ix_disease_xref_disease_id'), table_name='disease_xref')
    op.drop_table('disease_xref')
    op.drop_index('ix_disease_label_lang_type', table_name='disease_label')
    op.drop_index(op.f('ix_disease_label_lang'), table_name='disease_label')
    op.drop_index(op.f('ix_disease_label_disease_id'), table_name='disease_label')
    op.drop_table('disease_label')
    op.drop_index(op.f('ix_disease_content_lang'), table_name='disease_content')
    op.drop_index(op.f('ix_disease_content_disease_id'), table_name='disease_content')
    op.drop_table('disease_content')
    op.drop_table('provenance')
    op.drop_table('ingest_run')
    op.drop_table('source')
    op.drop_index('ix_disease_status', table_name='disease')
    op.drop_table('disease')
    # ### end Alembic commands ###
