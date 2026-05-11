"""Account merge service.

Merges two user accounts (e.g. when a Telegram user later signs in with the
same email and they need to be linked). The original VPN bot also moved
subscriptions and resynced RemnaWave; that logic has been stripped here.

What still happens during a merge:
- OAuth ids, telegram_id and email/password are transferred from secondary
  to primary (with the proper unique-constraint-safe two-step pattern)
- Balances are summed, restriction flags merged
- Payments, transactions, referrals, tickets, polls, contests, promo
  groups, ads, etc. are reassigned to primary
- Secondary is marked DELETED and its unique fields cleared

TODO(boilerplate): if your product has external resources tied to a user,
plug their re-binding here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

import structlog
from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud.user import OAUTH_PROVIDER_COLUMNS, get_user_by_id
from app.database.models import (
    AccessPolicy,
    AdminAuditLog,
    AdminRole,
    AdvertisingCampaign,
    AdvertisingCampaignRegistration,
    BroadcastHistory,
    ButtonClickLog,
    CabinetRefreshToken,
    CloudPaymentsPayment,
    ContestAttempt,
    CryptoBotPayment,
    DiscountOffer,
    FreekassaPayment,
    HeleketPayment,
    KassaAiPayment,
    MulenPayPayment,
    NewsArticle,
    Pal24Payment,
    PartnerApplication,
    PartnerStatus,
    PinnedMessage,
    PlategaPayment,
    Poll,
    PollResponse,
    PromoCode,
    PromoCodeUse,
    PromoOfferLog,
    PromoOfferTemplate,
    ReferralContest,
    ReferralContestEvent,
    ReferralEarning,
    RioPayPayment,
    SavedPaymentMethod,
    SentNotification,
    SeverPayPayment,
    SupportAuditLog,
    Ticket,
    TicketMessage,
    TicketNotification,
    Transaction,
    User,
    UserMessage,
    UserPromoGroup,
    UserRole,
    UserStatus,
    WataPayment,
    WelcomeText,
    WheelSpin,
    WithdrawalRequest,
    YooKassaPayment,
)


logger = structlog.get_logger(__name__)

_OAUTH_FIELDS: tuple[str, ...] = tuple(OAUTH_PROVIDER_COLUMNS.values())

_PAYMENT_MODELS: tuple[type, ...] = (
    CloudPaymentsPayment,
    CryptoBotPayment,
    FreekassaPayment,
    HeleketPayment,
    KassaAiPayment,
    MulenPayPayment,
    Pal24Payment,
    PlategaPayment,
    RioPayPayment,
    SeverPayPayment,
    WataPayment,
    YooKassaPayment,
)

_PARTNER_STATUS_PRIORITY: dict[str, int] = {
    PartnerStatus.NONE.value: 0,
    PartnerStatus.REJECTED.value: 1,
    PartnerStatus.PENDING.value: 2,
    PartnerStatus.APPROVED.value: 3,
}


def compute_auth_methods(user: User) -> list[str]:
    methods: list[str] = []
    if user.telegram_id:
        methods.append('telegram')
    if user.email and user.password_hash:
        methods.append('email')
    for provider, column in OAUTH_PROVIDER_COLUMNS.items():
        if getattr(user, column, None):
            methods.append(provider)
    return methods


def _build_user_preview(user: User) -> dict[str, Any]:
    return {
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'email': user.email,
        'auth_methods': compute_auth_methods(user),
        'balance_kopeks': user.balance_kopeks,
        # Subscriptions removed in boilerplate.
        'subscription': None,
        'subscriptions_count': 0,
        'created_at': user.created_at,
    }


async def get_merge_preview(
    db: AsyncSession,
    primary_user_id: int,
    secondary_user_id: int,
) -> dict[str, Any]:
    if primary_user_id == secondary_user_id:
        raise ValueError('primary_user_id и secondary_user_id не могут совпадать')
    primary = await get_user_by_id(db, primary_user_id)
    secondary = await get_user_by_id(db, secondary_user_id)
    if not primary:
        raise ValueError(f'Основной пользователь (id={primary_user_id}) не найден')
    if not secondary:
        raise ValueError(f'Вторичный пользователь (id={secondary_user_id}) не найден')
    return {
        'primary': _build_user_preview(primary),
        'secondary': _build_user_preview(secondary),
    }


async def execute_merge(
    db: AsyncSession,
    primary_user_id: int,
    secondary_user_id: int,
    keep_subscription_from: Literal['primary', 'secondary'] = 'primary',
    provider: str | None = None,
    provider_id: str | None = None,
) -> User:
    """Atomic account merge. Caller manages commit/rollback."""
    if primary_user_id == secondary_user_id:
        raise ValueError('primary_user_id и secondary_user_id не могут совпадать')

    primary = await get_user_by_id(db, primary_user_id)
    secondary = await get_user_by_id(db, secondary_user_id)

    if not primary:
        raise ValueError(f'Основной пользователь (id={primary_user_id}) не найден')
    if primary.status == UserStatus.DELETED.value:
        raise ValueError(f'Основной пользователь (id={primary_user_id}) удалён')
    if not secondary:
        raise ValueError(f'Вторичный пользователь (id={secondary_user_id}) не найден')
    if secondary.status == UserStatus.DELETED.value:
        raise ValueError(f'Вторичный пользователь (id={secondary_user_id}) уже удалён')

    logger.info(
        'Account merge started',
        primary_id=primary.id,
        secondary_id=secondary.id,
        provider=provider,
        provider_id=provider_id,
    )

    # 1. Move OAuth ids
    oauth_transfers: list[tuple[str, object]] = []
    for field in _OAUTH_FIELDS:
        secondary_value = getattr(secondary, field)
        primary_value = getattr(primary, field)
        if secondary_value and not primary_value:
            oauth_transfers.append((field, secondary_value))
            setattr(secondary, field, None)
    if oauth_transfers:
        await db.flush()
        for field, value in oauth_transfers:
            setattr(primary, field, value)

    # 2. Move telegram_id
    if secondary.telegram_id and not primary.telegram_id:
        transferred_tg_id = secondary.telegram_id
        secondary.telegram_id = None
        await db.flush()
        primary.telegram_id = transferred_tg_id

    # 3. Move email + password
    if not primary.email and secondary.email:
        transferred_email = secondary.email
        transferred_verified = secondary.email_verified
        transferred_verified_at = secondary.email_verified_at
        transferred_password_hash = secondary.password_hash
        secondary.email = None
        secondary.email_verified = False
        secondary.email_verified_at = None
        secondary.password_hash = None
        await db.flush()
        primary.email = transferred_email
        primary.email_verified = transferred_verified
        primary.email_verified_at = transferred_verified_at
        primary.password_hash = transferred_password_hash

    # 4. Sum balances
    transferred_kopeks = secondary.balance_kopeks
    if transferred_kopeks != 0:
        from app.database.crud.user import lock_user_for_update

        primary = await lock_user_for_update(db, primary)
        secondary = await lock_user_for_update(db, secondary)
        transferred_kopeks = secondary.balance_kopeks
        primary.balance_kopeks += transferred_kopeks
        secondary.balance_kopeks = 0

    # 4a. Boolean flag merge
    if secondary.has_had_paid_subscription and not primary.has_had_paid_subscription:
        primary.has_had_paid_subscription = True
    if secondary.has_made_first_topup and not primary.has_made_first_topup:
        primary.has_made_first_topup = True
    if secondary.restriction_topup and not primary.restriction_topup:
        primary.restriction_topup = True
    if secondary.restriction_subscription and not primary.restriction_subscription:
        primary.restriction_subscription = True
    if secondary.restriction_reason and not primary.restriction_reason:
        primary.restriction_reason = secondary.restriction_reason
    if secondary.used_promocodes:
        primary.used_promocodes = (primary.used_promocodes or 0) + secondary.used_promocodes

    # 5. Subscription merge — REMOVED in boilerplate (no Subscription model).
    # TODO(boilerplate): if you re-add subscriptions, transfer them here.

    # 6. Transactions
    await db.execute(update(Transaction).where(Transaction.user_id == secondary.id).values(user_id=primary.id))

    # 7. Payments
    for payment_model in _PAYMENT_MODELS:
        await db.execute(update(payment_model).where(payment_model.user_id == secondary.id).values(user_id=primary.id))
    await db.execute(
        update(SavedPaymentMethod).where(SavedPaymentMethod.user_id == secondary.id).values(user_id=primary.id)
    )

    # 8. Referrals
    await db.execute(
        delete(ReferralEarning).where(
            or_(
                and_(ReferralEarning.user_id == secondary.id, ReferralEarning.referral_id == primary.id),
                and_(ReferralEarning.user_id == primary.id, ReferralEarning.referral_id == secondary.id),
            )
        )
    )
    await db.execute(update(ReferralEarning).where(ReferralEarning.user_id == secondary.id).values(user_id=primary.id))
    await db.execute(
        update(ReferralEarning).where(ReferralEarning.referral_id == secondary.id).values(referral_id=primary.id)
    )
    await db.execute(
        update(User).where(User.referred_by_id == secondary.id, User.id != primary.id).values(referred_by_id=primary.id)
    )
    if primary.referred_by_id == secondary.id:
        primary.referred_by_id = None
    if primary.referred_by_id is None and secondary.referred_by_id is not None:
        if secondary.referred_by_id != primary.id:
            primary.referred_by_id = secondary.referred_by_id

    # 10. Withdrawals
    await db.execute(
        update(WithdrawalRequest).where(WithdrawalRequest.user_id == secondary.id).values(user_id=primary.id)
    )
    await db.execute(
        update(WithdrawalRequest).where(WithdrawalRequest.processed_by == secondary.id).values(processed_by=None)
    )

    # 10a. Discount offers (subscription_conversions / events removed)
    await db.execute(update(DiscountOffer).where(DiscountOffer.user_id == secondary.id).values(user_id=primary.id))

    # 10b. UserPromoGroup
    primary_group_ids = select(UserPromoGroup.promo_group_id).where(UserPromoGroup.user_id == primary.id)
    await db.execute(
        delete(UserPromoGroup).where(
            UserPromoGroup.user_id == secondary.id,
            UserPromoGroup.promo_group_id.in_(primary_group_ids),
        )
    )
    await db.execute(update(UserPromoGroup).where(UserPromoGroup.user_id == secondary.id).values(user_id=primary.id))

    # 10c. PollResponse
    primary_poll_ids = select(PollResponse.poll_id).where(PollResponse.user_id == primary.id)
    await db.execute(
        delete(PollResponse).where(
            PollResponse.user_id == secondary.id,
            PollResponse.poll_id.in_(primary_poll_ids),
        )
    )
    await db.execute(update(PollResponse).where(PollResponse.user_id == secondary.id).values(user_id=primary.id))

    # 10d. PromoOfferLog
    await db.execute(update(PromoOfferLog).where(PromoOfferLog.user_id == secondary.id).values(user_id=primary.id))

    # 10e. AdvertisingCampaignRegistration
    primary_campaign_ids = select(AdvertisingCampaignRegistration.campaign_id).where(
        AdvertisingCampaignRegistration.user_id == primary.id
    )
    await db.execute(
        delete(AdvertisingCampaignRegistration).where(
            AdvertisingCampaignRegistration.user_id == secondary.id,
            AdvertisingCampaignRegistration.campaign_id.in_(primary_campaign_ids),
        )
    )
    await db.execute(
        update(AdvertisingCampaignRegistration)
        .where(AdvertisingCampaignRegistration.user_id == secondary.id)
        .values(user_id=primary.id)
    )

    # 10f. ContestAttempt
    primary_round_ids = select(ContestAttempt.round_id).where(ContestAttempt.user_id == primary.id)
    await db.execute(
        delete(ContestAttempt).where(
            ContestAttempt.user_id == secondary.id,
            ContestAttempt.round_id.in_(primary_round_ids),
        )
    )
    await db.execute(update(ContestAttempt).where(ContestAttempt.user_id == secondary.id).values(user_id=primary.id))

    # 10g. UserRole — drop secondary's roles entirely (avoid privilege escalation).
    await db.execute(delete(UserRole).where(UserRole.user_id == secondary.id))
    await db.execute(update(UserRole).where(UserRole.assigned_by == secondary.id).values(assigned_by=None))

    # 10h. ReferralContestEvent
    await db.execute(
        delete(ReferralContestEvent).where(
            or_(
                and_(ReferralContestEvent.referrer_id == secondary.id, ReferralContestEvent.referral_id == primary.id),
                and_(ReferralContestEvent.referrer_id == primary.id, ReferralContestEvent.referral_id == secondary.id),
            )
        )
    )
    primary_referral_contest_ids = select(ReferralContestEvent.contest_id).where(
        ReferralContestEvent.referral_id == primary.id
    )
    await db.execute(
        delete(ReferralContestEvent).where(
            ReferralContestEvent.referral_id == secondary.id,
            ReferralContestEvent.contest_id.in_(primary_referral_contest_ids),
        )
    )
    await db.execute(
        update(ReferralContestEvent)
        .where(ReferralContestEvent.referral_id == secondary.id)
        .values(referral_id=primary.id)
    )
    await db.execute(
        update(ReferralContestEvent)
        .where(ReferralContestEvent.referrer_id == secondary.id)
        .values(referrer_id=primary.id)
    )

    # 10i. PromoCodeUse
    primary_promo_ids = select(PromoCodeUse.promocode_id).where(PromoCodeUse.user_id == primary.id)
    await db.execute(
        delete(PromoCodeUse).where(
            PromoCodeUse.user_id == secondary.id,
            PromoCodeUse.promocode_id.in_(primary_promo_ids),
        )
    )
    await db.execute(update(PromoCodeUse).where(PromoCodeUse.user_id == secondary.id).values(user_id=primary.id))

    # 10j. PartnerApplication
    await db.execute(
        update(PartnerApplication).where(PartnerApplication.user_id == secondary.id).values(user_id=primary.id)
    )
    await db.execute(
        update(PartnerApplication).where(PartnerApplication.processed_by == secondary.id).values(processed_by=None)
    )

    # 10k. Tickets
    await db.execute(update(Ticket).where(Ticket.user_id == secondary.id).values(user_id=primary.id))
    await db.execute(update(TicketMessage).where(TicketMessage.user_id == secondary.id).values(user_id=primary.id))
    await db.execute(
        update(TicketNotification).where(TicketNotification.user_id == secondary.id).values(user_id=primary.id)
    )

    # 10l. WheelSpin
    await db.execute(update(WheelSpin).where(WheelSpin.user_id == secondary.id).values(user_id=primary.id))

    # 10m. AdvertisingCampaign FK
    await db.execute(
        update(AdvertisingCampaign)
        .where(AdvertisingCampaign.partner_user_id == secondary.id)
        .values(partner_user_id=primary.id)
    )
    await db.execute(
        update(AdvertisingCampaign).where(AdvertisingCampaign.created_by == secondary.id).values(created_by=None)
    )

    # 10n. SentNotification
    await db.execute(
        update(SentNotification).where(SentNotification.user_id == secondary.id).values(user_id=primary.id)
    )

    # 10o. ButtonClickLog
    await db.execute(update(ButtonClickLog).where(ButtonClickLog.user_id == secondary.id).values(user_id=primary.id))

    # 10p. SupportAuditLog
    await db.execute(
        update(SupportAuditLog).where(SupportAuditLog.actor_user_id == secondary.id).values(actor_user_id=None)
    )
    await db.execute(
        update(SupportAuditLog).where(SupportAuditLog.target_user_id == secondary.id).values(target_user_id=primary.id)
    )

    # 10q. AdminAuditLog
    await db.execute(update(AdminAuditLog).where(AdminAuditLog.user_id == secondary.id).values(user_id=primary.id))

    # 10r. created_by FK clearing
    await db.execute(update(PromoCode).where(PromoCode.created_by == secondary.id).values(created_by=None))
    await db.execute(update(ReferralContest).where(ReferralContest.created_by == secondary.id).values(created_by=None))
    await db.execute(
        update(PromoOfferTemplate).where(PromoOfferTemplate.created_by == secondary.id).values(created_by=None)
    )
    await db.execute(update(BroadcastHistory).where(BroadcastHistory.admin_id == secondary.id).values(admin_id=None))
    await db.execute(update(Poll).where(Poll.created_by == secondary.id).values(created_by=None))
    await db.execute(update(UserMessage).where(UserMessage.created_by == secondary.id).values(created_by=None))
    await db.execute(update(WelcomeText).where(WelcomeText.created_by == secondary.id).values(created_by=None))
    await db.execute(update(PinnedMessage).where(PinnedMessage.created_by == secondary.id).values(created_by=None))
    await db.execute(update(AdminRole).where(AdminRole.created_by == secondary.id).values(created_by=None))
    await db.execute(update(AccessPolicy).where(AccessPolicy.created_by == secondary.id).values(created_by=None))
    await db.execute(update(NewsArticle).where(NewsArticle.created_by == secondary.id).values(created_by=None))

    # 11. Refresh tokens
    now = datetime.now(UTC)
    await db.execute(
        update(CabinetRefreshToken)
        .where(
            CabinetRefreshToken.user_id.in_([primary.id, secondary.id]),
            CabinetRefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )

    # 12. Partner status
    primary_priority = _PARTNER_STATUS_PRIORITY.get(primary.partner_status, 0)
    secondary_priority = _PARTNER_STATUS_PRIORITY.get(secondary.partner_status, 0)
    if secondary_priority > primary_priority:
        primary.partner_status = secondary.partner_status

    # 13. Referral commission
    if secondary.referral_commission_percent is not None and primary.referral_commission_percent is None:
        primary.referral_commission_percent = secondary.referral_commission_percent

    # 14. Mark secondary deleted and clear unique fields
    secondary.status = UserStatus.DELETED.value
    secondary.referral_code = None
    secondary.referred_by_id = None
    secondary.email = None
    secondary.email_verified = False
    secondary.email_verified_at = None
    secondary.email_verification_token = None
    secondary.email_verification_expires = None
    secondary.email_change_new = None
    secondary.email_change_code = None
    secondary.email_change_expires = None
    secondary.password_hash = None
    secondary.password_reset_token = None
    secondary.password_reset_expires = None
    secondary.telegram_id = None
    for field in _OAUTH_FIELDS:
        if getattr(secondary, field) is not None:
            setattr(secondary, field, None)
    secondary.updated_at = now

    logger.info('Account merge complete', primary_id=primary.id, secondary_id=secondary.id)

    await db.flush()
    return primary
