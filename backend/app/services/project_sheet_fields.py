"""项目总表字段注册表与字段规则。

字段来源：
- archive/project：来自项目档案或项目主表，作为引用字段展示。
- detail：项目总表人工维护字段，存放在 pms_project_sheet_detail.detail_data。
- computed：由 PMS 源字段实时计算或暂时留空，不能手填。
- system：系统维护字段，不能手填。
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any


PROJECT_SHEET_GROUPS = [
    {"key": "basic", "label": "基础信息"},
    {"key": "progress_notes", "label": "推进记录"},
    {"key": "plan", "label": "计划节点"},
    {"key": "actual", "label": "实际节点"},
    {"key": "stage", "label": "阶段进度"},
    {"key": "product", "label": "产品配置"},
    {"key": "delivery", "label": "交付验收"},
    {"key": "people", "label": "人员分工"},
    {"key": "issues", "label": "问题统计"},
    {"key": "duration", "label": "工期分析"},
    {"key": "system", "label": "系统信息"},
]


def _field(
    sort: int,
    key: str,
    label: str,
    group: str,
    value_type: str = "text",
    source_type: str = "detail",
    editable: bool = True,
    computed: bool = False,
) -> dict[str, Any]:
    is_system_field = source_type == "system"
    return {
        "sort": sort,
        "key": key,
        "label": label,
        "group": group,
        "value_type": value_type,
        "source_type": source_type,
        "editable": editable,
        "computed": computed,
        "list_available": not is_system_field,
        "quick_addable": (not is_system_field) and value_type != "long_text",
    }


PROJECT_SHEET_FIELDS = [
    _field(1, "project_code", "项目号", "basic", source_type="archive", editable=False),
    _field(2, "customer", "客户", "basic"),
    _field(3, "customer_code", "客户端代号", "basic"),
    _field(4, "project_owner", "项目", "basic"),
    _field(5, "progress_notes", "推进记录", "progress_notes", "long_text"),
    _field(6, "duplicate_check", "查重", "system", source_type="computed", editable=False, computed=True),
    _field(7, "order_year", "订单年份", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(8, "node_status", "节点", "basic", "select", source_type="project", editable=True),
    _field(9, "category", "类别", "basic"),
    _field(10, "product_line", "产品类", "basic", source_type="archive", editable=False),
    _field(11, "project_name", "项目名称", "basic", source_type="archive", editable=False),
    _field(12, "equipment_series", "设备系列", "product"),
    _field(13, "serial_no", "序列号", "product"),
    _field(14, "salesperson", "业务员", "people"),
    _field(15, "project_start_date", "立项日期", "basic", "date", source_type="project", editable=True),
    _field(16, "original_planned_ship_date", "原计划发货", "plan", "date", source_type="project", editable=True),
    _field(17, "actual_ship_date", "实际出货", "actual", "date"),
    _field(18, "ship_status", "发货状态", "delivery"),
    _field(19, "po_date", "PO日期", "basic", "date"),
    _field(20, "design_start_date", "设计开始", "plan", "date"),
    _field(21, "plan_order_done_date", "计划下单完", "plan", "date"),
    _field(22, "plan_frame_arrive_date", "计划框架到", "plan", "date"),
    _field(23, "plan_dryer_arrive_date", "计划dryer到", "plan", "date"),
    _field(24, "plan_production_date", "计划生产", "plan", "date"),
    _field(25, "plan_power_on_date", "计划通电", "plan", "date"),
    _field(26, "plan_ship_date", "计划发货", "plan", "date"),
    _field(27, "plan_drawing_done_date", "计划分图完", "plan", "date"),
    _field(28, "plan_purchase_request_done_date", "计划请购完", "plan", "date"),
    _field(29, "plan_test_done_date", "计划测完", "plan", "date"),
    _field(30, "actual_bom_release_date", "实际BOM发", "actual", "date"),
    _field(31, "actual_drawing_done_date", "实际分图完", "actual", "date"),
    _field(32, "actual_cost_accounting_done_date", "实际成本核算完", "actual", "date"),
    _field(33, "actual_purchase_request_done_date", "实际请购完", "actual", "date"),
    _field(34, "actual_order_done_date", "实际下单完", "actual", "date"),
    _field(35, "actual_frame_arrive_date", "实际框架到", "actual", "date"),
    _field(36, "actual_dryer_arrive_date", "实际dryer到", "actual", "date"),
    _field(37, "actual_production_date", "实际生产", "actual", "date"),
    _field(38, "actual_power_on_date", "实际通电", "actual", "date"),
    _field(39, "actual_test_done_date", "实际测完", "actual", "date"),
    _field(40, "bom_release_date", "BOM发出", "actual", "date"),
    _field(41, "design_days", "设计天数", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(42, "drawing_days", "分图天数", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(43, "purchase_request_days", "请购天数", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(44, "material_days", "物料天数", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(45, "assembly_days", "组装天数", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(46, "test_days", "测试天数", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(47, "issue_days", "问题天数", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(48, "teardown_days", "拆机天数", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(49, "rd_stage_duration", "研发阶段工期", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(50, "design_plus_queue_days", "设计加排队时间", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(51, "solution_days", "方案天数", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(52, "rd_queue_days", "研发排队天数", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(53, "design_progress", "设计进度", "stage", "progress", source_type="project", editable=True),
    _field(54, "order_progress", "下单进度", "stage", "progress", source_type="project", editable=True),
    _field(55, "kit_progress", "齐套进度", "stage", "progress", source_type="project", editable=True),
    _field(56, "frame_progress", "框架进度", "stage", "progress", source_type="project", editable=True),
    _field(57, "dryer_progress", "dryer进度", "stage", "progress", source_type="project", editable=True),
    _field(58, "assembly_progress", "组装进度", "stage", "progress", source_type="project", editable=True),
    _field(59, "test_progress", "测试进度", "stage", "progress", source_type="project", editable=True),
    _field(60, "substrate_type", "硅基/化合物", "product"),
    _field(61, "wafer_size", "Wafer尺寸", "product"),
    _field(62, "type_less", "Type/Less", "product"),
    _field(63, "single_double", "单/双", "product"),
    _field(64, "in_factory_cycle", "厂内周期", "duration", "number"),
    _field(65, "planned_ship_year", "计划出货年份", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(66, "actual_ship_year", "实际出货年份", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(67, "planned_ship_month", "计划出货月份", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(68, "planned_ship_year_month", "计划出货-提取年月", "duration", source_type="computed", editable=False, computed=True),
    _field(69, "actual_ship_year_month", "实际出货-提取年月", "duration", source_type="computed", editable=False, computed=True),
    _field(70, "actual_ship_month", "实际出货月份", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(71, "mechanical_bom_versions", "机械BOM版本数", "issues", "number"),
    _field(72, "production_issue_count", "生产过程问题数", "issues", "number"),
    _field(73, "customer_release", "交付客户Release", "delivery"),
    _field(74, "delivery_cycle", "交付周期", "duration", "number"),
    _field(75, "bench_single", "Bench/Single", "product"),
    _field(76, "actual_acceptance_date", "实际验收日期", "delivery", "date"),
    _field(77, "warranty_months", "质保时间(M)", "delivery", "number"),
    _field(78, "warranty_end_date", "质保截止时间", "delivery", "date", source_type="computed", editable=False, computed=True),
    _field(79, "last_editor", "最后编辑人", "system", source_type="system", editable=False),
    _field(80, "last_edit_time", "最后编辑时间", "system", "datetime", source_type="system", editable=False),
    _field(81, "powered_on_days", "已通电天数", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(82, "normal_project_start", "是否正常立项", "duration", source_type="computed", editable=False, computed=True),
    _field(83, "start_to_ship_days", "立项发货天数", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(84, "order_to_ship_days", "订单发货天数", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(85, "actual_start_to_bom_days", "实际立项BOM工期", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(86, "actual_assembly_days", "实际组装工期", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(87, "actual_test_days", "实际测试工期", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(88, "actual_drawing_days", "实际分图工期", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(89, "actual_purchase_request_days", "实际请购工期", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(90, "actual_order_days", "实际下单工期", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(91, "actual_material_follow_days", "实际追料工期", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(92, "project_address", "项目地址", "delivery", "long_text"),
    _field(93, "electrical_bom_versions", "电气BOM版本数", "issues", "number"),
    _field(94, "rd_issue_count", "研发问题数", "issues", "number"),
    _field(95, "supplier_issue_count", "供应商问题数", "issues", "number"),
    _field(96, "solution_engineer", "方案工程", "people"),
    _field(97, "mechanical_designer", "机械设计", "people"),
    _field(98, "electrical_designer", "电气设计", "people"),
    _field(99, "plc_engineer", "PLC", "people"),
    _field(100, "pc_engineer", "PC", "people"),
    _field(101, "process_engineer", "工艺", "people"),
    _field(102, "assembly_owner", "组装", "people"),
    _field(103, "test_owner", "测试", "people"),
    _field(104, "installation_owner", "装机", "people"),
    _field(105, "after_sales_owner", "售后", "people"),
    _field(106, "quality_owner", "质量", "people"),
    _field(107, "arrival_date", "到货时间", "delivery", "date"),
    _field(108, "movein_date", "Movein时间", "delivery", "date"),
    _field(109, "difference_days", "差异天数", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(110, "text_note", "文本", "progress_notes", "long_text"),
    _field(111, "actual_acceptance_year", "实际验收年份", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(112, "rd_start_month", "研发开始月", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(113, "rd_end_month", "研发结束月", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(114, "purchase_start_month", "采购开始月", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(115, "production_start_month", "生产开始月", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(116, "test_start_month", "测试开始月", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(117, "rd_duration_ratio", "研发工期占比", "duration", "percent", source_type="computed", editable=False, computed=True),
    _field(118, "purchase_duration_ratio", "采购工期占比", "duration", "percent", source_type="computed", editable=False, computed=True),
    _field(119, "assembly_duration_ratio", "组装工期占比", "duration", "percent", source_type="computed", editable=False, computed=True),
    _field(120, "test_duration_ratio", "测试工期占比", "duration", "percent", source_type="computed", editable=False, computed=True),
    _field(121, "rd_start_year", "研发开始年", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(122, "project_start_month", "立项月", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(123, "process_start_date", "工艺开始", "actual", "date"),
    _field(124, "process_end_date", "工艺结束", "actual", "date"),
    _field(125, "process_duration_days", "工艺工期", "duration", "number", source_type="computed", editable=False, computed=True),
    _field(126, "configuration", "配置", "product", "long_text"),
]

FIELD_BY_KEY = {field["key"]: field for field in PROJECT_SHEET_FIELDS}
GROUP_BY_KEY = {group["key"]: group for group in PROJECT_SHEET_GROUPS}
DETAIL_EDITABLE_KEYS = {
    field["key"]
    for field in PROJECT_SHEET_FIELDS
    if field["source_type"] == "detail" and field["editable"]
}


def normalize_sheet_field_keys(raw_keys: str | list[str] | tuple[str, ...] | None) -> list[str]:
    """规范化动态列表字段 key，去重并忽略未知/不可展示字段。"""
    if raw_keys is None:
        return []

    if isinstance(raw_keys, str):
        candidates = raw_keys.split(",")
    else:
        candidates = list(raw_keys)

    normalized: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.strip() if isinstance(candidate, str) else ""
        if not key or key in seen:
            continue

        field = FIELD_BY_KEY.get(key)
        if not field or not field["list_available"]:
            continue

        normalized.append(key)
        seen.add(key)
    return normalized


def _field_metadata(field: dict[str, Any]) -> dict[str, Any]:
    return dict(field)


def get_project_sheet_field_metadata() -> dict[str, list[dict[str, Any]]]:
    """返回项目总表字段元数据，不包含具体项目值。"""
    fields = [_field_metadata(field) for field in PROJECT_SHEET_FIELDS]
    fields_by_group: dict[str, list[dict[str, Any]]] = {group["key"]: [] for group in PROJECT_SHEET_GROUPS}
    for field in fields:
        fields_by_group[field["group"]].append(field)

    groups = [
        {
            "key": group["key"],
            "label": group["label"],
            "fields": fields_by_group[group["key"]],
        }
        for group in PROJECT_SHEET_GROUPS
    ]
    return {"groups": groups, "fields": fields}


def validate_sheet_detail_updates(values: dict[str, Any]) -> dict[str, Any]:
    """只允许更新人工维护字段，引用字段和计算字段一律拒绝。"""
    accepted: dict[str, Any] = {}
    for key, value in values.items():
        field = FIELD_BY_KEY.get(key)
        if not field:
            raise ValueError(f"未知字段：{key}")
        if key not in DETAIL_EDITABLE_KEYS:
            raise ValueError(f"字段不可编辑：{field['label']}")
        accepted[key] = _normalize_value(value, field["value_type"])
    return accepted


def _normalize_value(value: Any, value_type: str) -> Any:
    if value == "":
        return None
    if value is None:
        return None
    if value_type in {"number", "progress"}:
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    return value


def _as_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                return None
    return None


def _date_diff_days(start: Any, end: Any) -> int | None:
    start_date = _as_date(start)
    end_date = _as_date(end)
    if not start_date or not end_date:
        return None
    return (end_date - start_date).days


def _year(value: Any) -> int | None:
    parsed = _as_date(value)
    return parsed.year if parsed else None


def _month(value: Any) -> int | None:
    parsed = _as_date(value)
    return parsed.month if parsed else None


def _year_month(value: Any) -> str | None:
    parsed = _as_date(value)
    return f"{parsed.year}-{parsed.month:02d}" if parsed else None


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ratio(part: Any, total: Any) -> float | None:
    part_num = _number(part)
    total_num = _number(total)
    if part_num is None or not total_num:
        return None
    return round(part_num / total_num * 100, 2)


def compute_sheet_field_value(key: str, values: dict[str, Any]) -> Any:
    """计算字段。无法可靠计算时返回 None，由前端显示“待计算”。"""
    computed_map = {
        "order_year": lambda: _year(values.get("po_date")),
        "planned_ship_year": lambda: _year(values.get("plan_ship_date") or values.get("original_planned_ship_date")),
        "actual_ship_year": lambda: _year(values.get("actual_ship_date")),
        "planned_ship_month": lambda: _month(values.get("plan_ship_date") or values.get("original_planned_ship_date")),
        "planned_ship_year_month": lambda: _year_month(values.get("plan_ship_date") or values.get("original_planned_ship_date")),
        "actual_ship_year_month": lambda: _year_month(values.get("actual_ship_date")),
        "actual_ship_month": lambda: _month(values.get("actual_ship_date")),
        "design_days": lambda: _date_diff_days(values.get("design_start_date"), values.get("actual_bom_release_date") or values.get("plan_order_done_date")),
        "drawing_days": lambda: _date_diff_days(values.get("actual_bom_release_date"), values.get("actual_drawing_done_date")),
        "purchase_request_days": lambda: _date_diff_days(values.get("actual_drawing_done_date"), values.get("actual_purchase_request_done_date")),
        "material_days": lambda: _date_diff_days(values.get("actual_order_done_date"), values.get("actual_frame_arrive_date")),
        "assembly_days": lambda: _date_diff_days(values.get("actual_frame_arrive_date"), values.get("actual_power_on_date")),
        "test_days": lambda: _date_diff_days(values.get("actual_power_on_date"), values.get("actual_test_done_date")),
        "rd_stage_duration": lambda: _date_diff_days(values.get("design_start_date"), values.get("actual_bom_release_date")),
        "actual_start_to_bom_days": lambda: _date_diff_days(values.get("project_start_date"), values.get("actual_bom_release_date")),
        "actual_assembly_days": lambda: _date_diff_days(values.get("actual_frame_arrive_date"), values.get("actual_power_on_date")),
        "actual_test_days": lambda: _date_diff_days(values.get("actual_power_on_date"), values.get("actual_test_done_date")),
        "actual_drawing_days": lambda: _date_diff_days(values.get("actual_bom_release_date"), values.get("actual_drawing_done_date")),
        "actual_purchase_request_days": lambda: _date_diff_days(values.get("actual_drawing_done_date"), values.get("actual_purchase_request_done_date")),
        "actual_order_days": lambda: _date_diff_days(values.get("actual_purchase_request_done_date"), values.get("actual_order_done_date")),
        "actual_material_follow_days": lambda: _date_diff_days(values.get("actual_order_done_date"), values.get("actual_frame_arrive_date")),
        "warranty_end_date": lambda: None,
        "powered_on_days": lambda: _date_diff_days(values.get("actual_power_on_date"), date.today()),
        "start_to_ship_days": lambda: _date_diff_days(values.get("project_start_date"), values.get("actual_ship_date") or values.get("plan_ship_date")),
        "order_to_ship_days": lambda: _date_diff_days(values.get("po_date"), values.get("actual_ship_date") or values.get("plan_ship_date")),
        "actual_acceptance_year": lambda: _year(values.get("actual_acceptance_date")),
        "rd_start_month": lambda: _month(values.get("design_start_date")),
        "rd_end_month": lambda: _month(values.get("actual_bom_release_date") or values.get("actual_drawing_done_date")),
        "purchase_start_month": lambda: _month(values.get("actual_purchase_request_done_date")),
        "production_start_month": lambda: _month(values.get("actual_production_date")),
        "test_start_month": lambda: _month(values.get("actual_power_on_date")),
        "rd_start_year": lambda: _year(values.get("design_start_date")),
        "project_start_month": lambda: _month(values.get("project_start_date")),
        "process_duration_days": lambda: _date_diff_days(values.get("process_start_date"), values.get("process_end_date")),
        "difference_days": lambda: _date_diff_days(values.get("plan_ship_date") or values.get("original_planned_ship_date"), values.get("actual_ship_date")),
        "rd_duration_ratio": lambda: _ratio(values.get("rd_stage_duration"), values.get("delivery_cycle")),
        "purchase_duration_ratio": lambda: _ratio(values.get("actual_purchase_request_days"), values.get("delivery_cycle")),
        "assembly_duration_ratio": lambda: _ratio(values.get("actual_assembly_days"), values.get("delivery_cycle")),
        "test_duration_ratio": lambda: _ratio(values.get("actual_test_days"), values.get("delivery_cycle")),
    }
    if key in {"duplicate_check", "issue_days", "teardown_days", "design_plus_queue_days", "solution_days", "rd_queue_days", "normal_project_start"}:
        return None
    compute = computed_map.get(key)
    return compute() if compute else None


def build_sheet_detail_groups(values: dict[str, Any]) -> list[dict[str, Any]]:
    fields_by_group: dict[str, list[dict[str, Any]]] = {group["key"]: [] for group in PROJECT_SHEET_GROUPS}
    for field in PROJECT_SHEET_FIELDS:
        value = compute_sheet_field_value(field["key"], values) if field["computed"] else values.get(field["key"])
        fields_by_group[field["group"]].append({**_field_metadata(field), "value": value})
    return [
        {
            "key": group["key"],
            "label": group["label"],
            "fields": fields_by_group[group["key"]],
        }
        for group in PROJECT_SHEET_GROUPS
    ]
