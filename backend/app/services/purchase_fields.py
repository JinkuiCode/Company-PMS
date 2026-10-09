"""Single source of report labels, metadata, export and field-catalog entries."""
FIELDS = [
    ('product_line_name', '产品线', 'text', '项目信息', 'T_PUR_REQUISITION', 'FAPPLICATIONORGID', '请购组织匹配 PMS 产品线显示名称；未配置时显示金蝶组织名称并标注未配置产品线，不按项目档案产品线替代'),
    ('project_code', '项目编码', 'text', '项目信息', 'T_BAS_ASSISTANTDATAENTRY', 'FNUMBER', '申请明细项目辅助资料 F_TWBJ_ASSISTANT_83G 对应编码'),
    ('project_name', '项目名称', 'text', '项目信息', 'pms_project_archive', 'project_name', '项目编码精确匹配有权访问的 PMS 档案；无匹配时为空，不回退为金蝶名称'),
    ('material_code', '物料编码', 'text', '物料信息', 'T_BD_MATERIAL', 'FNUMBER', '按申请明细 FMATERIALID 关联'),
    ('material_name', '物料名称', 'text', '物料信息', 'T_BD_MATERIAL_L', 'FNAME', '中文语言 2052'),
    ('specification', '规格型号', 'text', '物料信息', 'T_BD_MATERIAL_L', 'FSPECIFICATION', '中文语言 2052'),
    ('unit_name', '申请单位', 'text', '采购申请', 'T_BD_UNIT_L', 'FNAME', '申请明细 FUNITID；累计数量均换算到此单位'),
    ('bill_no', '申请单编号', 'text', '采购申请', 'T_PUR_REQUISITION', 'FBILLNO', '一行对应一条申请明细，不按物料编码合并'),
    ('line_no', '申请单行号', 'number', '采购申请', 'T_PUR_REQENTRY', 'FSEQ', '单据行号，内部关联使用 FENTRYID'),
    ('application_date', '申请日期', 'date', '采购申请', 'T_PUR_REQUISITION', 'FAPPLICATIONDATE', '使用申请日期，不使用创建日期'),
    ('document_status', '数据状态', 'text', '采购申请', 'T_PUR_REQUISITION', 'FDOCUMENTSTATUS', '金蝶系统固定状态；已审核 C 才计入有效数量'),
    ('close_status', '关闭状态', 'text', '采购申请', 'T_PUR_REQUISITION', 'FCLOSESTATUS', '关闭不会抹去已发生的订单和入库'),
    ('requested', '申请数量', 'number', '采购申请', 'T_PUR_REQENTRY', 'FREQQTY', '保留原申请数量'),
    ('approved', '批准数量', 'number', '采购申请', 'T_PUR_REQENTRY', 'FAPPROVEQTY', '待下单计算基数；使用批准基本数量换算'),
    ('ordered', '累计下单数量', 'number', '采购订单', 'T_PUR_POORDERENTRY_LK', 'FBASEUNITQTY', '汇总当前关联量，排除未审核、作废订单；不用 OLD 数量'),
    ('last_order_date', '最近订单日期', 'date', '采购订单', 'T_PUR_POORDER', 'FDATE', '有效关联订单日期最大值'),
    ('supplier_name', '供应商', 'text', '采购订单', 'T_BD_SUPPLIER_L', 'FNAME', '不同供应商显示多家供应商，逐单名称在明细中展示'),
    ('order_statuses', '订单数据状态', 'text', '采购订单', 'T_PUR_POORDER', 'FDOCUMENTSTATUS', '已验证来源的关联订单状态去重显示，不取单张代表全部'),
    ('received', '累计入库数量', 'number', '采购入库', 'T_STK_INSTOCKENTRY', 'FBASEUNITQTY', '有效实收入库基本数量换算；来源不明确时为空'),
    ('returned', '累计退料数量', 'number', '采购入库', 'T_PUR_MRBENTRY_LK', 'FBASEUNITQTY', '只减有效入库后退料；收料退料不重复扣减'),
    ('net_received', '累计净入库数量', 'number', '采购入库', None, None, '累计入库数量减累计退料数量'),
    ('last_stock_date', '最近入库日期', 'date', '采购入库', 'T_STK_INSTOCK', 'FDATE', '有效关联入库日期最大值'),
    ('stock_statuses', '入库数据状态', 'text', '采购入库', 'T_STK_INSTOCK', 'FDOCUMENTSTATUS', '已验证来源的关联入库状态去重显示，不取单张代表全部'),
    ('pending_order', '待下单数量', 'number', '进度', None, None, '批准数量减累计下单数量；未审核申请为空，超量保留负数'),
    ('pending_receipt', '待入库数量', 'number', '进度', None, None, '累计下单数量减累计净入库数量；超量保留负数'),
    ('progress', '采购进度', 'text', '进度', None, None, '未下单、部分下单、待入库、已完成或数据待核对；系统固定计算状态'),
]

DOCUMENT_STATUSES = {'A': '创建', 'B': '审核中', 'C': '已审核', 'D': '重新审核', 'Z': '暂存'}
PROGRESS_LABELS = {'not_ordered': '未下单', 'ordering': '部分下单', 'receiving': '待入库',
                   'complete': '已完成', 'review': '数据待核对'}


def report_fields():
    return [dict(key=key, label=label, value_type=kind, group=group, description=description,
                 source_table=table, source_column=column, editable=False, list_available=True)
            for key, label, kind, group, table, column, description in FIELDS]


OVERVIEW_COUNTS = [
    ('completion_rate', '申请行完成率', '已完成申请行 / 当前查询条件下全部申请行 × 100；待核对计分母、不计分子'),
    ('total_lines', '申请行数', '当前查询条件下的申请明细行数，按项目编码及请购组织分组'),
    ('not_ordered_lines', '未下单', '采购进度为未下单的申请行数'),
    ('ordering_lines', '部分下单', '采购进度为部分下单的申请行数'),
    ('receiving_lines', '待入库', '采购进度为待入库的申请行数'),
    ('complete_lines', '已完成', '采购进度为已完成的申请行数'),
    ('review_lines', '数据待核对', '采购进度为数据待核对的申请行数'),
]


def overview_fields():
    return [*report_fields()[:3], dict(key='organization_name', label='请购组织', value_type='text',
            group='项目信息', description='当前组合的金蝶请购组织中文名称', editable=False, list_available=True),
            *[dict(key=key, label=label, value_type='number', group='申请行进度',
                   description=description, editable=False, list_available=True)
              for key, label, description in OVERVIEW_COUNTS]]


def catalog_fields():
    return [dict(module='purchase_report', module_name='采购进度查询', group=group,
                 field_name=label, field_code=key, value_type=kind, source_type='system',
                 storage_table=table, storage_column=column, editable=False, computed=table is None,
                 enum_code=None, description=description, catalog_source='PURCHASE_REPORT_FIELDS', sort=100000 + index)
            for index, (key, label, kind, group, table, column, description) in enumerate(FIELDS)] + [
        dict(module='purchase_overview', module_name='采购总进度', group=field['group'],
             field_name=field['label'], field_code=field['key'], value_type=field['value_type'],
             source_type='system', storage_table=None, storage_column=None, editable=False,
             computed=True, enum_code=None, description=field['description'],
             catalog_source='PURCHASE_OVERVIEW_FIELDS', sort=101000 + index)
        for index, field in enumerate(overview_fields())]
