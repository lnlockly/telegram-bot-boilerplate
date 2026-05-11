"""Constants for the menu builder.

The original VPN bot defined connect / subscription / traffic / server-status
buttons here. The boilerplate keeps only product-agnostic entries: balance,
promocode, referrals, contests, support, info, language, admin/moderator
panels.

TODO(boilerplate): add your own product menu entries here.
"""

from typing import Any


MENU_LAYOUT_CONFIG_KEY = 'menu_layout_config'


DEFAULT_MENU_CONFIG: dict[str, Any] = {
    'version': 1,
    'rows': [
        {
            'id': 'balance_row',
            'buttons': ['balance'],
            'conditions': None,
            'max_per_row': 1,
        },
        {
            'id': 'promo_referral_row',
            'buttons': ['promocode', 'referrals'],
            'conditions': None,
            'max_per_row': 2,
        },
        {
            'id': 'contests_row',
            'buttons': ['contests'],
            'conditions': {'contests_visible': True},
            'max_per_row': 2,
        },
        {
            'id': 'support_info_row',
            'buttons': ['support', 'info'],
            'conditions': None,
            'max_per_row': 2,
        },
        {
            'id': 'language_row',
            'buttons': ['language'],
            'conditions': {'language_selection_enabled': True},
            'max_per_row': 2,
        },
        {
            'id': 'admin_row',
            'buttons': ['admin_panel'],
            'conditions': {'is_admin': True},
            'max_per_row': 1,
        },
        {
            'id': 'moderator_row',
            'buttons': ['moderator_panel'],
            'conditions': {'is_moderator': True},
            'max_per_row': 1,
        },
    ],
    'buttons': {
        'balance': {
            'type': 'builtin',
            'builtin_id': 'balance',
            'text': {'ru': '💰 Баланс: {balance}', 'en': '💰 Balance: {balance}'},
            'action': 'menu_balance',
            'enabled': True,
            'visibility': 'all',
            'conditions': None,
            'dynamic_text': True,
        },
        'promocode': {
            'type': 'builtin',
            'builtin_id': 'promocode',
            'text': {'ru': '🎟️ Промокод', 'en': '🎟️ Promo code'},
            'action': 'menu_promocode',
            'enabled': True,
            'visibility': 'all',
            'conditions': None,
            'dynamic_text': False,
        },
        'referrals': {
            'type': 'builtin',
            'builtin_id': 'referrals',
            'text': {'ru': '👥 Рефералы', 'en': '👥 Referrals'},
            'action': 'menu_referrals',
            'enabled': True,
            'visibility': 'all',
            'conditions': {'referral_enabled': True},
            'dynamic_text': False,
        },
        'contests': {
            'type': 'builtin',
            'builtin_id': 'contests',
            'text': {'ru': '🎲 Конкурсы', 'en': '🎲 Contests'},
            'action': 'contests_menu',
            'enabled': True,
            'visibility': 'all',
            'conditions': None,
            'dynamic_text': False,
        },
        'support': {
            'type': 'builtin',
            'builtin_id': 'support',
            'text': {'ru': '💬 Поддержка', 'en': '💬 Support'},
            'action': 'menu_support',
            'enabled': True,
            'visibility': 'all',
            'conditions': {'support_enabled': True},
            'dynamic_text': False,
        },
        'info': {
            'type': 'builtin',
            'builtin_id': 'info',
            'text': {'ru': 'ℹ️ Инфо', 'en': 'ℹ️ Info'},
            'action': 'menu_info',
            'enabled': True,
            'visibility': 'all',
            'conditions': None,
            'dynamic_text': False,
        },
        'language': {
            'type': 'builtin',
            'builtin_id': 'language',
            'text': {'ru': '🌐 Язык', 'en': '🌐 Language'},
            'action': 'menu_language',
            'enabled': True,
            'visibility': 'all',
            'conditions': None,
            'dynamic_text': False,
        },
        'admin_panel': {
            'type': 'builtin',
            'builtin_id': 'admin_panel',
            'text': {'ru': '⚙️ Админ панель', 'en': '⚙️ Admin panel'},
            'action': 'admin_panel',
            'enabled': True,
            'visibility': 'admins',
            'conditions': None,
            'dynamic_text': False,
        },
        'moderator_panel': {
            'type': 'builtin',
            'builtin_id': 'moderator_panel',
            'text': {'ru': '🧑‍⚖️ Модерация', 'en': '🧑‍⚖️ Moderation'},
            'action': 'moderator_panel',
            'enabled': True,
            'visibility': 'moderators',
            'conditions': None,
            'dynamic_text': False,
        },
    },
}


