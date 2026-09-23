"""Data scope only; never grants a business action or bypasses validation."""
ALL_BUSINESS_DATA = 'business:data:all'
ALL_DATA_SCOPE = object()


def has_all_business_data(context):
    return bool(context and ALL_BUSINESS_DATA in context.get('permissions', []))
