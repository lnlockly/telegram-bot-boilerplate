"""processed_webhook_events table for replay protection.

Stores (provider, event_id) of every webhook we've already credited. A captured
valid webhook replayed against the bot will hit the unique constraint and be
rejected (HIGH #8). Mirrors the SQLAlchemy ProcessedWebhookEvent model.

Revision ID: 37ebcf6eea38
Revises: 2e114f336cb5
Create Date: 2026-05-11
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '37ebcf6eea38'
down_revision: Union[str, None] = '2e114f336cb5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'processed_webhook_events',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('provider', sa.String(32), nullable=False),
        sa.Column('event_id', sa.String(255), nullable=False),
        sa.Column(
            'processed_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.UniqueConstraint('provider', 'event_id', name='uq_processed_webhook_events_provider_event'),
    )
    op.create_index(
        'ix_processed_webhook_events_processed_at',
        'processed_webhook_events',
        ['processed_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_processed_webhook_events_processed_at', table_name='processed_webhook_events')
    op.drop_table('processed_webhook_events')
