from django import template

register = template.Library()


@register.filter
def ru_wines(value):
    """
    Возвращает правильную форму слова «вино» по правилам русского языка.
    Примеры: 0 вин, 1 вино, 2 вина, 5 вин, 11 вин, 21 вино.
    """
    try:
        n = int(value)
    except (TypeError, ValueError):
        return "вин"

    last_two = n % 100
    last_one = n % 10

    if 11 <= last_two <= 19:
        return "вин"
    if last_one == 1:
        return "вино"
    if 2 <= last_one <= 4:
        return "вина"
    return "вин"
