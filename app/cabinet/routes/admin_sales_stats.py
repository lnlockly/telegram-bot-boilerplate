"""Admin routes for sales statistics in cabinet."""

from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud.transaction import REAL_PAYMENT_METHODS
from app.database.models import (
    PaymentMethod,
    Transaction,
    TransactionType,
    User,
)

from ..dependencies import get_cabinet_db, require_permission


logger = structlog.get_logger(__name__)

router = APIRouter(prefix='/admin/stats/sales', tags=['Cabinet Admin Sales Stats'])


# ============ Helpers ============

MAX_PERIOD_DAYS = 730  # 2 years max


def _parse_period(
    days: int | None,
    start_date: str | None,
    end_date: str | None,
) -> tuple[datetime, datetime]:
    """Parse period from preset days or custom date range."""
    now = datetime.now(UTC)
    if start_date and end_date:
        try:
            start = datetime.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Invalid start_date format',
            )
        try:
            end = datetime.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Invalid end_date format',
            )
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        if start > end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='start_date must be before end_date',
            )
        if (end - start).days > MAX_PERIOD_DAYS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Date range cannot exceed {MAX_PERIOD_DAYS} days',
            )
        return start, end.replace(hour=23, minute=59, second=59)
    if days is not None and days > 0:
        days = min(days, MAX_PERIOD_DAYS)
        start = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    return datetime(2020, 1, 1, tzinfo=UTC), now


# ============ Summary Schemas ============


class SalesSummary(BaseModel):
    """Summary stats for the top cards."""

    total_revenue_kopeks: int
    manual_topup_kopeks: int
    active_subscriptions: int
    active_trials: int
    new_trials: int
    trial_to_paid_conversion: float
    renewals_count: int
    addon_revenue_kopeks: int


# ============ Summary Endpoint ============


@router.get('/summary', response_model=SalesSummary)
async def get_sales_summary(
    days: int | None = Query(default=30, description='Preset period in days (7, 30, 90, 0=all)'),
    start_date: str | None = Query(default=None, description='Custom start date ISO format'),
    end_date: str | None = Query(default=None, description='Custom end date ISO format'),
    admin: User = Depends(require_permission('sales_stats:read')),
    db: AsyncSession = Depends(get_cabinet_db),
) -> SalesSummary:
    """Get summary statistics for sales dashboard cards."""
    # Subscription/tariff/conversion models removed; return empty stub.
    _ = _parse_period(days, start_date, end_date)
    return SalesSummary(
        total_revenue_kopeks=0,
        manual_topup_kopeks=0,
        active_subscriptions=0,
        active_trials=0,
        new_trials=0,
        trial_to_paid_conversion=0.0,
        renewals_count=0,
        addon_revenue_kopeks=0,
    )


# ============ Trials Schemas ============


class ProviderBreakdownItem(BaseModel):
    provider: str
    count: int


class DailyTrialItem(BaseModel):
    date: str
    registrations: int
    trials: int


class TrialsStatsResponse(BaseModel):
    total_trials: int
    total_registrations: int
    conversion_rate: float
    avg_trial_duration_days: float
    by_provider: list[ProviderBreakdownItem]
    daily: list[DailyTrialItem]


# ============ Trials Endpoint ============


@router.get('/trials', response_model=TrialsStatsResponse)
async def get_trials_stats(
    days: int | None = Query(default=30),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    admin: User = Depends(require_permission('sales_stats:read')),
    db: AsyncSession = Depends(get_cabinet_db),
) -> TrialsStatsResponse:
    """Get trial registration statistics with provider breakdown."""
    # Subscription/conversion models removed; return empty stub.
    _ = _parse_period(days, start_date, end_date)
    return TrialsStatsResponse(
        total_trials=0,
        total_registrations=0,
        conversion_rate=0.0,
        avg_trial_duration_days=0.0,
        by_provider=[],
        daily=[],
    )


# ============ Sales Schemas ============


class SalesByTariffItem(BaseModel):
    tariff_id: int
    tariff_name: str
    count: int


class SalesByPeriodItem(BaseModel):
    period_days: int
    count: int


class DailySalesItem(BaseModel):
    date: str
    count: int
    revenue_kopeks: int


class DailyTariffSalesItem(BaseModel):
    date: str
    tariff_name: str
    count: int


