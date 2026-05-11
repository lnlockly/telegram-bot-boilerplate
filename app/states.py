from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    waiting_for_language = State()
    waiting_for_rules_accept = State()
    waiting_for_privacy_policy_accept = State()
    waiting_for_referral_code = State()


class BalanceStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_pal24_method = State()
    waiting_for_platega_method = State()
    waiting_for_stars_payment = State()
    waiting_for_support_request = State()


class PromoCodeStates(StatesGroup):
    waiting_for_code = State()
    waiting_for_referral_code = State()


class AdminStates(StatesGroup):
    # Stub states kept so legacy admin handlers register at import time.
    # They're unreachable from the boilerplate's keyboards but live in case
    # downstream code re-enables related features.
    adding_traffic = State()
    creating_campaign_subscription_days = State()
    creating_campaign_subscription_devices = State()
    creating_campaign_subscription_servers = State()
    creating_campaign_subscription_traffic = State()
    creating_campaign_tariff_days = State()
    creating_campaign_tariff_select = State()
    creating_promo_group_device_discount = State()
    creating_promo_group_server_discount = State()
    creating_promo_group_traffic_discount = State()
    editing_campaign_subscription_days = State()
    editing_campaign_subscription_devices = State()
    editing_campaign_subscription_servers = State()
    editing_campaign_subscription_traffic = State()
    editing_campaign_tariff_days = State()
    editing_promo_group_device_discount = State()
    editing_promo_group_server_discount = State()
    editing_promo_group_traffic_discount = State()
    editing_promo_offer_test_duration = State()
    editing_traffic_setting = State()
    editing_user_devices = State()
    editing_user_traffic = State()
    extending_subscription = State()
    granting_subscription = State()
    viewing_user_from_potential_customers_list = State()
    viewing_user_from_ready_to_renew_list = State()

    waiting_for_user_search = State()
    waiting_for_bulk_ban_list = State()
    sending_user_message = State()
    editing_user_balance = State()
    editing_user_restriction_reason = State()

    creating_promocode = State()
    setting_promocode_type = State()
    setting_promocode_value = State()
    setting_promocode_uses = State()
    setting_promocode_expiry = State()
    setting_discount_hours = State()  # Для DISCOUNT: ввод срока действия скидки в часах
    selecting_promo_group = State()

    creating_campaign_name = State()
    creating_campaign_start = State()
    creating_campaign_bonus = State()
    creating_campaign_balance = State()

    editing_campaign_name = State()
    editing_campaign_start = State()
    editing_campaign_balance = State()

    waiting_for_broadcast_message = State()
    waiting_for_broadcast_media = State()
    confirming_broadcast = State()

    creating_promo_group_name = State()
    creating_promo_group_priority = State()
    creating_promo_group_period_discount = State()
    creating_promo_group_auto_assign = State()

    editing_promo_group_menu = State()
    editing_promo_group_name = State()
    editing_promo_group_priority = State()
    editing_promo_group_period_discount = State()
    editing_promo_group_auto_assign = State()

    creating_referral_contest_title = State()
    creating_referral_contest_description = State()
    creating_referral_contest_prize = State()
    creating_referral_contest_mode = State()
    creating_referral_contest_start = State()
    creating_referral_contest_end = State()
    creating_referral_contest_time = State()
    editing_referral_contest_summary_times = State()
    adding_virtual_participant_name = State()
    adding_virtual_participant_count = State()
    editing_virtual_participant_count = State()
    # Массовое создание виртуальных участников (массовка)
    adding_mass_virtual_count = State()  # Сколько призраков создать
    adding_mass_virtual_referrals = State()  # По сколько рефералов у каждого
    editing_daily_contest_field = State()
    editing_daily_contest_value = State()

    editing_user_referrals = State()
    editing_user_referral_percent = State()

    # Тестовое начисление реферального дохода
    test_referral_earning_input = State()

    # Диагностика рефералов
    referral_diagnostics_period = State()
    waiting_for_log_file = State()

    editing_rules_page = State()
    editing_privacy_policy = State()
    editing_public_offer = State()
    creating_faq_title = State()
    creating_faq_content = State()
    editing_faq_title = State()
    editing_faq_content = State()
    editing_notification_value = State()

    editing_welcome_text = State()
    editing_pinned_message = State()
    confirming_pinned_broadcast = State()
    waiting_for_message_buttons = 'waiting_for_message_buttons'

    editing_promo_offer_message = State()
    editing_promo_offer_button = State()
    editing_promo_offer_valid_hours = State()
    editing_promo_offer_active_duration = State()
    editing_promo_offer_discount = State()
    selecting_promo_offer_user = State()
    searching_promo_offer_user = State()

    # Состояния для отслеживания источника перехода
    viewing_user_from_balance_list = State()
    viewing_user_from_campaign_list = State()


class SupportStates(StatesGroup):
    waiting_for_message = State()


class TicketStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_message = State()
    waiting_for_reply = State()


class AdminTicketStates(StatesGroup):
    waiting_for_reply = State()
    waiting_for_block_duration = State()


class SupportSettingsStates(StatesGroup):
    waiting_for_desc = State()


class BotConfigStates(StatesGroup):
    waiting_for_value = State()
    waiting_for_search_query = State()
    waiting_for_import_file = State()


class PricingStates(StatesGroup):
    waiting_for_value = State()


class ContestStates(StatesGroup):
    waiting_for_answer = State()


class AdminSubmenuStates(StatesGroup):
    in_users_submenu = State()
    in_promo_submenu = State()
    in_communications_submenu = State()
    in_settings_submenu = State()
    in_system_submenu = State()


class BlacklistStates(StatesGroup):
    waiting_for_blacklist_url = State()


class ReferralWithdrawalStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_payment_details = State()
    confirming = State()