BUILTIN_BUTTONS_INFO: list[dict[str, Any]] = [
    {
        'id': 'balance',
        'default_text': {'ru': '💰 Баланс: {balance}', 'en': '💰 Balance: {balance}'},
        'callback_data': 'menu_balance',
        'default_conditions': None,
        'supports_dynamic_text': True,
    },
    {
        'id': 'promocode',
        'default_text': {'ru': '🎟️ Промокод', 'en': '🎟️ Promo code'},
        'callback_data': 'menu_promocode',
        'default_conditions': None,
        'supports_dynamic_text': False,
    },
    {
        'id': 'referrals',
        'default_text': {'ru': '👥 Рефералы', 'en': '👥 Referrals'},
        'callback_data': 'menu_referrals',
        'default_conditions': {'referral_enabled': True},
        'supports_dynamic_text': False,
    },
    {
        'id': 'contests',
        'default_text': {'ru': '🎲 Конкурсы', 'en': '🎲 Contests'},
        'callback_data': 'contests_menu',
        'default_conditions': {'contests_visible': True},
        'supports_dynamic_text': False,
    },
    {
        'id': 'support',
        'default_text': {'ru': '💬 Поддержка', 'en': '💬 Support'},
        'callback_data': 'menu_support',
        'default_conditions': {'support_enabled': True},
        'supports_dynamic_text': False,
    },
    {
        'id': 'info',
        'default_text': {'ru': 'ℹ️ Инфо', 'en': 'ℹ️ Info'},
        'callback_data': 'menu_info',
        'default_conditions': None,
        'supports_dynamic_text': False,
    },
    {
        'id': 'language',
        'default_text': {'ru': '🌐 Язык', 'en': '🌐 Language'},
        'callback_data': 'menu_language',
        'default_conditions': {'language_selection_enabled': True},
        'supports_dynamic_text': False,
    },
    {
        'id': 'admin_panel',
        'default_text': {'ru': '⚙️ Админ панель', 'en': '⚙️ Admin panel'},
        'callback_data': 'admin_panel',
        'default_conditions': {'is_admin': True},
        'supports_dynamic_text': False,
    },
    {
        'id': 'moderator_panel',
        'default_text': {'ru': '🧑‍⚖️ Модерация', 'en': '🧑‍⚖️ Moderation'},
        'callback_data': 'moderator_panel',
        'default_conditions': {'is_moderator': True},
        'supports_dynamic_text': False,
    },
]


AVAILABLE_CALLBACKS: list[dict[str, Any]] = [
    {
        'callback_data': 'back_to_menu',
        'name': 'Назад в меню',
        'category': 'menu',
        'icon': '⬅️',
        'text': {'ru': '⬅️ Назад', 'en': '⬅️ Back'},
    },
    {
        'callback_data': 'menu_faq',
        'name': 'FAQ',
        'category': 'menu',
        'icon': '❓',
        'text': {'ru': '❓ FAQ', 'en': '❓ FAQ'},
    },
    {
        'callback_data': 'menu_info_promo_groups',
        'name': 'Промо-группы',
        'category': 'menu',
        'icon': '👥',
        'text': {'ru': '👥 Промо-группы', 'en': '👥 Promo groups'},
    },
    {
        'callback_data': 'menu_privacy_policy',
        'name': 'Политика конфиденциальности',
        'category': 'menu',
        'icon': '🔒',
        'text': {'ru': '🔒 Политика конфиденциальности', 'en': '🔒 Privacy Policy'},
    },
    {
        'callback_data': 'menu_public_offer',
        'name': 'Публичная оферта',
        'category': 'menu',
        'icon': '📜',
        'text': {'ru': '📜 Публичная оферта', 'en': '📜 Public Offer'},
    },
    {
        'callback_data': 'menu_rules',
        'name': 'Правила',
        'category': 'menu',
        'icon': '📋',
        'text': {'ru': '📋 Правила', 'en': '📋 Rules'},
    },
    {
        'callback_data': 'balance_history',
        'name': 'История баланса',
        'category': 'balance',
        'icon': '📜',
        'text': {'ru': '📜 История', 'en': '📜 History'},
    },
    {
        'callback_data': 'balance_topup',
        'name': 'Пополнить баланс',
        'category': 'balance',
        'icon': '💳',
        'text': {'ru': '💳 Пополнить', 'en': '💳 Top up'},
    },
    {
        'callback_data': 'referral_create_invite',
        'name': 'Создать инвайт',
        'category': 'referral',
        'icon': '✉️',
        'text': {'ru': '✉️ Создать инвайт', 'en': '✉️ Create invite'},
    },
    {
        'callback_data': 'referral_show_qr',
        'name': 'QR код реферала',
        'category': 'referral',
        'icon': '📱',
        'text': {'ru': '📱 QR код', 'en': '📱 QR code'},
    },
    {
        'callback_data': 'referral_list',
        'name': 'Список рефералов',
        'category': 'referral',
        'icon': '👥',
        'text': {'ru': '👥 Мои рефералы', 'en': '👥 My referrals'},
    },
    {
        'callback_data': 'referral_analytics',
        'name': 'Аналитика рефералов',
        'category': 'referral',
        'icon': '📊',
        'text': {'ru': '📊 Аналитика', 'en': '📊 Analytics'},
    },
    {
        'callback_data': 'create_ticket',
        'name': 'Создать тикет',
        'category': 'support',
        'icon': '✏️',
        'text': {'ru': '✏️ Создать тикет', 'en': '✏️ Create ticket'},
    },
    {
        'callback_data': 'my_tickets',
        'name': 'Мои тикеты',
        'category': 'support',
        'icon': '📋',
        'text': {'ru': '📋 Мои тикеты', 'en': '📋 My tickets'},
    },
]


DYNAMIC_PLACEHOLDERS: list[dict[str, str]] = [
    {'placeholder': '{balance}', 'description': 'Баланс пользователя', 'example': '1 500 ₽', 'category': 'user'},
    {'placeholder': '{username}', 'description': 'Имя пользователя', 'example': 'John', 'category': 'user'},
    {'placeholder': '{referral_count}', 'description': 'Количество рефералов', 'example': '12', 'category': 'referral'},
    {
        'placeholder': '{referral_earnings}',
        'description': 'Заработок с рефералов',
        'example': '500 ₽',
        'category': 'referral',
    },
]
