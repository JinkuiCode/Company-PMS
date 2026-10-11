"""Movement chronology is accounting input; display order is not."""
from datetime import date, datetime
from decimal import Decimal

from app.services.stock_detail_balance import running_balances
from app.services.stock_detail_fields import report_fields
from app.services.report_filters import matches_filters

SORT_TYPES = {f['key']: f['type'] for f in report_fields()}


def chronological_rows(rows):
    return sorted(rows, key=lambda row: (row['bill_date'], row['source_order'],
        row['created_at'], row['bill_no'], row['bill_seq'], row['row_id']))


def display_movements(rows, openings, *, conditions=(), sort='bill_date', direction='asc'):
    if sort not in SORT_TYPES or direction not in {'asc', 'desc'}:
        raise ValueError('Invalid movement display order')
    movements = [row for row in running_balances(chronological_rows(rows), openings)
                 if matches_filters(row, conditions)]
    kind = SORT_TYPES[sort]

    def value(row):
        result = row.get(sort)
        if result is None or kind == 'text' and not str(result).strip():
            return None
        if kind in {'number', 'decimal'}:
            return Decimal(str(result))
        if kind == 'date':
            return result.date() if isinstance(result, datetime) else date.fromisoformat(result) if isinstance(result, str) else result
        return str(result).strip().casefold()

    present, empty = [], []
    for row in movements:
        (empty if value(row) is None else present).append(row)
    # Stable ties retain canonical source chronology in both directions.
    present.sort(key=value, reverse=direction == 'desc')
    return [*present, *empty]
