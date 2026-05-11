from datetime import UTC, datetime

import structlog
from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.localization.loader import DEFAULT_LANGUAGE
from app.localization.texts import get_texts


__all__ = (
    'get_main_menu_keyboard_async',
    'get_main_menu_keyboard',
    'get_info_menu_keyboard',
    'get_rules_keyboard',
    'get_privacy_policy_keyboard',
    'get_post_registration_keyboard',
    'get_channel_sub_keyboard',
    'get_language_selection_keyboard',
    'get_back_keyboard',
    'get_balance_keyboard',
    'get_payment_methods_keyboard',
    'get_yookassa_payment_keyboard',
    'get_referral_keyboard',
    'get_support_keyboard',
    'get_pagination_keyboard',
    'get_confirmation_keyboard',
    'get_saved_cards_keyboard',
    'get_confirm_unlink_keyboard',
    'get_cryptobot_payment_keyboard',
    'get_happ_download_button_row',
    'get_ticket_cancel_keyboard',
    'get_my_tickets_keyboard',
    'get_ticket_view_keyboard',
    'get_ticket_reply_cancel_keyboard',
    'get_admin_tickets_keyboard',
    'get_admin_ticket_view_keyboard',
    'get_admin_ticket_reply_cancel_keyboard',
)


logger = structlog.get_logger(__name__)


async def get_main_menu_keyboard_async(
    db: AsyncSession,
    language: str = DEFAULT_LANGUAGE,
    is_admin: bool = False,
    has_had_paid_subscription: bool = False,
    has_active_subscription: bool = False,
    subscription_is_active: bool = False,
    balance_kopeks: int = 0,
    subscription=None,
    show_resume_checkout: bool = False,
    has_saved_cart: bool = False,
    *,
    is_moderator: bool = False,
    custom_buttons: list[InlineKeyboardButton] | None = None,
    user=None,  # Добавляем параметр пользователя для получения данных
) -> InlineKeyboardMarkup:
    """
    Асинхронная версия get_main_menu_keyboard с поддержкой конструктора меню.

    Если MENU_LAYOUT_ENABLED=True, использует конфигурацию из БД.
    Иначе делегирует в синхронную версию.
    """
    if settings.MENU_LAYOUT_ENABLED:
        from app.services.menu_layout_service import MenuContext, MenuLayoutService

        # Получаем данные для плейсхолдеров
        subscription_days_left = 0
        traffic_used_gb = 0.0
        traffic_left_gb = 0.0
        referral_count = 0
        referral_earnings_kopeks = 0
        registration_days = 0
        promo_group_id = None
        has_autopay = False
        username = ''

        # Заполняем данными из подписки
        if subscription:
            # Дни до окончания подписки
            if hasattr(subscription, 'days_left'):
                # Используем свойство из модели, которое правильно вычисляет дни в UTC
                subscription_days_left = subscription.days_left
            elif hasattr(subscription, 'end_date') and subscription.end_date:
                # Fallback: вычисляем вручную, используя UTC
                now_utc = datetime.now(UTC)
                days_left = (subscription.end_date - now_utc).days
                subscription_days_left = max(0, days_left)

            # Трафик
            if hasattr(subscription, 'traffic_used_gb'):
                traffic_used_gb = subscription.traffic_used_gb or 0.0

            if hasattr(subscription, 'traffic_limit_gb') and subscription.traffic_limit_gb:
                traffic_left_gb = max(0, subscription.traffic_limit_gb - (subscription.traffic_used_gb or 0))

            # Автоплатеж
            if hasattr(subscription, 'autopay_enabled'):
                has_autopay = subscription.autopay_enabled

        # Получаем данные пользователя
        if user:
            # Имя пользователя
            if hasattr(user, 'username') and user.username:
                username = user.username
            elif hasattr(user, 'first_name') and user.first_name:
                username = user.first_name

            # Дни с регистрации
            if hasattr(user, 'created_at') and user.created_at:
                now_utc = datetime.now(UTC)
                registration_days = (now_utc - user.created_at).days

            # ID промо-группы
            if hasattr(user, 'promo_group_id'):
                promo_group_id = user.promo_group_id

        # Получаем данные о рефералах из БД (если нужно)
        try:
            from app.database.crud.referral import get_user_referral_stats

            if user and hasattr(user, 'id'):
                referral_data = await get_user_referral_stats(db, user.id)
                if referral_data:
                    referral_count = referral_data.get('invited_count', 0)
                    referral_earnings_kopeks = referral_data.get('total_earned_kopeks', 0)
        except Exception as e:
            logger.error('Error getting referral data', error=e)

        context = MenuContext(
            language=language,
            is_admin=is_admin,
            is_moderator=is_moderator,
            has_active_subscription=has_active_subscription,
            subscription_is_active=subscription_is_active,
            has_had_paid_subscription=has_had_paid_subscription,
            balance_kopeks=balance_kopeks,
            subscription=subscription,
            show_resume_checkout=show_resume_checkout,
            has_saved_cart=has_saved_cart,
            custom_buttons=custom_buttons or [],
            # Добавляем данные для плейсхолдеров
            username=username,
            subscription_days=subscription_days_left,
            traffic_used_gb=traffic_used_gb,
            traffic_left_gb=traffic_left_gb,
            referral_count=referral_count,
            referral_earnings_kopeks=referral_earnings_kopeks,
            registration_days=registration_days,
            promo_group_id=promo_group_id,
            has_autopay=has_autopay,
        )

        return await MenuLayoutService.build_keyboard(db, context)

    # Fallback на синхронную версию
    return get_main_menu_keyboard(
        language=language,
        is_admin=is_admin,
        has_had_paid_subscription=has_had_paid_subscription,
        has_active_subscription=has_active_subscription,
        subscription_is_active=subscription_is_active,
        balance_kopeks=balance_kopeks,
        subscription=subscription,
        show_resume_checkout=show_resume_checkout,
        has_saved_cart=has_saved_cart,
        is_moderator=is_moderator,
        custom_buttons=custom_buttons,
    )


