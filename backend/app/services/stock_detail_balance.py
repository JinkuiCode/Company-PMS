"""Quantity arithmetic for verified, ordered ERP movements (no database access)."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, localcontext


@dataclass(frozen=True)
class InventoryKey:
    organization_id: int
    material_id: int
    stock_id: int
    stock_status_id: int
    owner_type: str
    owner_id: int
    unit_id: int
    keeper_type: str = ''
    keeper_id: int = 0
    stock_location_id: int = 0
    lot_id: int = 0
    auxiliary_property_id: int = 0
    bom_id: int = 0
    mto_no: str = ''
    project_no: str = ''
    produce_date: date | None = None
    expiry_date: date | None = None
    lot_no: str = ''


def quantity(value):
    if not isinstance(value, Decimal):
        raise TypeError('库存数量必须使用Decimal，禁止浮点数参与计算')
    if not value.is_finite():
        raise ValueError('库存数量无效')
    return value


def signed_movement(rule, base_qty, direction=None):
    """Preserve vendor income/issue columns; returns are not swapped positives.

    Source adapters choose a verified rule. Unknown directions fail closed
    rather than reproducing the vendor SQL's catch-all ELSE for malformed data.
    """
    q = quantity(base_qty)
    zero = Decimal(0)
    if rule == 'income':
        return q, zero
    if rule == 'issue':
        return zero, q
    if rule == 'negative_income':
        return q.copy_negate(), zero
    if rule == 'negative_issue':
        return zero, q.copy_negate()
    if rule in ('transfer_in', 'transfer_out'):
        if direction not in ('GENERAL', 'RETURN'):
            raise ValueError('未知调拨方向')
        if rule == 'transfer_in':
            return (q, zero) if direction == 'GENERAL' else (zero, q.copy_negate())
        return (zero, q) if direction == 'GENERAL' else (q.copy_negate(), zero)
    if rule == 'conversion':
        if direction not in ('A', 'B'):
            raise ValueError('未知转换方向')
        return (q, zero) if direction == 'B' else (zero, q)
    raise ValueError('未知库存收发规则')


def stock_quantity(base_qty, numerator, denominator, precision):
    """DLL FBASEQTY * FSTOREURNOM / FSTOREURNUM, then inventory precision."""
    base_qty, numerator, denominator = map(quantity, (base_qty, numerator, denominator))
    if type(precision) is not int or not 0 <= precision <= 10:
        raise ValueError('库存单位精度无效')
    with localcontext() as ctx:
        ctx.prec = 50
        converted = base_qty
        if numerator and denominator:
            scale = Decimal('0.0000000001')
            product = (base_qty * denominator).quantize(scale, rounding=ROUND_HALF_UP)
            converted = (product / numerator).quantize(scale, rounding=ROUND_HALF_UP)
        return converted.quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)


def running_balances(rows, verified_openings):
    """Consume complete chronological movements before slicing pages.

    The reader must explicitly establish every opening, including zero. Missing
    source coverage must not silently become a zero opening. Input quantities
    must already be in the key's unit and retain the ERP direction/sign.
    """
    balances = {key: quantity(value) for key, value in verified_openings.items()}
    for row in rows:
        key = row['inventory_key']
        if key not in balances:
            raise ValueError('库存维度的期初尚未核实')
        with localcontext() as ctx:
            ctx.prec = 50
            balances[key] += quantity(row['income_qty']) - quantity(row['issue_qty'])
        yield {**row, 'balance_qty': balances[key]}


def derive_openings(baseline_date, start_date, verified_baseline, movements):
    """Roll an explicitly verified start-of-day baseline up to the query day.

    The reader supplies a complete interval and explicitly established zero
    dimensions. This function never infers missing dimensions or source coverage.
    """
    if type(baseline_date) is not date or type(start_date) is not date or baseline_date > start_date:
        raise ValueError('期初基点日期无效')
    balances = {key: quantity(value) for key, value in verified_baseline.items()}
    seen = set()
    for row in movements:
        day, identity = row['bill_date'], row['row_id']
        if type(day) is not date or not baseline_date <= day < start_date:
            raise ValueError('期初补算流水超出日期范围')
        if not identity or identity in seen:
            raise ValueError('期初补算流水标识缺失或重复')
        seen.add(identity)
        key = row['inventory_key']
        if key not in balances:
            raise ValueError('库存维度的期初尚未核实')
        with localcontext() as ctx:
            ctx.prec = 50
            balances[key] += quantity(row['income_qty']) - quantity(row['issue_qty'])
    return balances
