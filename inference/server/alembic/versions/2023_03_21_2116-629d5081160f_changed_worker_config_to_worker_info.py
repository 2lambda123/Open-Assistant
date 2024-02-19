"""changed worker config to worker info

Revision ID: 629d5081160f
Revises: 7d5be54acd49
Create Date: 2023-03-21 21:16:57.999842

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "629d5081160f"
down_revision = "7d5be54acd49"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("worker_event", sa.Column("worker_info", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.drop_column("worker_event", "worker_config")
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "worker_event",
        sa.Column("worker_config", postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    )
    op.drop_column("worker_event", "worker_info")
    # ### end Alembic commands ###
