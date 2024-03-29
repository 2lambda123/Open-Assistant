"""Created date

Revision ID: aac6b2f66006
Revises: 35bdc1a08bb8
Create Date: 2023-01-08 21:28:27.342729

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "aac6b2f66006"
down_revision = "35bdc1a08bb8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "message_embedding",
        sa.Column("created_date", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("message_embedding", "created_date")
    # ### end Alembic commands ###
