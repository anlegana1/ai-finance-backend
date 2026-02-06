"""add default_currency to users

Revision ID: 20260206_0001
Revises: 
Create Date: 2026-02-06

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260206_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("default_currency", sa.Text(), nullable=False, server_default="CAD"),
        schema="public",
    )

    op.create_check_constraint(
        "users_default_currency_check",
        "users",
        "default_currency in ('CAD','USD','COP')",
        schema="public",
    )


def downgrade() -> None:
    op.drop_constraint(
        "users_default_currency_check",
        "users",
        type_="check",
        schema="public",
    )

    op.drop_column("users", "default_currency", schema="public")