_LANGUAGE_DISPLAY_NAMES = {
    'ru': '🇷🇺 Русский',
    'ru-ru': '🇷🇺 Русский',
    'en': '🇬🇧 English',
    'en-us': '🇺🇸 English',
    'en-gb': '🇬🇧 English',
    'ua': '🇺🇦 Українська',
    'uk': '🇺🇦 Українська',
    'uk-ua': '🇺🇦 Українська',
    'kk': '🇰🇿 Қазақша',
    'kk-kz': '🇰🇿 Қазақша',
    'kz': '🇰🇿 Қазақша',
    'uz': '🇺🇿 Oʻzbekcha',
    'uz-uz': '🇺🇿 Oʻzbekcha',
    'tr': '🇹🇷 Türkçe',
    'tr-tr': '🇹🇷 Türkçe',
    'pl': '🇵🇱 Polski',
    'pl-pl': '🇵🇱 Polski',
    'de': '🇩🇪 Deutsch',
    'de-de': '🇩🇪 Deutsch',
    'fr': '🇫🇷 Français',
    'fr-fr': '🇫🇷 Français',
    'es': '🇪🇸 Español',
    'es-es': '🇪🇸 Español',
    'it': '🇮🇹 Italiano',
    'it-it': '🇮🇹 Italiano',
    'pt': '🇵🇹 Português',
    'pt-pt': '🇵🇹 Português',
    'pt-br': '🇧🇷 Português',
    'zh': '🇨🇳 中文',
    'zh-cn': '🇨🇳 中文 (简体)',
    'zh-hans': '🇨🇳 中文 (简体)',
    'zh-tw': '🇹🇼 中文 (繁體)',
    'zh-hant': '🇹🇼 中文 (繁體)',
    'vi': '🇻🇳 Tiếng Việt',
    'vi-vn': '🇻🇳 Tiếng Việt',
    'fa': '🇮🇷 فارسی',
    'fa-ir': '🇮🇷 فارسی',
}


def get_rules_keyboard(language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=texts.RULES_ACCEPT, callback_data='rules_accept'),
                InlineKeyboardButton(text=texts.RULES_DECLINE, callback_data='rules_decline'),
            ]
        ]
    )


def get_privacy_policy_keyboard(language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=texts.PRIVACY_POLICY_ACCEPT, callback_data='privacy_policy_accept'),
                InlineKeyboardButton(text=texts.PRIVACY_POLICY_DECLINE, callback_data='privacy_policy_decline'),
            ]
        ]
    )


def get_channel_sub_keyboard(
    channels: list[dict] | str | None = None,
    language: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    """Subscription keyboard for required channels.

    Supports Bot API 9.4 colored buttons via ``style`` parameter:
    - subscribed channels → green (``style='success'``)
    - unsubscribed channels → blue (``style='primary'``)

    Args:
        channels: List of dicts with 'channel_link', 'title', and optional
                  'is_subscribed' keys, OR a string (legacy single channel_link).
        language: Locale code for button text.
    """
    texts = get_texts(language)
    buttons: list[list[InlineKeyboardButton]] = []

    if isinstance(channels, str):
        # Legacy: single channel link string
        if channels:
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=texts.t('CHANNEL_SUBSCRIBE_BUTTON', '🔗 Подписаться'),
                        url=channels,
                        style='primary',
                    )
                ]
            )
    elif isinstance(channels, list):
        for ch in channels:
            link = ch.get('channel_link')
            title = ch.get('title')
            is_subscribed = ch.get('is_subscribed', False)
            if link:
                if is_subscribed:
                    label = f'✅ {title}' if title else '✅'
                    buttons.append([InlineKeyboardButton(text=label, url=link, style='success')])
                else:
                    label = title or texts.t('CHANNEL_SUBSCRIBE_BUTTON', '🔗 Подписаться')
                    buttons.append([InlineKeyboardButton(text=label, url=link, style='primary')])

    buttons.append(
        [
            InlineKeyboardButton(
                text=texts.t('CHANNEL_CHECK_BUTTON', '✅ Я подписался'),
                callback_data='sub_channel_check',
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_post_registration_keyboard(language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts.t('POST_REGISTRATION_CONTINUE_BUTTON', 'Продолжить ➡️'),
                    callback_data='back_to_menu',
                )
            ],
        ]
    )


