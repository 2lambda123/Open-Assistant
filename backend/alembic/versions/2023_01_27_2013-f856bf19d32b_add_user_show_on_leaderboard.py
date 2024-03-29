"""add user.show_on_leaderboard

Revision ID: f856bf19d32b
Revises: c84fcd6900dc
Create Date: 2023-01-27 20:13:56.533374

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f856bf19d32b"
down_revision = "c84fcd6900dc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "user", sa.Column("show_on_leaderboard", sa.Boolean(), server_default=sa.text("true"), nullable=False)
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("user", "show_on_leaderboard")
    # ### end Alembic commands ###
