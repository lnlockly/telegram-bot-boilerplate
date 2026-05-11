"""Unique partial index on completed transactions(external_id, payment_method).

Enforces idempotency at the DB level: even if two webhook deliveries race past the
application-level FOR UPDATE check, only one completed transaction per
(external_id, payment_method) tuple can be inserted. Targets retried Telegram Stars
successful_payment events (CRITICAL #2) and any other provider that stores its
provider charge id in transactions.external_id.

Revision ID: 2e114f336cb5
Revises: 155e9677840a
Create Date: 2026-05-11
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '2e114f336cb5'
down_revision: Union[str, None] = '155e9677840a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Partial unique index — applies only to completed rows. Pending/cancelled
    # rows are allowed to share an external_id (e.g. retried payment attempts).
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_transactions_external_id_method_completed
        ON transactions (external_id, payment_method)
        WHERE is_completed = TRUE AND external_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS uq_transactions_external_id_method_completed')