class SalesStatsResponse(BaseModel):
    total_sales: int
    total_revenue_kopeks: int
    avg_order_kopeks: int
    top_tariff_name: str
    by_tariff: list[SalesByTariffItem]
    by_period: list[SalesByPeriodItem]
    daily: list[DailySalesItem]
    daily_by_tariff: list[DailyTariffSalesItem]


# ============ Sales Endpoint ============


@router.get('/subscriptions', response_model=SalesStatsResponse)
async def get_sales_stats(
    days: int | None = Query(default=30),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    admin: User = Depends(require_permission('sales_stats:read')),
    db: AsyncSession = Depends(get_cabinet_db),
) -> SalesStatsResponse:
    """Get subscription sales statistics."""
    # Subscription/Tariff models removed; return empty stub.
    _ = _parse_period(days, start_date, end_date)
    return SalesStatsResponse(
        total_sales=0,
        total_revenue_kopeks=0,
        avg_order_kopeks=0,
        top_tariff_name='-',
        by_tariff=[],
        by_period=[],
        daily=[],
        daily_by_tariff=[],
    )


# ============ Renewals Schemas ============


class DailyRenewalItem(BaseModel):
    date: str
    count: int


class RenewalPeriodStats(BaseModel):
    count: int
    revenue_kopeks: int


class RenewalChange(BaseModel):
    absolute: int
    percent: float
    trend: str


class RenewalsStatsResponse(BaseModel):
    total_renewals: int
    total_revenue_kopeks: int
    renewal_rate: float
    current_period: RenewalPeriodStats
    previous_period: RenewalPeriodStats
    change: RenewalChange
    daily: list[DailyRenewalItem]


# ============ Renewals Endpoint ============