def get_language_selection_keyboard(
    current_language: str | None = None,
    *,
    include_back: bool = False,
    language: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    available_languages = settings.get_available_languages()

    buttons: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []

    normalized_current = (current_language or '').lower()

    for index, lang_code in enumerate(available_languages, start=1):
        normalized_code = lang_code.lower()
        display_name = _LANGUAGE_DISPLAY_NAMES.get(
            normalized_code,
            normalized_code.upper(),
        )

        prefix = '✅ ' if normalized_code == normalized_current and normalized_current else ''

        row.append(
            InlineKeyboardButton(
                text=f'{prefix}{display_name}',
                callback_data=f'language_select:{normalized_code}',
            )
        )

        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    if include_back:
        texts = get_texts(language)
        buttons.append([InlineKeyboardButton(text=texts.BACK, callback_data='back_to_menu')])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _get_balance_text(cached_styles: dict, language: str, texts, balance_kopeks: int) -> str:
    """Build balance button text with formatting."""
    bal_cfg = cached_styles.get('balance', {})
    safe_balance = balance_kopeks or 0

    # Custom label overrides the whole text including balance amount
    custom_bal = bal_cfg.get('labels', {}).get(language, '')
    if custom_bal:
        return custom_bal
    if hasattr(texts, 'BALANCE_BUTTON') and safe_balance > 0:
        return texts.BALANCE_BUTTON.format(balance=texts.format_price(safe_balance))
    return texts.t('BALANCE_BUTTON_DEFAULT', '💰 Баланс: {balance}').format(
        balance=texts.format_price(safe_balance),
    )


def _is_support_enabled() -> bool:
    """Check if support menu is enabled."""
    try:
        from app.services.support_settings_service import SupportSettingsService

        return SupportSettingsService.is_support_menu_enabled()
    except Exception:
        return settings.SUPPORT_MENU_ENABLED


def _build_cabinet_main_menu_keyboard(
    language: str,
    texts,
    *,
    is_admin: bool,
    is_moderator: bool,
    balance_kopeks: int = 0,
) -> InlineKeyboardMarkup:
    """Build the main-menu keyboard for Cabinet mode.

    Row layout and button arrangement are driven by the cached menu layout
    (``get_cached_menu_layout``).  Each row specifies which buttons it contains
    and how many fit per keyboard row (``max_per_row``).
    """
    from app.utils.button_styles_cache import CALLBACK_TO_SECTION, get_cached_button_styles
    from app.utils.menu_layout_cache import get_cached_menu_layout
    from app.utils.miniapp_buttons import (
        CALLBACK_TO_CABINET_STYLE,
        _resolve_style,
        build_cabinet_url,
    )

    global_style = _resolve_style((settings.CABINET_BUTTON_STYLE or '').strip())
    cached_styles = get_cached_button_styles()
    layout = get_cached_menu_layout()
    custom_buttons_cfg: dict[str, dict] = layout.get('custom_buttons', {})

    def _cabinet_button(
        text: str,
        path: str,
        callback_fallback: str,
        *,
        style: str | None = None,
        icon_custom_emoji_id: str | None = None,
    ) -> InlineKeyboardButton:
        url = build_cabinet_url(path)
        if url:
            section = CALLBACK_TO_SECTION.get(callback_fallback)
            section_cfg = cached_styles.get(section or '', {}) if section else {}

            # 'default' in per-section config means "no color" — do not fall through.
            if style:
                resolved = _resolve_style(style)
            elif section_cfg.get('style'):
                resolved = _resolve_style(section_cfg['style'])
            else:
                resolved = global_style or _resolve_style(CALLBACK_TO_CABINET_STYLE.get(callback_fallback))
            resolved_emoji = icon_custom_emoji_id or section_cfg.get('icon_custom_emoji_id') or None

            return InlineKeyboardButton(
                text=text,
                web_app=types.WebAppInfo(url=url),
                style=resolved,
                icon_custom_emoji_id=resolved_emoji or None,
            )
        return InlineKeyboardButton(text=text, callback_data=callback_fallback)

    # -- Collect row definitions sorted by row_N key --
    row_keys = sorted(
        (k for k in layout if k.startswith('row_')),
        key=lambda k: int(k.split('_', 1)[1]) if k.split('_', 1)[1].isdigit() else 0,
    )

    keyboard_rows: list[list[InlineKeyboardButton]] = []

    for row_key in row_keys:
        row_def = layout[row_key]
        btn_ids: list[str] = row_def.get('buttons', [])
        max_per_row: int = row_def.get('max_per_row', 1)
        row_buttons: list[InlineKeyboardButton] = []

        for btn_id in btn_ids:
            # --- Custom URL buttons ---
            if btn_id.startswith('custom_'):
                custom_cfg = custom_buttons_cfg.get(btn_id)
                if not custom_cfg or not custom_cfg.get('url') or not custom_cfg.get('enabled', True):
                    continue
                custom_text = (
                    custom_cfg.get('labels', {}).get(language, '')
                    or custom_cfg.get('labels', {}).get('ru', '')
                    or 'Link'
                )
                resolved_style = _resolve_style(custom_cfg.get('style'))
                resolved_emoji = custom_cfg.get('icon_custom_emoji_id') or None
                open_in = custom_cfg.get('open_in', 'external')
                link_kwarg = (
                    {'web_app': types.WebAppInfo(url=custom_cfg['url'])}
                    if open_in == 'webapp'
                    else {'url': custom_cfg['url']}
                )
                row_buttons.append(
                    InlineKeyboardButton(
                        text=custom_text,
                        **link_kwarg,
                        style=resolved_style,
                        icon_custom_emoji_id=resolved_emoji,
                    ),
                )
                continue

            # --- Built-in buttons ---
            section_cfg = cached_styles.get(btn_id, {})

            match btn_id:
                case 'home':
                    if not section_cfg.get('enabled', True):
                        continue
                    home_text = section_cfg.get('labels', {}).get(language, '') or texts.t(
                        'MENU_PROFILE', '👤 Личный кабинет'
                    )
                    row_buttons.append(_cabinet_button(home_text, '/', 'menu_profile_unavailable'))

                case 'subscription':
                    if not section_cfg.get('enabled', True):
                        continue
                    default_sub_text = (
                        texts.t('MY_SUBSCRIPTIONS_BUTTON', '📱 Мои подписки')
                        if settings.is_multi_tariff_enabled()
                        else texts.MENU_SUBSCRIPTION
                    )
                    sub_text = section_cfg.get('labels', {}).get(language, '') or default_sub_text
                    row_buttons.append(_cabinet_button(sub_text, '/subscription', 'menu_subscription'))

                case 'balance':
                    if not section_cfg.get('enabled', True):
                        continue
                    balance_text = _get_balance_text(cached_styles, language, texts, balance_kopeks)
                    row_buttons.append(_cabinet_button(balance_text, '/balance', 'menu_balance'))

                case 'referral':
                    if not settings.is_referral_program_enabled():
                        continue
                    if not section_cfg.get('enabled', True):
                        continue
                    ref_text = section_cfg.get('labels', {}).get(language, '') or texts.MENU_REFERRALS
                    row_buttons.append(_cabinet_button(ref_text, '/referral', 'menu_referrals'))

                case 'support':
                    if not _is_support_enabled():
                        continue
                    if not section_cfg.get('enabled', True):
                        continue
                    sup_text = section_cfg.get('labels', {}).get(language, '') or texts.MENU_SUPPORT
                    row_buttons.append(_cabinet_button(sup_text, '/support', 'menu_support'))

                case 'info':
                    if not section_cfg.get('enabled', True):
                        continue
                    info_text = section_cfg.get('labels', {}).get(language, '') or texts.t('MENU_INFO', 'ℹ️ Инфо')
                    row_buttons.append(_cabinet_button(info_text, '/info', 'menu_info'))

                case 'language':
                    if not section_cfg.get('enabled', True):
                        continue
                    if not settings.is_language_selection_enabled():
                        continue
                    lang_text = section_cfg.get('labels', {}).get(language, '') or texts.MENU_LANGUAGE
                    resolved_lang_emoji = section_cfg.get('icon_custom_emoji_id') or None
                    row_buttons.append(
                        InlineKeyboardButton(
                            text=lang_text,
                            callback_data='menu_language',
                            icon_custom_emoji_id=resolved_lang_emoji,
                        )
                    )

                case 'admin':
                    if not is_admin:
                        continue
                    admin_row = [InlineKeyboardButton(text=texts.MENU_ADMIN, callback_data='admin_panel')]
                    if section_cfg.get('enabled', True):
                        admin_web_text = section_cfg.get('labels', {}).get(language, '') or '🖥 Веб-Админка'
                        admin_row.append(_cabinet_button(admin_web_text, '/admin', 'admin_panel'))
                    keyboard_rows.append(admin_row)
                    continue  # bypass max_per_row chunking

        # Split collected buttons into keyboard rows respecting max_per_row
        if row_buttons:
            for i in range(0, len(row_buttons), max_per_row):
                keyboard_rows.append(row_buttons[i : i + max_per_row])

    # -- Moderator panel (only when not admin — admin row handled above) --
    if is_moderator and not is_admin:
        keyboard_rows.append([InlineKeyboardButton(text='🧑‍⚖️ Модерация', callback_data='moderator_panel')])

    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)


