"""Generate public field definitions for isolated UI tests; never opens a database."""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'backend'))
from app.services.purchase_fields import report_fields, overview_fields, PROGRESS_LABELS, DOCUMENT_STATUSES
from app.services.inventory_fields import report_fields as inventory_fields
from app.services.stock_detail_fields import report_fields as stock_fields
from app.services.report_filters import query_fields, filter_fields

lines = [{'value': 1, 'label': '8吋Bench'}, {'value': 2, 'label': '光伏'}]
purchase = dict(fields=report_fields(), overview_fields=overview_fields(),
    query_fields=query_fields('purchase'), column_filter_fields=query_fields('purchase'),
    overview_query_fields=list({f['field']: f for f in [*query_fields('purchase'), *query_fields('purchase-overview')]}.values()),
    overview_column_filter_fields=query_fields('purchase-overview'), query_schema_version=2,
    progress_labels=PROGRESS_LABELS, document_status_labels=DOCUMENT_STATUSES,
    organizations=lines, start_date='2026-01-01')
inventory = dict(fields=inventory_fields(), query_fields=query_fields('inventory'),
    column_filter_fields=query_fields('inventory'), organizations=lines, query_schema_version=2)
stock = dict(fields=stock_fields(), query_fields=query_fields('stock-detail'),
    column_filter_fields=query_fields('stock-detail'), filter_fields=filter_fields('stock-detail'),
    organizations=lines, sort_fields=[f['key'] for f in stock_fields()],
    default_sort={'sort': 'bill_date', 'direction': 'asc'}, query_schema_version=2,
    summary_scope_note='完整期间汇总（不随附加条件重算）', opening_scope_note='完整查询范围期初')
destination = Path(__file__).parent / 'fixtures/theme-reports.generated.json'
destination.write_text(json.dumps(dict(purchase=purchase, inventory=inventory, stock=stock), ensure_ascii=False, indent=2)+'\n')
print('Generated report field fixtures only; no database or network access')