@router.get('/renewals', response_model=RenewalsStatsResponse)
async def get_renewals_stats(
    days: int | None = Query(default=30),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    admin: User = Depends(require_permission('sales_stats:read')),
    db: AsyncSession = Depends(get_cabinet_db),
) -> RenewalsStatsResponse:
    """Get renewal statistics with period comparison."""
    try:
        period_start, period_end = _parse_period(days, start_date, end_date)
        is_all_time = days is not None and days == 0

        if is_all_time:
            repeat_users_subquery = (
                select(Transaction.user_id)
                .where(
                    and_(
                        Transaction.type == TransactionType.SUBSCRIPTION_PAYMENT.value,
                        Transaction.is_completed == True,
                    )
                )
                .group_by(Transaction.user_id)
                .having(func.count(Transaction.id) > 1)
            )
            existing_users_subquery = repeat_users_subquery

            current_result = await db.execute(
                select(
                    func.count(Transaction.id).label('count'),
                    func.coalesce(func.sum(func.abs(Transaction.amount_kopeks)), 0).label('revenue'),
                ).where(
                    and_(
                        Transaction.type == TransactionType.SUBSCRIPTION_PAYMENT.value,
                        Transaction.is_completed == True,
                        Transaction.user_id.in_(repeat_users_subquery),
                    )
                )
            )
            current = current_result.one()
            current_count = current.count
            current_revenue = current.revenue

            prev = type('Row', (), {'count': 0, 'revenue': 0})()
        else:
            period_length = period_end - period_start
            prev_start = period_start - period_length
            prev_end = period_start

            existing_users_subquery = (
                select(Transaction.user_id)
                .where(
                    and_(
                        Transaction.type == TransactionType.SUBSCRIPTION_PAYMENT.value,
                        Transaction.is_completed == True,
                        Transaction.created_at < period_start,
                    )
                )
                .distinct()
            )

            current_result = await db.execute(
                select(
                    func.count(Transaction.id).label('count'),
                    func.coalesce(func.sum(func.abs(Transaction.amount_kopeks)), 0).label('revenue'),
                ).where(
                    and_(
                        Transaction.type == TransactionType.SUBSCRIPTION_PAYMENT.value,
                        Transaction.is_completed == True,
                        Transaction.created_at >= period_start,
                        Transaction.created_at <= period_end,
                        Transaction.user_id.in_(existing_users_subquery),
                    )
                )
            )
            current = current_result.one()
            current_count = current.count
            current_revenue = current.revenue

            prev_existing_subquery = (
                select(Transaction.user_id)
                .where(
                    and_(
                        Transaction.type == TransactionType.SUBSCRIPTION_PAYMENT.value,
                        Transaction.is_completed == True,
                        Transaction.created_at < prev_start,
                    )
                )
                .distinct()
            )
            prev_result = await db.execute(
                select(
                    func.count(Transaction.id).label('count'),
                    func.coalesce(func.sum(func.abs(Transaction.amount_kopeks)), 0).label('revenue'),
                ).where(
                    and_(
                        Transaction.type == TransactionType.SUBSCRIPTION_PAYMENT.value,
                        Transaction.is_completed == True,
                        Transaction.created_at >= prev_start,
                        Transaction.created_at <= prev_end,
                        Transaction.user_id.in_(prev_existing_subquery),
                    )
                )
            )
            prev = prev_result.one()

        if prev.count > 0:
            change_percent = round(((current_count - prev.count) / prev.count) * 100, 1)
        else:
            change_percent = 100.0 if current_count > 0 else 0.0

        if change_percent > 0:
            trend = 'up'
        elif change_percent < 0:
            trend = 'down'
        else:
            trend = 'stable'

        total_sub_payments_result = await db.execute(
            select(func.count(Transaction.id)).where(
                and_(
                    Transaction.type == TransactionType.SUBSCRIPTION_PAYMENT.value,
                    Transaction.is_completed == True,
                    Transaction.created_at >= period_start,
                    Transaction.created_at <= period_end,
                )
            )
        )
        total_sub_payments = total_sub_payments_result.scalar() or 0
        renewal_rate = round((current_count / total_sub_payments * 100), 1) if total_sub_payments > 0 else 0.0

        daily_query = await db.execute(
            select(
                func.date(Transaction.created_at).label('date'),
                func.count(Transaction.id).label('count'),
            )
            .where(
                and_(
                    Transaction.type == TransactionType.SUBSCRIPTION_PAYMENT.value,
                    Transaction.is_completed == True,
                    Transaction.created_at >= period_start,
                    Transaction.created_at <= period_end,
                    Transaction.user_id.in_(existing_users_subquery),
                )
            )
            .group_by(func.date(Transaction.created_at))
            .order_by(func.date(Transaction.created_at))
        )
        daily = [
            DailyRenewalItem(
                date=row.date.isoformat() if hasattr(row.date, 'isoformat') else str(row.date),
                count=row.count,
            )
            for row in daily_query
        ]

        return RenewalsStatsResponse(
            total_renewals=current_count,
            total_revenue_kopeks=current_revenue,
            renewal_rate=renewal_rate,
            current_period=RenewalPeriodStats(count=current_count, revenue_kopeks=current_revenue),
            previous_period=RenewalPeriodStats(count=prev.count, revenue_kopeks=prev.revenue),
            change=RenewalChange(
                absolute=current_count - prev.count,
                percent=change_percent,
                trend=trend,
            ),
            daily=daily,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error('Failed to get renewals stats', error=e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Failed to load renewals statistics',
        )


# ============ Add-ons Schemas ============


class AddonByPackageItem(BaseModel):
    traffic_gb: int
    count: int


class DailyAddonItem(BaseModel):
    date: str
    count: int
    total_gb: int


class DailyDeviceItem(BaseModel):
    date: str
    count: int


class AddonsStatsResponse(BaseModel):
    total_purchases: int
    total_gb_purchased: int
    addon_revenue_kopeks: int
    device_purchases: int
    device_revenue_kopeks: int
    by_package: list[AddonByPackageItem]
    daily: list[DailyAddonItem]
    daily_devices: list[DailyDeviceItem]


# ============ Add-ons Endpoint ============


@router.get('/addons', response_model=AddonsStatsResponse)
async def get_addons_stats(
    days: int | None = Query(default=30),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    admin: User = Depends(require_permission('sales_stats:read')),
    db: AsyncSession = Depends(get_cabinet_db),
) -> AddonsStatsResponse:
    """Get add-on purchase statistics."""
    # TrafficPurchase model removed; return empty stub.
    _ = _parse_period(days, start_date, end_date)
    return AddonsStatsResponse(
        total_purchases=0,
        total_gb_purchased=0,
        addon_revenue_kopeks=0,
        device_purchases=0,
        device_revenue_kopeks=0,
        by_package=[],
        daily=[],
        daily_devices=[],
    )


# ============ Deposits Schemas ============


class DepositByMethodItem(BaseModel):
    method: str
    count: int
    amount_kopeks: int


class DailyDepositItem(BaseModel):
    date: str
    count: int
    amount_kopeks: int


class DailyDepositByMethodItem(BaseModel):
    date: str
    method: str
    amount_kopeks: int


class DepositsStatsResponse(BaseModel):
    total_deposits: int
    total_amount_kopeks: int
    avg_deposit_kopeks: int
    by_method: list[DepositByMethodItem]
    daily: list[DailyDepositItem]
    daily_by_method: list[DailyDepositByMethodItem]


# ============ Deposits Endpoint ============


@router.get('/deposits', response_model=DepositsStatsResponse)
async def get_deposits_stats(
    days: int | None = Query(default=30),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    admin: User = Depends(require_permission('sales_stats:read')),
    db: AsyncSession = Depends(get_cabinet_db),
) -> DepositsStatsResponse:
    """Get deposit statistics with payment method breakdown."""
    try:
        period_start, period_end = _parse_period(days, start_date, end_date)

        methods_with_manual = [*REAL_PAYMENT_METHODS, PaymentMethod.MANUAL.value]
        base_filter = and_(
            Transaction.type.in_([TransactionType.DEPOSIT.value, TransactionType.SUBSCRIPTION_PAYMENT.value]),
            Transaction.is_completed == True,
            Transaction.payment_method.in_(methods_with_manual),
            Transaction.created_at >= period_start,
            Transaction.created_at <= period_end,
        )

        totals_result = await db.execute(
            select(
                func.count(Transaction.id).label('count'),
                func.coalesce(func.sum(func.abs(Transaction.amount_kopeks)), 0).label('amount'),
            ).where(base_filter)
        )
        totals = totals_result.one()
        total_deposits = totals.count
        total_amount = totals.amount
        avg_deposit = total_amount // total_deposits if total_deposits > 0 else 0

        by_method_query = await db.execute(
            select(
                Transaction.payment_method.label('method'),
                func.count(Transaction.id).label('count'),
                func.coalesce(func.sum(func.abs(Transaction.amount_kopeks)), 0).label('amount'),
            )
            .where(base_filter)
            .group_by(Transaction.payment_method)
            .order_by(func.sum(func.abs(Transaction.amount_kopeks)).desc())
        )
        by_method = [
            DepositByMethodItem(method=row.method or 'unknown', count=row.count, amount_kopeks=row.amount)
            for row in by_method_query
        ]

        daily_query = await db.execute(
            select(
                func.date(Transaction.created_at).label('date'),
                func.count(Transaction.id).label('count'),
                func.coalesce(func.sum(func.abs(Transaction.amount_kopeks)), 0).label('amount'),
            )
            .where(base_filter)
            .group_by(func.date(Transaction.created_at))
            .order_by(func.date(Transaction.created_at))
        )
        daily = [
            DailyDepositItem(
                date=row.date.isoformat() if hasattr(row.date, 'isoformat') else str(row.date),
                count=row.count,
                amount_kopeks=row.amount,
            )
            for row in daily_query
        ]

        daily_by_method_query = await db.execute(
            select(
                func.date(Transaction.created_at).label('date'),
                Transaction.payment_method.label('method'),
                func.coalesce(func.sum(func.abs(Transaction.amount_kopeks)), 0).label('amount'),
            )
            .where(base_filter)
            .group_by(func.date(Transaction.created_at), Transaction.payment_method)
            .order_by(func.date(Transaction.created_at), Transaction.payment_method)
        )
        daily_by_method = [
            DailyDepositByMethodItem(
                date=row.date.isoformat() if hasattr(row.date, 'isoformat') else str(row.date),
                method=row.method or 'unknown',
                amount_kopeks=row.amount,
            )
            for row in daily_by_method_query
        ]

        return DepositsStatsResponse(
            total_deposits=total_deposits,
            total_amount_kopeks=total_amount,
            avg_deposit_kopeks=avg_deposit,
            by_method=by_method,
            daily=daily,
            daily_by_method=daily_by_method,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error('Failed to get deposits stats', error=e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Failed to load deposits statistics',
        )