def get_main_menu_keyboard(
    language: str = DEFAULT_LANGUAGE,
    is_admin: bool = False,
    has_had_paid_subscription: bool = False,
    has_active_subscription: bool = False,
    subscription_is_active: bool = False,
    balance_kopeks: int = 0,
    subscription=None,
    show_resume_checkout: bool = False,
    has_saved_cart: bool = False,  # Новый параметр для отображения уведомления о сохраненной корзине
    *,
    is_moderator: bool = False,
    custom_buttons: list[InlineKeyboardButton] | None = None,
) -> InlineKeyboardMarkup:
    texts = get_texts(language)

    if settings.is_cabinet_mode():
        return _build_cabinet_main_menu_keyboard(
            language,
            texts,
            is_admin=is_admin,
            is_moderator=is_moderator,
            balance_kopeks=balance_kopeks,
        )

    if settings.DEBUG:
        logger.debug(
            'DEBUG KEYBOARD',
            language=language,
            is_admin=is_admin,
            has_had_paid=has_had_paid_subscription,
            has_active=has_active_subscription,
            sub_active=subscription_is_active,
            balance=balance_kopeks,
        )

    safe_balance = balance_kopeks or 0
    if hasattr(texts, 'BALANCE_BUTTON') and safe_balance > 0:
        balance_button_text = texts.BALANCE_BUTTON.format(balance=texts.format_price(safe_balance))
    else:
        balance_button_text = texts.t(
            'BALANCE_BUTTON_DEFAULT',
            '💰 Баланс: {balance}',
        ).format(balance=texts.format_price(safe_balance))

    keyboard: list[list[InlineKeyboardButton]] = []
    paired_buttons: list[InlineKeyboardButton] = []

    keyboard.append([InlineKeyboardButton(text=balance_button_text, callback_data='menu_balance')])

    if custom_buttons:
        for button in custom_buttons:
            if isinstance(button, InlineKeyboardButton):
                paired_buttons.append(button)

    # Добавляем кнопки промокода и рефералов, учитывая настройки
    paired_buttons.append(InlineKeyboardButton(text=texts.MENU_PROMOCODE, callback_data='menu_promocode'))

    # Добавляем кнопку рефералов, только если программа включена
    if settings.is_referral_program_enabled():
        paired_buttons.append(InlineKeyboardButton(text=texts.MENU_REFERRALS, callback_data='menu_referrals'))

    # Добавляем кнопку конкурсов
    if settings.CONTESTS_ENABLED and settings.CONTESTS_BUTTON_VISIBLE:
        paired_buttons.append(
            InlineKeyboardButton(text=texts.t('CONTESTS_BUTTON', '🎲 Конкурсы'), callback_data='contests_menu')
        )

    try:
        from app.services.support_settings_service import SupportSettingsService

        support_enabled = SupportSettingsService.is_support_menu_enabled()
    except Exception:
        support_enabled = settings.SUPPORT_MENU_ENABLED

    if support_enabled:
        paired_buttons.append(InlineKeyboardButton(text=texts.MENU_SUPPORT, callback_data='menu_support'))

    paired_buttons.append(
        InlineKeyboardButton(
            text=texts.t('MENU_INFO', 'ℹ️ Инфо'),
            callback_data='menu_info',
        )
    )

    if settings.is_language_selection_enabled():
        paired_buttons.append(InlineKeyboardButton(text=texts.MENU_LANGUAGE, callback_data='menu_language'))

    for i in range(0, len(paired_buttons), 2):
        row = paired_buttons[i : i + 2]
        keyboard.append(row)

    if settings.DEBUG:
        logger.debug('DEBUG KEYBOARD: админ кнопка', is_admin=is_admin)

    if is_admin:
        if settings.DEBUG:
            logger.debug('DEBUG KEYBOARD: Админ кнопка ДОБАВЛЕНА')
        keyboard.append([InlineKeyboardButton(text=texts.MENU_ADMIN, callback_data='admin_panel')])
    elif settings.DEBUG:
        logger.debug('DEBUG KEYBOARD: Админ кнопка НЕ добавлена')
    # Moderator access (limited support panel)
    if (not is_admin) and is_moderator:
        keyboard.append([InlineKeyboardButton(text='🧑‍⚖️ Модерация', callback_data='moderator_panel')])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_info_menu_keyboard(
    language: str = DEFAULT_LANGUAGE,
    show_privacy_policy: bool = False,
    show_public_offer: bool = False,
    show_faq: bool = False,
    show_promo_groups: bool = False,
) -> InlineKeyboardMarkup:
    texts = get_texts(language)

    buttons: list[list[InlineKeyboardButton]] = []

    if show_faq:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=texts.t('MENU_FAQ', '❓ FAQ'),
                    callback_data='menu_faq',
                )
            ]
        )

    if show_promo_groups:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=texts.t('MENU_PROMO_GROUPS_INFO', '🎯 Промогруппы'),
                    callback_data='menu_info_promo_groups',
                )
            ]
        )

    if show_privacy_policy:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=texts.t('MENU_PRIVACY_POLICY', '🛡️ Политика конф.'),
                    callback_data='menu_privacy_policy',
                )
            ]
        )

    if show_public_offer:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=texts.t('MENU_PUBLIC_OFFER', '📄 Оферта'),
                    callback_data='menu_public_offer',
                )
            ]
        )

    buttons.append([InlineKeyboardButton(text=texts.MENU_RULES, callback_data='menu_rules')])

    buttons.append([InlineKeyboardButton(text=texts.BACK, callback_data='back_to_menu')])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_happ_download_button_row(texts) -> list[InlineKeyboardButton] | None:
    if not settings.is_happ_download_button_enabled():
        return None

    return [
        InlineKeyboardButton(
            text=texts.t('HAPP_DOWNLOAD_BUTTON', '⬇️ Скачать Happ'), callback_data='subscription_happ_download'
        )
    ]


def get_back_keyboard(language: str = DEFAULT_LANGUAGE, callback_data: str = 'back_to_menu') -> InlineKeyboardMarkup:
    texts = get_texts(language)
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=texts.BACK, callback_data=callback_data)]])


