"""Pure procurement accounting; the reader must supply complete source edges.

The SQL adapter owns state decoding and authorization. ``effective`` must be a
validated boolean, never a truthy raw ERP status code. All quantities passed to
this layer are basic-unit quantities except the request's display quantities.
"""
from decimal import Decimal, InvalidOperation, localcontext


def _quantity(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() and number >= 0 else None


def summarize_requisition(request, orders, links, receipts, returns=(), *, complete=False):
    """Return Decimal totals, or None plus issues when a total cannot be proved.

    ``links`` includes ALL application sources for the supplied order entries,
    including other applications, so a merged order cannot be misallocated.
    Receipts and returns must be complete for these orders, not paginated.
    This function does not select visible rows or grant access to a report.
    """
    with localcontext() as context:
        context.prec = 38
        if complete is not True:
            return dict(requested=_quantity(request.get('requested')), approved=_quantity(request.get('approved')),
                        ordered=None, received=None, returned=None, net_received=None,
                        pending_order=None, pending_receipt=None, issues=['incomplete_chain'])
        return _summarize(request, orders, links, receipts, returns)


def _summarize(request, orders, links, receipts, returns):
    issues = set()
    approved = _quantity(request.get('approved'))
    approved_base = _quantity(request.get('approved_base'))
    conversion_ok = approved is not None and approved > 0 and approved_base is not None and approved_base > 0
    if not conversion_ok:
        issues.add('unresolved_unit_conversion')
    order_map = {}
    for order in orders:
        if order['id'] in order_map:
            issues.add('duplicate_order')
        order_map[order['id']] = order
    relevant = [link for link in links if link['request_id'] == request['id']]
    relevant_ids = {link['order_id'] for link in relevant}
    sources = {}
    for link in links:
        sources.setdefault(link['order_id'], set()).add(link['request_id'])
    order_ok = 'duplicate_order' not in issues and conversion_ok
    ordered_base = Decimal(0)
    active_orders = set()
    seen_links = set()
    for link in relevant:
        identity = (link['order_id'], link['request_id'], link.get('request_bill_id'))
        if identity in seen_links:
            issues.add('duplicate_order_allocation')
            order_ok = False
            continue
        seen_links.add(identity)
        order = order_map.get(link['order_id'])
        if (not order or request['bill_id'] is None or request['material_id'] is None
                or link.get('request_bill_id') != request['bill_id'] or order.get('material_id') != request['material_id']):
            issues.add('order_source_mismatch')
            order_ok = False
            continue
        if order.get('effective') is False:
            continue
        if order.get('effective') is not True:
            issues.add('unknown_order_state')
            order_ok = False
            continue
        active_orders.add(order['id'])
        quantity = _quantity(link.get('base_qty'))
        if request['base_unit_id'] is None or order.get('base_unit_id') != request['base_unit_id'] or quantity is None:
            issues.add('invalid_order_quantity_or_unit')
            order_ok = False
            continue
        ordered_base += quantity

    received_base = Decimal(0)
    receipt_ok = order_ok
    valid_receipts = {}
    seen_receipts = set()
    for receipt in receipts:
        order_id = receipt.get('order_id')
        if order_id not in relevant_ids:
            continue
        if receipt['id'] in seen_receipts:
            issues.add('duplicate_receipt')
            receipt_ok = False
            continue
        seen_receipts.add(receipt['id'])
        if receipt.get('effective') is False:
            continue
        if receipt.get('effective') is not True or order_id not in active_orders:
            issues.add('receipt_state_or_source_conflict')
            receipt_ok = False
            continue
        if len(sources[order_id]) != 1:
            issues.add('ambiguous_receipt_allocation')
            receipt_ok = False
            continue
        if receipt.get('material_id') != request['material_id']:
            issues.add('receipt_material_mismatch')
            receipt_ok = False
            continue
        if receipt.get('base_unit_id') != request['base_unit_id']:
            issues.add('receipt_unit_mismatch')
            receipt_ok = False
            continue
        quantity = _quantity(receipt.get('base_qty'))
        if quantity is None:
            issues.add('invalid_receipt_quantity')
            receipt_ok = False
            continue
        valid_receipts[receipt['id']] = quantity
        received_base += quantity

    returned_base = Decimal(0)
    return_ok = receipt_ok
    seen_returns = set()
    returned_by_receipt = {}
    for row in returns:
        if row.get('effective') is False or row.get('source_kind') == 'receive':
            continue
        if row['id'] in seen_returns:
            issues.add('duplicate_return')
            return_ok = False
            continue
        seen_returns.add(row['id'])
        quantity = _quantity(row.get('base_qty'))
        receipt_id = row.get('receipt_id')
        if (row.get('effective') is not True or row.get('source_kind') != 'stock'
                or receipt_id not in valid_receipts or quantity is None
                or row.get('base_unit_id') != request['base_unit_id']
                or row.get('material_id') != request['material_id']):
            issues.add('unresolved_return')
            return_ok = False
            continue
        returned_base += quantity
        returned_by_receipt[receipt_id] = returned_by_receipt.get(receipt_id, Decimal(0)) + quantity
    if any(qty > valid_receipts[key] for key, qty in returned_by_receipt.items()):
        issues.add('return_exceeds_receipt')
        return_ok = False
    # Subtract in base units before conversion; do not classify rounded display quantities.
    pending_order_base = approved_base - ordered_base if request.get('effective') is True and order_ok else None
    net_received_base = received_base - returned_base if return_ok else None
    pending_receipt_base = ordered_base - net_received_base if order_ok and return_ok else None
    def display(quantity):
        return quantity * approved / approved_base if quantity is not None else None
    ordered = display(ordered_base) if order_ok else None
    received = display(received_base) if receipt_ok else None
    returned = display(returned_base) if return_ok else None
    net_received = display(net_received_base)
    pending_order = display(pending_order_base)
    pending_receipt = display(pending_receipt_base)
    if pending_order_base is not None and pending_order_base < 0:
        issues.add('over_ordering')
    if pending_receipt_base is not None and pending_receipt_base < 0:
        issues.add('over_delivery')
    return dict(requested=_quantity(request.get('requested')), approved=approved, ordered=ordered,
                received=received, returned=returned, net_received=net_received,
                pending_order=pending_order, pending_receipt=pending_receipt,
                ordered_base=ordered_base if order_ok else None,
                pending_order_base=pending_order_base, pending_receipt_base=pending_receipt_base,
                issues=sorted(issues))
