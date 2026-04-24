from app.constants import PREMIUM_FEATURES


def render_premium_overview(is_premium: bool) -> str:
    features = "\n".join(f"• {feature}" for feature in PREMIUM_FEATURES.values())
    status = "активен" if is_premium else "не активен"
    return (
        f"Premium сейчас {status}.\n\n"
        "Что будет в Premium:\n"
        f"{features}\n\n"
        "Сейчас это честная заготовка без оплаты: можно посмотреть экран преимуществ и понять направление развития продукта."
    )


def render_premium_stub(feature_name: str, is_premium: bool) -> str:
    if is_premium:
        return (
            f"{feature_name} отмечена как premium-функция. Платежи еще не подключены, "
            "а сама функция пока находится в roadmap-версии."
        )
    return (
        f"{feature_name} относится к Premium. Экран оплаты пока не подключен, "
        "поэтому сейчас это только демонстрация feature flag."
    )