def get_balance_keyboard(language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    texts = get_texts(language)

    keyboard = [
        [
            InlineKeyboardButton(text=texts.BALANCE_HISTORY, callback_data='balance_history'),
            InlineKeyboardButton(text=texts.BALANCE_TOP_UP, callback_data='balance_topup'),
        ],
    ]
    if settings.YOOKASSA_RECURRENT_ENABLED:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('SAVED_CARDS_BUTTON', '💳 Привязанные карты'),
                    callback_data='saved_cards_list',
                )
            ]
        )
    keyboard.append([InlineKeyboardButton(text=texts.BACK, callback_data='back_to_menu')])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_payment_methods_keyboard(amount_kopeks: int, language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    keyboard = []
    has_direct_payment_methods = False

    amount_kopeks = max(0, int(amount_kopeks or 0))

    def _build_callback(method: str) -> str:
        if amount_kopeks > 0:
            return f'topup_amount|{method}|{amount_kopeks}'
        return f'topup_{method}'

    if settings.TELEGRAM_STARS_ENABLED:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_TELEGRAM_STARS', '⭐ Telegram Stars'), callback_data=_build_callback('stars')
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_yookassa_enabled():
        if settings.YOOKASSA_SBP_ENABLED:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        text=texts.t('PAYMENT_SBP_YOOKASSA', '🏦 Оплатить по СБП (YooKassa)'),
                        callback_data=_build_callback('yookassa_sbp'),
                    )
                ]
            )
            has_direct_payment_methods = True

        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_CARD_YOOKASSA', '💳 Банковская карта (YooKassa)'),
                    callback_data=_build_callback('yookassa'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.TRIBUTE_ENABLED:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_CARD_TRIBUTE', '💳 Банковская карта (Tribute)'),
                    callback_data=_build_callback('tribute'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_mulenpay_enabled():
        mulenpay_name = settings.get_mulenpay_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t(
                        'PAYMENT_CARD_MULENPAY',
                        '💳 Банковская карта ({mulenpay_name})',
                    ).format(mulenpay_name=mulenpay_name),
                    callback_data=_build_callback('mulenpay'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_wata_enabled():
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_CARD_WATA', '💳 Банковская карта (WATA)'),
                    callback_data=_build_callback('wata'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_pal24_enabled():
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_CARD_PAL24', '🏦 СБП (PayPalych)'), callback_data=_build_callback('pal24')
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_platega_enabled() and settings.get_platega_active_methods():
        platega_name = settings.get_platega_display_name()
        if settings.PLATEGA_INLINE_METHODS:
            for method_code in settings.get_platega_active_methods():
                title = settings.get_platega_method_display_title(method_code)
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            text=f'{title} ({platega_name})',
                            callback_data=_build_callback(f'platega_m{method_code}'),
                        )
                    ]
                )
        else:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        text=texts.t('PAYMENT_PLATEGA', f'💳 {platega_name}'),
                        callback_data=_build_callback('platega'),
                    )
                ]
            )
        has_direct_payment_methods = True

    if settings.is_cryptobot_enabled():
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_CRYPTOBOT', '🪙 Криптовалюта (CryptoBot)'),
                    callback_data=_build_callback('cryptobot'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_heleket_enabled():
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_HELEKET', '🪙 Криптовалюта (Heleket)'),
                    callback_data=_build_callback('heleket'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_cloudpayments_enabled():
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_CLOUDPAYMENTS', '💳 Банковская карта (CloudPayments)'),
                    callback_data=_build_callback('cloudpayments'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_freekassa_sbp_enabled():
        sbp_name = settings.get_freekassa_sbp_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_FREEKASSA_SBP', f'📱 {sbp_name}'),
                    callback_data=_build_callback('freekassa_sbp'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_freekassa_card_enabled():
        card_name = settings.get_freekassa_card_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_FREEKASSA_CARD', f'💳 {card_name}'),
                    callback_data=_build_callback('freekassa_card'),
                )
            ]
        )
        has_direct_payment_methods = True

    if (
        settings.is_freekassa_enabled()
        and not settings.is_freekassa_sbp_enabled()
        and not settings.is_freekassa_card_enabled()
    ):
        freekassa_name = settings.get_freekassa_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_FREEKASSA', f'💳 {freekassa_name}'),
                    callback_data=_build_callback('freekassa'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_kassa_ai_sbp_enabled():
        sbp_name = settings.get_kassa_ai_sbp_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_KASSA_AI_SBP', f'📱 {sbp_name}'),
                    callback_data=_build_callback('kassa_ai_sbp'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_kassa_ai_card_enabled():
        card_name = settings.get_kassa_ai_card_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_KASSA_AI_CARD', f'💳 {card_name}'),
                    callback_data=_build_callback('kassa_ai_card'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_kassa_ai_sberpay_enabled():
        sberpay_name = settings.get_kassa_ai_sberpay_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_KASSA_AI_SBERPAY', f'💳 {sberpay_name}'),
                    callback_data=_build_callback('kassa_ai_sberpay'),
                )
            ]
        )
        has_direct_payment_methods = True

    if (
        settings.is_kassa_ai_enabled()
        and not settings.is_kassa_ai_sbp_enabled()
        and not settings.is_kassa_ai_card_enabled()
        and not settings.is_kassa_ai_sberpay_enabled()
    ):
        kassa_ai_name = settings.get_kassa_ai_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_KASSA_AI', f'💳 {kassa_ai_name}'), callback_data=_build_callback('kassa_ai')
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_riopay_enabled():
        riopay_name = settings.get_riopay_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_RIOPAY', f'💳 Банковская карта ({riopay_name})'),
                    callback_data=_build_callback('riopay'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_severpay_enabled():
        severpay_name = settings.get_severpay_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_SEVERPAY', f'💳 Банковская карта ({severpay_name})'),
                    callback_data=_build_callback('severpay'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_paypear_enabled():
        paypear_name = settings.get_paypear_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_PAYPEAR', f'💳 Оплата ({paypear_name})'),
                    callback_data=_build_callback('paypear'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_rollypay_enabled():
        rollypay_name = settings.get_rollypay_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_ROLLYPAY', f'💳 {rollypay_name}'),
                    callback_data=_build_callback('rollypay'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_overpay_enabled():
        overpay_name = settings.get_overpay_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_OVERPAY', f'💳 {overpay_name}'),
                    callback_data=_build_callback('overpay'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_aurapay_sbp_enabled():
        sbp_name = settings.get_aurapay_sbp_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_AURAPAY_SBP', f'📱 {sbp_name}'),
                    callback_data=_build_callback('aurapay_sbp'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_aurapay_card_enabled():
        card_name = settings.get_aurapay_card_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_AURAPAY_CARD', f'💳 {card_name}'),
                    callback_data=_build_callback('aurapay_card'),
                )
            ]
        )
        has_direct_payment_methods = True

    if (
        settings.is_aurapay_enabled()
        and not settings.is_aurapay_sbp_enabled()
        and not settings.is_aurapay_card_enabled()
    ):
        aurapay_name = settings.get_aurapay_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_AURAPAY', f'💳 {aurapay_name}'),
                    callback_data=_build_callback('aurapay'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_etoplatezhi_sbp_enabled():
        sbp_name = settings.get_etoplatezhi_sbp_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_ETOPLATEZHI_SBP', f'📱 {sbp_name}'),
                    callback_data=_build_callback('etoplatezhi_sbp'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_etoplatezhi_card_enabled():
        card_name = settings.get_etoplatezhi_card_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_ETOPLATEZHI_CARD', f'💳 {card_name}'),
                    callback_data=_build_callback('etoplatezhi_card'),
                )
            ]
        )
        has_direct_payment_methods = True

    if (
        settings.is_etoplatezhi_enabled()
        and not settings.is_etoplatezhi_sbp_enabled()
        and not settings.is_etoplatezhi_card_enabled()
    ):
        etoplatezhi_name = settings.get_etoplatezhi_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_ETOPLATEZHI', f'💳 {etoplatezhi_name}'),
                    callback_data=_build_callback('etoplatezhi'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_antilopay_sbp_enabled():
        sbp_name = settings.get_antilopay_sbp_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_ANTILOPAY_SBP', f'📱 {sbp_name}'),
                    callback_data=_build_callback('antilopay_sbp'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_antilopay_card_enabled():
        card_name = settings.get_antilopay_card_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_ANTILOPAY_CARD', f'💳 {card_name}'),
                    callback_data=_build_callback('antilopay_card'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_antilopay_sberpay_enabled():
        sberpay_name = settings.get_antilopay_sberpay_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_ANTILOPAY_SBERPAY', f'💳 {sberpay_name}'),
                    callback_data=_build_callback('antilopay_sberpay'),
                )
            ]
        )
        has_direct_payment_methods = True

    if (
        settings.is_antilopay_enabled()
        and not settings.is_antilopay_sbp_enabled()
        and not settings.is_antilopay_card_enabled()
        and not settings.is_antilopay_sberpay_enabled()
    ):
        antilopay_name = settings.get_antilopay_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_ANTILOPAY', f'💳 {antilopay_name}'),
                    callback_data=_build_callback('antilopay'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_jupiter_sbp_enabled():
        jupiter_sbp_name = settings.get_jupiter_sbp_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_JUPITER_SBP', f'📱 {jupiter_sbp_name}'),
                    callback_data=_build_callback('jupiter_sbp'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_jupiter_enabled() and not settings.is_jupiter_sbp_enabled():
        jupiter_name = settings.get_jupiter_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_JUPITER', f'🪐 {jupiter_name}'),
                    callback_data=_build_callback('jupiter'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_donut_card_enabled():
        donut_card_name = settings.get_donut_card_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_DONUT_CARD', f'💳 {donut_card_name}'),
                    callback_data=_build_callback('donut_card'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_donut_sbp_enabled():
        donut_sbp_name = settings.get_donut_sbp_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_DONUT_SBP', f'📱 {donut_sbp_name}'),
                    callback_data=_build_callback('donut_sbp'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_donut_sbp_qr_enabled():
        donut_qr_name = settings.get_donut_sbp_qr_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_DONUT_SBP_QR', f'🏦 {donut_qr_name}'),
                    callback_data=_build_callback('donut_sbp_qr'),
                )
            ]
        )
        has_direct_payment_methods = True

    if (
        settings.is_donut_enabled()
        and not settings.is_donut_card_enabled()
        and not settings.is_donut_sbp_enabled()
        and not settings.is_donut_sbp_qr_enabled()
    ):
        donut_name = settings.get_donut_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_DONUT', f'🍩 {donut_name}'),
                    callback_data=_build_callback('donut'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_lava_card_enabled():
        lava_card_name = settings.get_lava_card_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_LAVA_CARD', f'💳 {lava_card_name}'),
                    callback_data=_build_callback('lava_card'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_lava_sbp_enabled():
        lava_sbp_name = settings.get_lava_sbp_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_LAVA_SBP', f'📱 {lava_sbp_name}'),
                    callback_data=_build_callback('lava_sbp'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_lava_enabled() and not settings.is_lava_card_enabled() and not settings.is_lava_sbp_enabled():
        lava_name = settings.get_lava_display_name()
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_LAVA', f'🌋 {lava_name}'),
                    callback_data=_build_callback('lava'),
                )
            ]
        )
        has_direct_payment_methods = True

    if settings.is_support_topup_enabled():
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENT_VIA_SUPPORT', '🛠️ Через поддержку'), callback_data='topup_support'
                )
            ]
        )

    if not keyboard:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENTS_TEMPORARILY_UNAVAILABLE', '⚠️ Способы оплаты временно недоступны'),
                    callback_data='payment_methods_unavailable',
                )
            ]
        )
    elif not has_direct_payment_methods and settings.is_support_topup_enabled():
        keyboard.insert(
            0,
            [
                InlineKeyboardButton(
                    text=texts.t('PAYMENTS_TEMPORARILY_UNAVAILABLE', '⚠️ Способы оплаты временно недоступны'),
                    callback_data='payment_methods_unavailable',
                )
            ],
        )

    keyboard.append([InlineKeyboardButton(text=texts.BACK, callback_data='menu_balance')])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_yookassa_payment_keyboard(
    payment_id: str, amount_kopeks: int, confirmation_url: str, language: str = DEFAULT_LANGUAGE
) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=texts.t('PAY_NOW_BUTTON', '💳 Оплатить'), url=confirmation_url)],
            [
                InlineKeyboardButton(
                    text=texts.t('CHECK_STATUS_BUTTON', '📊 Проверить статус'),
                    callback_data=f'check_yookassa_status_{payment_id}',
                )
            ],
            [InlineKeyboardButton(text=texts.t('MY_BALANCE_BUTTON', '💰 Мой баланс'), callback_data='menu_balance')],
        ]
    )


