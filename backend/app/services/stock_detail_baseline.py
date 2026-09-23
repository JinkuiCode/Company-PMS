"""Select an organization-wide baseline, never a latest material balance row."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta


@dataclass(frozen=True)
class Baseline:
    effective_date: date
    balance_date: date | None = None
    balance_type: int | None = None


def load_baseline(cursor, organization_id, start_date):
    if type(organization_id) is not int or organization_id <= 0 or type(start_date) is not date:
        raise ValueError('库存基点查询条件无效')
    cursor.execute("""SELECT TOP (1) FCLOSEDATE AS close_date FROM dbo.T_STK_CLOSEPROFILE
        WHERE FORGID=%s AND FCATEGORY='STK' AND FCLOSEDATE<%s
        ORDER BY FCLOSEDATE DESC""", (organization_id, start_date))
    closes = cursor.fetchall()
    if closes:
        closed = closes[0]['close_date']
        closed = closed.date() if isinstance(closed, datetime) else closed
        if type(closed) is not date or closed >= start_date:
            raise ValueError('库存结账日期无效')
        cursor.execute("""SELECT TOP (1) 1 AS [exists] FROM dbo.T_STK_INVBAL
            WHERE FSTOCKORGID=%s AND FBALTYPE=0 AND FBALDATE=%s""", (organization_id, closed))
        if not cursor.fetchall():
            raise ValueError('已结账组织缺少库存快照，无法确认期初')
        return Baseline(closed + timedelta(days=1), closed, 0)
    cursor.execute("""SELECT FVALUE AS start_date FROM dbo.T_BAS_SYSTEMPROFILE
        WHERE FORGID=%s AND FCATEGORY='STK' AND FKEY='STARTSTOCKDATE'""", (organization_id,))
    starts = cursor.fetchall()
    if len(starts) != 1:
        raise ValueError('库存启用日期缺失或重复')
    try:
        value = starts[0]['start_date']
        startup = datetime.fromisoformat(str(value).strip()).date()
        initial_day = startup - timedelta(days=1)
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError('库存启用日期无效') from error
    # Initial inventory is a movement on startup minus one day. Reconstruct
    # from that day rather than silently assuming a missing snapshot is zero.
    return Baseline(min(start_date, initial_day))
