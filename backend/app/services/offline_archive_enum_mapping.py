"""Fixed 2026-10-09 approved aliases. Ambiguous source values stay unchanged.

Only the approved V4 workbook uses these mappings; online enum labels and
existing business references are never rewritten by this module.
"""
import json
from app.models.dict import SysDict,SysDictItem
from app.models.parameter import SysParameter

MAPPING_REVISION = "2026-10-09-merge-01"
SEED_MARKER = "offline_archive_enum_merge_20261009"

APPROVED_ALIASES = {'archive_category': {'AS类': 'AS类',
                      'BS类': 'BS类',
                      'C类': 'C类',
                      'D类': 'D类',
                      '主机': '主机',
                      '免费': '免费',
                      '售后（待分类）': '待分类',
                      '辅机': '辅机'},
 'machine_model': {'12" Single': '12吋 Single',
                   '12"Cassette Less': '12吋 Cassette Less',
                   '12吋"Single': '12吋 Single',
                   '12吋Bench cassette less normal': '12吋Bench cassette less normal',
                   '12吋CassetteLess': '12吋 Cassette Less',
                   '12吋CassetteType': '12吋 Cassette Type',
                   '12吋Single': '12吋 Single',
                   '12＂cassette Less': '12吋 Cassette Less',
                   '12＂Cassette less': '12吋 Cassette Less',
                   '12＂Single': '12吋 Single',
                   '4"&6" Cassette Type': '4/6吋兼容 Cassette Type',
                   '4吋6吋兼容CassetteType': '4/6吋兼容 Cassette Type',
                   '6" Cassette Type': '6吋 Cassette Type',
                   '6"&8" Cassette Type': '6/8吋兼容 Cassette Type',
                   '6"CassetteType': '6吋 Cassette Type',
                   '6&8吋兼容Cassette Type': '6/8吋兼容 Cassette Type',
                   '6.3/8吋兼容CassetteType': '6.3/8吋兼容CassetteType',
                   '6/8吋Single': '6/8吋 Single',
                   '6吋 CassetteType': '6吋 Cassette Type',
                   '6吋CassetteType': '6吋 Cassette Type',
                   '6＂CassetteType': '6吋 Cassette Type',
                   '8" Cassette Less': '8吋 Cassette Less',
                   '8" Cassette Type': '8吋 Cassette Type',
                   '8" Cassetteless': '8吋 Cassette Less',
                   '8" Cssstte Less': '8" Cssstte Less',
                   '8"Cassette type': '8吋 Cassette Type',
                   '8"CassetteLess': '8吋 Cassette Less',
                   '8"CassetteType': '8吋 Cassette Type',
                   '8"Single': '8吋 Single',
                   '8吋 CassetteLess': '8吋 Cassette Less',
                   '8吋 CassetteType': '8吋 Cassette Type',
                   '8＂Cassette type': '8吋 Cassette Type',
                   '8＂CassetteLess': '8吋 Cassette Less',
                   '8＂CassetteType': '8吋 Cassette Type',
                   'HOT SPM': 'HOT SPM',
                   'HotSpm': 'HOT SPM',
                   'Single': 'Single',
                   '辅机': '辅机'},
 'quantity_unit': {'EA': '个',
                   'm': '米',
                   'PCS': '个',
                   '㎡': '㎡',
                   '个': '个',
                   '包': '包',
                   '卷': '卷',
                   '只': '只',
                   '台': '台',
                   '块': '块',
                   '套': '套',
                   '对': '对',
                   '批': '批',
                   '根': '根',
                   '次': '次',
                   '段': '段',
                   '片': '片',
                   '米': '米',
                   '给': '给',
                   '颗': '颗'},
 'sales_company': {'无锡亚电智能装备有限公司': '无锡亚电智能装备有限公司'},
 'legacy_archive_status': {'取消转销售工单': '取消转销售工单',
                           '已发货': '已发货',
                           '已完结': '已完结',
                           '已验收': '已验收',
                           '待开展': '待开展',
                           '待立项': '待立项',
                           '待验收': '待验收',
                           '施工中': '施工中',
                           '项目取消': '项目取消'},
 'equipment_series': {'DF-1500B': 'DF-1500B',
                      'DF-1500TB': 'DF-1500TB',
                      'DF-2000B': 'DF-2000B',
                      'DF-2000LB': 'DF-2000LB',
                      'DF-2000NB': 'DF-2000NB',
                      'DF-2000TB': 'DF-2000TB',
                      'DF-3000B': 'DF-3000B',
                      'DF-3000LB': 'DF-3000LB',
                      'FY-2000S': 'FY-2000S',
                      'FY-3000S': 'FY-3000S',
                      'SZ-0100A': 'SZ-0100A',
                      'SZ-0200B': 'SZ-0200B',
                      'TW-0100A': 'TW-0100A'}}