def get_referral_keyboard(language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    texts = get_texts(language)

    keyboard = [
        [
            InlineKeyboardButton(
                text=texts.t('CREATE_INVITE_BUTTON', '📝 Создать приглашение'), callback_data='referral_create_invite'
            )
        ],
        [InlineKeyboardButton(text=texts.t('SHOW_QR_BUTTON', '📱 Показать QR код'), callback_data='referral_show_qr')],
        [
            InlineKeyboardButton(
                text=texts.t('REFERRAL_LIST_BUTTON', '👥 Список рефералов'), callback_data='referral_list'
            )
        ],
        [
            InlineKeyboardButton(
                text=texts.t('REFERRAL_ANALYTICS_BUTTON', '📊 Аналитика'), callback_data='referral_analytics'
            )
        ],
    ]

    # Добавляем кнопку вывода, если включена
    if settings.is_referral_withdrawal_enabled():
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('REFERRAL_WITHDRAWAL_BUTTON', '💸 Запросить вывод'),
                    callback_data='referral_withdrawal',
                )
            ]
        )

    keyboard.append([InlineKeyboardButton(text=texts.BACK, callback_data='back_to_menu')])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_support_keyboard(language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    try:
        from app.services.support_settings_service import SupportSettingsService

        tickets_enabled = SupportSettingsService.is_tickets_enabled()
        contact_enabled = SupportSettingsService.is_contact_enabled()
    except Exception:
        tickets_enabled = True
        contact_enabled = True
    rows: list[list[InlineKeyboardButton]] = []
    # Tickets
    if tickets_enabled:
        rows.append(
            [
                InlineKeyboardButton(
                    text=texts.t('CREATE_TICKET_BUTTON', '🎫 Создать тикет'), callback_data='create_ticket'
                )
            ]
        )
        rows.append(
            [InlineKeyboardButton(text=texts.t('MY_TICKETS_BUTTON', '📋 Мои тикеты'), callback_data='my_tickets')]
        )
    # Direct contact
    if contact_enabled and settings.get_support_contact_url():
        rows.append(
            [
                InlineKeyboardButton(
                    text=texts.t('CONTACT_SUPPORT_BUTTON', '💬 Связаться с поддержкой'),
                    url=settings.get_support_contact_url() or 'https://t.me/',
                )
            ]
        )
    rows.append([InlineKeyboardButton(text=texts.BACK, callback_data='back_to_menu')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_pagination_keyboard(
    current_page: int, total_pages: int, callback_prefix: str, language: str = DEFAULT_LANGUAGE
) -> list[list[InlineKeyboardButton]]:
    texts = get_texts(language)
    keyboard = []

    if total_pages > 1:
        row = []

        if current_page > 1:
            row.append(
                InlineKeyboardButton(
                    text=texts.t('PAGINATION_PREV', '⬅️'), callback_data=f'{callback_prefix}_page_{current_page - 1}'
                )
            )

        row.append(InlineKeyboardButton(text=f'{current_page}/{total_pages}', callback_data='current_page'))

        if current_page < total_pages:
            row.append(
                InlineKeyboardButton(
                    text=texts.t('PAGINATION_NEXT', '➡️'), callback_data=f'{callback_prefix}_page_{current_page + 1}'
                )
            )

        keyboard.append(row)

    return keyboard


def get_confirmation_keyboard(
    confirm_data: str, cancel_data: str = 'cancel', language: str = DEFAULT_LANGUAGE
) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=texts.YES, callback_data=confirm_data),
                InlineKeyboardButton(text=texts.NO, callback_data=cancel_data),
            ]
        ]
    )


