"""Archive diff order matching the approved create form; other resources stay unchanged."""
ARCHIVE_BASIC_ORDER = (
    'archive_category', 'project_code', 'project_name', 'customer', 'product_line_id',
    'quantity', 'quantity_unit', 'manager_id', 'machine_model', 'equipment_series', 'serial_no',
)
ARCHIVE_FORM_ORDER = ARCHIVE_BASIC_ORDER + (
    'contract_signed_date', 'contract_ship_date', 'actual_ship_date', 'warranty_end_date',
    'address_province', 'address_city', 'address_detail', 'project_contact', 'contact_phone',
    'sales_company', 'legacy_archive_status', 'legacy_code_date', 'legacy_updated_date',
    'delivery_note', 'remarks',
)
_ORDER = {field: index for index, field in enumerate(ARCHIVE_FORM_ORDER)}


def order_archive_log_items(entity_type, items):
    if entity_type != 'pms_project_archive':
        return items
    def rank(item):
        field = item['field_key']
        field = {'business_product_line_id': 'product_line_id'}.get(field, field)
        return _ORDER.get(field, len(_ORDER))
    # Stable sorting preserves the existing order of system/unknown fields.
    return sorted(items, key=rank)
