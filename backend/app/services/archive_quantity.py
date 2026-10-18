"""Quantity business rule, independent of legacy storage and response parsing."""
from decimal import Decimal, InvalidOperation


def validate_archive_quantity(value):
    """Empty is governed by field policy; a supplied quantity must be a positive integer."""
    if value is None or value == '':
        return
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('数量只允许填写正整数') from None
    if not quantity.is_finite() or quantity <= 0 or quantity != quantity.to_integral_value():
        raise ValueError('数量只允许填写正整数')
    if quantity >= Decimal('1e12'):
        raise ValueError('数量最多允许12位正整数')