_PAYMENT_METHOD_LOCALE_KEYS: dict[str, tuple[str, str]] = {
    'bank_card': ('PAYMENT_METHOD_BANK_CARD', '💳 Банковская карта'),
    'yoo_money': ('PAYMENT_METHOD_YOO_MONEY', '🟣 ЮMoney'),
    'sberbank': ('PAYMENT_METHOD_SBERBANK', '🟢 СберPay'),
    'tinkoff_bank': ('PAYMENT_METHOD_TINKOFF_BANK', '🟡 Т-Банк'),
    'sbp': ('PAYMENT_METHOD_SBP', '🏦 СБП'),
    'mir_pay': ('PAYMENT_METHOD_MIR_PAY', '🟦 Mir Pay'),
}


def _get_payment_method_display_name(card, language: str = DEFAULT_LANGUAGE) -> str:
    """Локализованное название метода оплаты + реквизиты."""
    texts = get_texts(language)

    # Для банковских карт title уже содержит тип + маску (например "Visa *4444")
    if card.method_type == 'bank_card' or (not card.method_type and card.card_last4):
        if card.title:
            return card.title
        if card.card_last4:
            return f'{card.card_type or "Card"} *{card.card_last4}'

    # Для остальных методов: локализованное название + реквизиты из title
    locale_entry = _PAYMENT_METHOD_LOCALE_KEYS.get(card.method_type)
    if locale_entry:
        key, default = locale_entry
        method_name = texts.t(key, default)
    else:
        method_name = card.method_type or 'Card'

    if card.title:
        return f'{method_name} {card.title}'
    return method_name


def get_saved_cards_keyboard(cards: list, language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    keyboard = []
    for card in cards:
        card_label = f'🗑 {_get_payment_method_display_name(card, language)}'
        keyboard.append([InlineKeyboardButton(text=card_label, callback_data=f'unlink_card_{card.id}')])
    keyboard.append([InlineKeyboardButton(text=texts.BACK, callback_data='menu_balance')])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_confirm_unlink_keyboard(card_id: int, language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts.t('SAVED_CARDS_CONFIRM_YES', '✅ Да, отвязать'),
                    callback_data=f'confirm_unlink_{card_id}',
                ),
                InlineKeyboardButton(
                    text=texts.t('CANCEL', '❌ Отмена'),
                    callback_data='saved_cards_list',
                ),
            ]
        ]
    )


def get_cryptobot_payment_keyboard(
    payment_id: str,
    local_payment_id: int,
    amount_usd: float,
    asset: str,
    bot_invoice_url: str,
    language: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=texts.t('PAY_WITH_COINS_BUTTON', '🪙 Оплатить'), url=bot_invoice_url)],
            [
                InlineKeyboardButton(
                    text=texts.t('CHECK_STATUS_BUTTON', '📊 Проверить статус'),
                    callback_data=f'check_cryptobot_{local_payment_id}',
                )
            ],
            [InlineKeyboardButton(text=texts.t('MY_BALANCE_BUTTON', '💰 Мой баланс'), callback_data='menu_balance')],
        ]
    )


def get_ticket_cancel_keyboard(language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts.t('CANCEL_TICKET_CREATION', '❌ Отменить создание тикета'),
                    callback_data='cancel_ticket_creation',
                )
            ]
        ]
    )


