from datetime import date

# Субота=5, Неділя=6 → вихідні
WEEKEND_DAYS = {5, 6}

def get_price_for_date(check_in_date: date, weekday_price: int, weekend_price: int) -> int:
    """
    Повертає ціну для дати заїзду.
    Weekday = Monday(0)..Thursday(3) → weekday_price
    Weekend = Friday(4), Saturday(5), Sunday(6) → weekend_price
    """
    if check_in_date.weekday() in WEEKEND_DAYS:
        return weekend_price
    return weekday_price

def get_price_label(check_in_date: date, weekday_price: int, weekend_price: int) -> str:
    """
    Повертає рядок з ціною і поясненням для відображення користувачу.
    """
    if check_in_date.weekday() in WEEKEND_DAYS:
        return f"💰 {weekend_price} грн (вихідний день)"
    return f"💰 {weekday_price} грн (будній день)"

def is_weekend(d: date) -> bool:
    return d.weekday() in WEEKEND_DAYS
