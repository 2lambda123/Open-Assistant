"""add_journal_table

Revision ID: 3358eb6834e6
Revises: 067c4002f2d9
Create Date: 2022-12-27 14:44:59.483868

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "3358eb6834e6"
down_revision = "067c4002f2d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "journal",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_date", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "event_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("person_id", sqlmodel.sql.sqltypes.GUID(), nullable=True),
        sa.Column("post_id", sqlmodel.sql.sqltypes.GUID(), nullable=True),
        sa.Column("api_client_id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column("event_type", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
        sa.ForeignKeyConstraint(
            ["api_client_id"],
            ["api_client.id"],
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["person.id"],
        ),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["post.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_journal_person_id"), "journal", ["person_id"], unique=False)
    op.create_table(
        "journal_integration",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("last_run", sa.DateTime(), nullable=True),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(length=512), nullable=False),
        sa.Column("last_journal_id", sqlmodel.sql.sqltypes.GUID(), nullable=True),
        sa.Column("last_error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("next_run", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["last_journal_id"],
            ["journal.id"],
        ),
        sa.PrimaryKeyConstraint("id", "description"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("journal_integration")
    op.drop_index(op.f("ix_journal_person_id"), table_name="journal")
    op.drop_table("journal")
    # ### end Alembic commands ###
