from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Security
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud.referral import get_referral_statistics
from app.database.crud.transaction import REAL_PAYMENT_METHODS, get_transactions_statistics
from app.database.crud.user import get_users_statistics
from app.database.models import (
    Ticket,
    TicketStatus,
    Transaction,
    TransactionType,
    User,
    UserStatus,
)

from ..dependencies import get_db_session, require_api_token


router = APIRouter()


def _kopeks_to_rubles(value: float | None) -> float:
    return round((value or 0) / 100, 2)


async def _get_overview(db: AsyncSession) -> dict[str, object]:
    total_users = await db.scalar(select(func.count()).select_from(User)) or 0
    active_users = (
        await db.scalar(select(func.count()).select_from(User).where(User.status == UserStatus.ACTIVE.value)) or 0
    )
    blocked_users = (
        await db.scalar(select(func.count()).select_from(User).where(User.status == UserStatus.BLOCKED.value)) or 0
    )

    total_balance_kopeks = await db.scalar(select(func.coalesce(func.sum(User.balance_kopeks), 0))) or 0

    pending_tickets = (
        await db.scalar(
            select(func.count())
            .select_from(Ticket)
            .where(Ticket.status.in_([TicketStatus.OPEN.value, TicketStatus.ANSWERED.value]))
        )
        or 0
    )

    today = datetime.now(UTC).date()
    today_transactions = (
        await db.scalar(
            select(func.coalesce(func.sum(func.abs(Transaction.amount_kopeks)), 0)).where(
                func.date(Transaction.created_at) == today,
                Transaction.type == TransactionType.DEPOSIT.value,
                Transaction.payment_method.in_(REAL_PAYMENT_METHODS),
            )
        )
        or 0
    )

    return {
        'users': {
            'total': total_users,
            'active': active_users,
            'blocked': blocked_users,
            'balance_kopeks': int(total_balance_kopeks),
            'balance_rubles': _kopeks_to_rubles(total_balance_kopeks),
        },
        # Subscription metrics removed alongside the VPN stack.
        'subscriptions': {
            'active': 0,
            'expired': 0,
        },
        'support': {
            'open_tickets': pending_tickets,
        },
        'payments': {
            'today_kopeks': int(today_transactions),
            'today_rubles': _kopeks_to_rubles(today_transactions),
        },
    }


@router.get(
    '/overview',
    summary='Общая статистика',
    response_description='Агрегированные показатели пользователей, саппорта и платежей',
)
async def stats_overview(
    _: object = Security(require_api_token),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    return await _get_overview(db)


@router.get(
    '/full',
    summary='Полная статистика',
    response_description='Расширенные показатели пользователей, платежей и рефералов',
)
async def stats_full(
    _: object = Security(require_api_token),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    overview = await _get_overview(db)

    users_stats = await get_users_statistics(db)
    transactions_stats = await get_transactions_statistics(
        db, start_date=datetime(2020, 1, 1, tzinfo=UTC), end_date=datetime.now(UTC)
    )
    referral_stats = await get_referral_statistics(db)

    transactions_totals = transactions_stats.get('totals', {})
    transactions_today = transactions_stats.get('today', {})

    transactions_totals = {
        **transactions_totals,
        'income_rubles': _kopeks_to_rubles(transactions_totals.get('income_kopeks')),
        'expenses_rubles': _kopeks_to_rubles(transactions_totals.get('expenses_kopeks')),
        'profit_rubles': _kopeks_to_rubles(transactions_totals.get('profit_kopeks')),
    }

    transactions_today = {
        **transactions_today,
        'income_rubles': _kopeks_to_rubles(transactions_today.get('income_kopeks')),
    }

    referral_stats = {
        **referral_stats,
        'total_paid_rubles': _kopeks_to_rubles(referral_stats.get('total_paid_kopeks')),
        'today_earnings_rubles': _kopeks_to_rubles(referral_stats.get('today_earnings_kopeks')),
        'week_earnings_rubles': _kopeks_to_rubles(referral_stats.get('week_earnings_kopeks')),
        'month_earnings_rubles': _kopeks_to_rubles(referral_stats.get('month_earnings_kopeks')),
    }

    return {
        'overview': overview,
        'users': users_stats,
        'subscriptions': {},
        'transactions': {
            **transactions_stats,
            'totals': transactions_totals,
            'today': transactions_today,
        },
        'referrals': referral_stats,
    }