APPROVED_ENUM_OPTIONS = {'archive_category': ['AS类', 'BS类', 'C类', 'D类', '主机', '免费', '待分类', '辅机'],
 'archive_machine_model': ['12吋 Single',
                           '12吋 Cassette Less',
                           '12吋Bench cassette less normal',
                           '12吋 Cassette Type',
                           '4/6吋兼容 Cassette Type',
                           '6吋 Cassette Type',
                           '6/8吋兼容 Cassette Type',
                           '6.3/8吋兼容CassetteType',
                           '6/8吋 Single',
                           '8吋 Cassette Less',
                           '8吋 Cassette Type',
                           '8" Cssstte Less',
                           '8吋 Single',
                           'HOT SPM',
                           'Single',
                           '辅机'],
 'archive_quantity_unit': ['个',
                           '米',
                           '㎡',
                           '包',
                           '卷',
                           '只',
                           '台',
                           '块',
                           '套',
                           '对',
                           '批',
                           '根',
                           '次',
                           '段',
                           '片',
                           '给',
                           '颗'],
 'archive_sales_company': ['无锡亚电智能装备有限公司'],
 'archive_legacy_archive_status': ['取消转销售工单', '已发货', '已完结', '已验收', '待开展', '待立项', '待验收', '施工中', '项目取消'],
 'equipment_series': ['DF-1500B',
                      'DF-1500TB',
                      'DF-2000B',
                      'DF-2000LB',
                      'DF-2000NB',
                      'DF-2000TB',
                      'DF-3000B',
                      'DF-3000LB',
                      'FY-2000S',
                      'FY-3000S',
                      'SZ-0100A',
                      'SZ-0200B',
                      'TW-0100A']}

def normalize_offline_enum(field,value):
    return APPROVED_ALIASES.get(field,{}).get(value,value)

def initialize_offline_enum_options(db):
    """One-time upgrade preparation, never restore user-disabled/deleted values."""
    if db.get(SysParameter,SEED_MARKER):return
    from app.services.operation_log import record_operation_log,serialize_model
    added=0
    for code,labels in APPROVED_ENUM_OPTIONS.items():
        definition=db.query(SysDict).filter_by(dict_code=code).with_for_update().one()
        items=db.query(SysDictItem).filter_by(dict_id=definition.id).all()
        existing_labels={i.item_label for i in items}
        definition.next_value=max(definition.next_value or 1,max((int(i.item_value) for i in items if i.item_value.isdigit()),default=0)+1)
        for label in labels:
            if label in existing_labels:continue
            item=SysDictItem(dict_id=definition.id,item_label=label,item_value=str(definition.next_value),sort=len(items)+1,status=1)
            definition.next_value+=1;db.add(item);db.flush();items.append(item);existing_labels.add(label);added+=1
            record_operation_log(db,module="业务枚举",action="create",entity_type="sys_enum_item",entity_id=item.id,
                entity_name=label,summary="准备已批准的线下档案枚举",after_data=serialize_model(item))
    db.add(SysParameter(code=SEED_MARKER,value_text=json.dumps({"revision":MAPPING_REVISION,"added":added}),version=1))
    db.commit()
