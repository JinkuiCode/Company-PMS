"""Quantity-only public columns, aligned with the accepted report preview."""
FIELDS = (
    ('product_line_name', '产品线', 'text', 180),
    ('material_code', '物料编码', 'text', 140),
    ('material_name', '物料名称', 'text', 100),
    ('bill_date', '日期', 'date', 110),
    ('bill_name', '单据名称', 'text', 130),
    ('bill_no', '单据编号', 'text', 155),
    ('bill_seq', '行号', 'number', 65),
    ('stock_name', '仓库名称', 'text', 115),
    ('stock_status_name', '库存状态', 'text', 95),
    ('owner_type_name', '货主类型', 'text', 100),
    ('owner_name', '货主', 'text', 210),
    ('unit_name', '库存单位', 'text', 80),
    ('opening_qty', '期初', 'decimal', 95),
    ('income_qty', '收入', 'decimal', 95),
    ('issue_qty', '发出', 'decimal', 95),
    ('balance_qty', '结存', 'decimal', 95),
)

QUERY_ONLY_FIELDS = (('specification', '规格型号', 'text', 140),)


def report_fields():
    return [{'key': key, 'label': label, 'type': kind, 'width': width}
            for key, label, kind, width in FIELDS]


def catalog_fields():
    return [dict(module='stock_detail_report', module_name='物料收发明细', group='物料收发',
        field_name=label, field_code=key, value_type='number' if kind == 'decimal' else kind,
        source_type='system', storage_table='sys_product_line' if key == 'product_line_name' else 'STK_StockDetailRpt',
        storage_column='display_name' if key == 'product_line_name' else key,
        editable=False, computed=key in ('opening_qty', 'balance_qty', 'product_line_name'), enum_code=None,
        description='库存组织 ID 精确匹配 PMS 产品线显示名称；未配置时保留原组织名称并标注未配置产品线' if key == 'product_line_name' else '按金蝶库存报表来源只读计算；详见物料收发明细报表说明',
        catalog_source='STOCK_DETAIL_REPORT_FIELDS', sort=120000 + index)
        for index, (key, label, kind, width) in enumerate((*FIELDS, *QUERY_ONLY_FIELDS))]
