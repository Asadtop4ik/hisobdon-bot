from decimal import Decimal, InvalidOperation

MAX_AMOUNT = 10**15


def minor(value: str) -> int:
    try:
        number = Decimal(str(value).replace(' ', '').replace(',', '.')) * 100
        if not number.is_finite() or number != number.to_integral_value() or abs(number) > MAX_AMOUNT:
            raise ValueError('Summa noto‘g‘ri yoki 2 kasrdan ortiq.')
        return int(number)
    except (InvalidOperation, OverflowError) as exc:
        raise ValueError('Summani raqam bilan kiriting.') from exc


def money(value: int, currency: str = '') -> str:
    sign = '-' if value < 0 else ''
    whole, fraction = divmod(abs(value), 100)
    result = f'{sign}{whole:,}'.replace(',', ' ')
    if fraction:
        result += f'.{fraction:02d}'
    return f'{result} {currency}'.strip()
