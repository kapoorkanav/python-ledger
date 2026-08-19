"""outbox reliability, per-currency external accounts, hot-path indexes

Revision ID: ebe31fe867c1
Revises: a5b102707601
Create Date: 2026-08-18 12:53:55.567567

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ebe31fe867c1'
down_revision: Union[str, Sequence[str], None] = 'a5b102707601'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- outbox reliability -------------------------------------------------
    op.add_column("outbox_events", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("outbox_events", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("outbox_events", sa.Column("failed", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("outbox_events", sa.Column("last_error", sa.String(), nullable=True))

    # --- one external clearing account per currency -------------------------
    op.execute("UPDATE accounts SET name = 'EXTERNAL:USD' WHERE name = 'EXTERNAL'")
    op.create_index(
        "uq_external_account_per_currency",
        "accounts",
        ["name"],
        unique=True,
        postgresql_where=sa.text("name LIKE 'EXTERNAL:%'"),
    )

    # --- hot-path index -------------------------------------------------
    # get_balance() aggregates by account_id on every write and every read.
    op.create_index("ix_ledger_entries_account_id", "ledger_entries", ["account_id"])
    # The relay only ever polls for rows still awaiting delivery.
    op.create_index(
        "ix_outbox_events_pending",
        "outbox_events",
        ["created_at"],
        postgresql_where=sa.text("published = false AND failed = false"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_outbox_events_pending", table_name="outbox_events")
    op.drop_index("ix_ledger_entries_account_id", table_name="ledger_entries")
    op.drop_index("uq_external_account_per_currency", table_name="accounts")
    op.execute("UPDATE accounts SET name = 'EXTERNAL' WHERE name = 'EXTERNAL:USD'")
    op.drop_column("outbox_events", "last_error")
    op.drop_column("outbox_events", "failed")
    op.drop_column("outbox_events", "attempts")
    op.drop_column("outbox_events", "published_at")
