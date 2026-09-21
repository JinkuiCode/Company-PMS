"""Add archive business fields without rewriting historic rows or requirements."""
from datetime import datetime

from sqlalchemy import inspect, select, insert, text

from app.models.field_policy import SysBusinessFieldPolicy


ARCHIVE_BUSINESS_COLUMNS = {
    'product_line_id': 'INT',
    'contract_signed_date': 'DATE',
    'contract_ship_date': 'DATE',
    'actual_ship_date': 'DATE',
    'warranty_end_date': 'DATE',
    'address_province': 'NVARCHAR(6)',
    'address_city': 'NVARCHAR(6)',
    'address_detail': 'NVARCHAR(512)',
    'project_contact': 'NVARCHAR(64)',
    'contact_phone': 'NVARCHAR(32)',
}
CONTRACT_REQUIRED_FIELDS = ('contract_signed_date', 'contract_ship_date')


def upgrade_archive_business_fields(engine) -> None:
    with engine.begin() as connection:
        inspector = inspect(connection)
        if not inspector.has_table('pms_project_archive'):
            return
        columns = {column['name'] for column in inspector.get_columns('pms_project_archive')}
        for name, sql_type in ARCHIVE_BUSINESS_COLUMNS.items():
            if name not in columns:
                connection.execute(text(f'ALTER TABLE pms_project_archive ADD {name} {sql_type} NULL'))
        policy = SysBusinessFieldPolicy.__table__
        cutoff = datetime.now()
        for key in CONTRACT_REQUIRED_FIELDS:
            exists = connection.execute(select(policy.c.id).where(
                policy.c.module_code == 'project_archive', policy.c.field_key == key,
            )).first()
            if not exists:
                connection.execute(insert(policy).values(
                    module_code='project_archive', field_key=key, visible=True,
                    editable=True, required=True, list_available=True,
                    required_effective_at=cutoff,
                ))
