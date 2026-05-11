def format_period_description(period_days: int, language: str = "ru") -> str:
    if period_days <= 0:
        return "—"
    if period_days % 30 == 0:
        months = period_days // 30
        if language == "en":
            return f"{months} month{'s' if months != 1 else ''}"
        return f"{months} мес."
    if language == "en":
        return f"{period_days} day{'s' if period_days != 1 else ''}"
    return f"{period_days} дн."