def get_my_tickets_keyboard(
    tickets: list[dict],
    current_page: int = 1,
    total_pages: int = 1,
    language: str = DEFAULT_LANGUAGE,
    page_prefix: str = 'my_tickets_page_',
) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    keyboard = []

    for ticket in tickets:
        status_emoji = ticket.get('status_emoji', '❓')
        # Override status emoji for closed tickets in admin list
        if ticket.get('is_closed', False):
            status_emoji = '✅'
        title = ticket.get('title', 'Без названия')[:25]
        button_text = f'{status_emoji} #{ticket["id"]} {title}'

        keyboard.append([InlineKeyboardButton(text=button_text, callback_data=f'view_ticket_{ticket["id"]}')])

    # Пагинация
    if total_pages > 1:
        nav_row = []

        if current_page > 1:
            nav_row.append(
                InlineKeyboardButton(
                    text=texts.t('PAGINATION_PREV', '⬅️'), callback_data=f'{page_prefix}{current_page - 1}'
                )
            )

        nav_row.append(InlineKeyboardButton(text=f'{current_page}/{total_pages}', callback_data='current_page'))

        if current_page < total_pages:
            nav_row.append(
                InlineKeyboardButton(
                    text=texts.t('PAGINATION_NEXT', '➡️'), callback_data=f'{page_prefix}{current_page + 1}'
                )
            )

        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton(text=texts.BACK, callback_data='menu_support')])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_ticket_view_keyboard(
    ticket_id: int, is_closed: bool = False, language: str = DEFAULT_LANGUAGE
) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    keyboard = []

    if not is_closed:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('REPLY_TO_TICKET', '💬 Ответить'), callback_data=f'reply_ticket_{ticket_id}'
                )
            ]
        )

    if not is_closed:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('CLOSE_TICKET', '🔒 Закрыть тикет'), callback_data=f'close_ticket_{ticket_id}'
                )
            ]
        )

    keyboard.append([InlineKeyboardButton(text=texts.BACK, callback_data='my_tickets')])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_ticket_reply_cancel_keyboard(language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts.t('CANCEL_REPLY', '❌ Отменить ответ'), callback_data='cancel_ticket_reply'
                )
            ]
        ]
    )


# ==================== ADMIN TICKET KEYBOARDS ====================


def get_admin_tickets_keyboard(
    tickets: list[dict],
    current_page: int = 1,
    total_pages: int = 1,
    language: str = DEFAULT_LANGUAGE,
    scope: str = 'all',
    *,
    back_callback: str = 'admin_submenu_support',
) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    keyboard = []

    # Разделяем открытые/закрытые
    open_rows = []
    closed_rows = []
    for ticket in tickets:
        status_emoji = ticket.get('status_emoji', '❓')
        if ticket.get('is_closed', False):
            status_emoji = '✅'
        user_name = ticket.get('user_name', 'Unknown')
        username = ticket.get('username')
        telegram_id = ticket.get('telegram_id')
        # Сформируем компактное отображение: Имя (@username | ID)
        name_parts = [user_name[:15]]
        contact_parts = []
        if username:
            contact_parts.append(f'@{username}')
        if telegram_id:
            contact_parts.append(str(telegram_id))
        if contact_parts:
            name_parts.append(f'({" | ".join(contact_parts)})')
        name_display = ' '.join(name_parts)
        title = ticket.get('title', 'Без названия')[:20]
        locked_emoji = ticket.get('locked_emoji', '')
        button_text = f'{status_emoji} #{ticket["id"]} {locked_emoji} {name_display}: {title}'.replace('  ', ' ')
        row = [InlineKeyboardButton(text=button_text, callback_data=f'admin_view_ticket_{ticket["id"]}')]
        if ticket.get('is_closed', False):
            closed_rows.append(row)
        else:
            open_rows.append(row)

    # Scope switcher
    switch_row = []
    switch_row.append(
        InlineKeyboardButton(text=texts.t('OPEN_TICKETS', '🔴 Открытые'), callback_data='admin_tickets_scope_open')
    )
    switch_row.append(
        InlineKeyboardButton(text=texts.t('CLOSED_TICKETS', '🟢 Закрытые'), callback_data='admin_tickets_scope_closed')
    )
    keyboard.append(switch_row)

    if open_rows and scope in ('all', 'open'):
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('ADMIN_CLOSE_ALL_OPEN_TICKETS', '🔒 Закрыть все открытые'),
                    callback_data='admin_tickets_close_all_open',
                )
            ]
        )
        keyboard.append(
            [InlineKeyboardButton(text=texts.t('OPEN_TICKETS_HEADER', 'Открытые тикеты'), callback_data='noop')]
        )
        keyboard.extend(open_rows)
    if closed_rows and scope in ('all', 'closed'):
        keyboard.append(
            [InlineKeyboardButton(text=texts.t('CLOSED_TICKETS_HEADER', 'Закрытые тикеты'), callback_data='noop')]
        )
        keyboard.extend(closed_rows)

    # Пагинация
    if total_pages > 1:
        nav_row = []

        if current_page > 1:
            nav_row.append(
                InlineKeyboardButton(
                    text=texts.t('PAGINATION_PREV', '⬅️'), callback_data=f'admin_tickets_page_{scope}_{current_page - 1}'
                )
            )

        nav_row.append(InlineKeyboardButton(text=f'{current_page}/{total_pages}', callback_data='current_page'))

        if current_page < total_pages:
            nav_row.append(
                InlineKeyboardButton(
                    text=texts.t('PAGINATION_NEXT', '➡️'), callback_data=f'admin_tickets_page_{scope}_{current_page + 1}'
                )
            )

        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton(text=texts.BACK, callback_data=back_callback)])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_ticket_view_keyboard(
    ticket_id: int, is_closed: bool = False, language: str = DEFAULT_LANGUAGE, *, is_user_blocked: bool = False
) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    keyboard = []

    if not is_closed:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('REPLY_TO_TICKET', '💬 Ответить'), callback_data=f'admin_reply_ticket_{ticket_id}'
                )
            ]
        )

    if not is_closed:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('CLOSE_TICKET', '🔒 Закрыть тикет'), callback_data=f'admin_close_ticket_{ticket_id}'
                )
            ]
        )

    # Блок-контролы: когда не заблокирован — показать два варианта, когда заблокирован — только "Разблокировать"
    if is_user_blocked:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('UNBLOCK', '✅ Разблокировать'), callback_data=f'admin_unblock_user_ticket_{ticket_id}'
                )
            ]
        )
    else:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.t('BLOCK_FOREVER', '🚫 Заблокировать'),
                    callback_data=f'admin_block_user_perm_ticket_{ticket_id}',
                ),
                InlineKeyboardButton(
                    text=texts.t('BLOCK_BY_TIME', '⏳ Блок по времени'),
                    callback_data=f'admin_block_user_ticket_{ticket_id}',
                ),
            ]
        )

    keyboard.append([InlineKeyboardButton(text=texts.BACK, callback_data='admin_tickets')])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_ticket_reply_cancel_keyboard(language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts.t('CANCEL_REPLY', '❌ Отменить ответ'), callback_data='cancel_admin_ticket_reply'
                )
            ]
        ]
    )
