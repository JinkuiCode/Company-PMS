"""The verified view's complete projection; shared by API, export and catalog."""
FIELDS = [
    ('FID', '库存内码', 'text', 150, 'T_STK_INVENTORY.FID；用于精确关联库存组织，不按物料合并'),
    ('Organization', '组织', 'text', 180, '库存组织对应金蝶组织名称；显示源值，权限按FSTOCKORGID校验'),
    ('Stock', '仓库', 'text', 130, '库存仓库对应T_BD_STOCK_L.FNAME'),
    ('MaterialCode', '物料编码', 'text', 150, 'T_BD_MATERIAL.FNUMBER'),
    ('MaterialName', '物料名称', 'text', 210, 'T_BD_MATERIAL_L.FNAME'),
    ('FSPECIFICATION', '规格型号', 'text', 250, 'T_BD_MATERIAL_L.FSPECIFICATION'),
    ('Brand', '品牌', 'text', 130, 'T_BD_MATERIAL.F_QKTD_Text1'),
    ('Material', '材质', 'text', 130, 'T_BD_MATERIAL.F_QKTD_Text'),
    ('SupplierNumber', '供应商编码', 'text', 180, 'T_BD_MATERIAL.F_QKTD_Text2；不是供应商名称'),
    ('FBaseQty', '基本单位数量', 'number', 140, 'CAST(T_STK_INVENTORY.FBaseQty AS decimal(8,2))；视图排除源数量为0，不表示可用库存'),
    ('Unit', '单位', 'text', 90, '物料基本单位FBASEUNITID对应中文单位名称'),
]


def report_fields():
    return [dict(key=key, label=label, value_type=kind, width=width, group='即时库存',
                 description=description, editable=False, list_available=True)
            for key, label, kind, width, description in FIELDS]


def catalog_fields():
    return [dict(module='inventory_report', module_name='即时库存查询', group='即时库存',
        field_name=label, field_code=key, value_type=kind, source_type='system',
        storage_table='YD_JIN_INVENTORY', storage_column=key, editable=False, computed=False,
        enum_code=None, description=description, catalog_source='INVENTORY_REPORT_FIELDS', sort=110000+i)
        for i, (key,label,kind,width,description) in enumerate(FIELDS)]
