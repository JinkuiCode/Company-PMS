"""Allow historical null names and remove the legacy project-name uniqueness rule."""
from sqlalchemy import Engine, MetaData, inspect, text
from sqlalchemy.schema import CreateIndex, CreateTable

from app.models.project import PmsProjectArchive


TABLE = "pms_project_archive"
NAME_INDEX = "ux_pms_project_archive_project_name_key"


def _sqlite_rebuild_archive(engine: Engine) -> None:
    model_table = PmsProjectArchive.__table__
    metadata = MetaData()
    for foreign_key in model_table.foreign_keys:
        referenced_table = foreign_key.column.table
        if referenced_table.fullname not in metadata.tables:
            referenced_table.to_metadata(metadata)
    temporary_table = model_table.to_metadata(metadata, name=f"{TABLE}_initial_upgrade")
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
        try:
            with connection.begin():
                old_columns = {column["name"] for column in inspect(connection).get_columns(TABLE)}
                connection.execute(CreateTable(temporary_table))
                copied = [column.name for column in model_table.columns if column.name in old_columns]
                names = ", ".join(f'"{name}"' for name in copied)
                fallback_values = {
                    "created_at": "CURRENT_TIMESTAMP",
                    "updated_at": "CURRENT_TIMESTAMP",
                    "status": "1",
                    "is_enabled": "1",
                    "erp_synced": "0",
                }
                selected = ", ".join(
                    f'COALESCE("{name}", {fallback_values[name]})' if name in fallback_values else f'"{name}"'
                    for name in copied
                )
                connection.execute(text(
                    f'INSERT INTO "{TABLE}_initial_upgrade" ({names}) '
                    f'SELECT {selected} FROM "{TABLE}"'
                ))
                connection.exec_driver_sql(f'DROP TABLE "{TABLE}"')
                connection.exec_driver_sql(
                    f'ALTER TABLE "{TABLE}_initial_upgrade" RENAME TO "{TABLE}"'
                )
                for index in model_table.indexes:
                    connection.execute(CreateIndex(index))
        finally:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()


def _mssql_upgrade_archive(engine: Engine, columns: dict[str, dict]) -> None:
    with engine.begin() as connection:
        if "data_origin" not in columns:
            connection.execute(text(
                "ALTER TABLE pms_project_archive ADD data_origin NVARCHAR(32) "
                "NOT NULL CONSTRAINT DF_pms_project_archive_data_origin DEFAULT 'pms'"
            ))
        indexes = {item["name"] for item in inspect(connection).get_indexes(TABLE)}
        if NAME_INDEX in indexes:
            connection.execute(text(f"DROP INDEX {NAME_INDEX} ON {TABLE}"))
        if not columns["project_name"]["nullable"]:
            connection.execute(text("ALTER TABLE pms_project_archive ALTER COLUMN project_name NVARCHAR(128) NULL"))
        if not columns["project_name_key"]["nullable"]:
            connection.execute(text("ALTER TABLE pms_project_archive ALTER COLUMN project_name_key NVARCHAR(128) NULL"))

def upgrade_project_archive_initial(engine: Engine) -> None:
    inspector = inspect(engine)
    if not inspector.has_table(TABLE):
        return
    columns = {column["name"]: column for column in inspector.get_columns(TABLE)}
    needs_nullable = not columns["project_name"]["nullable"] or not columns["project_name_key"]["nullable"]
    has_name_index = NAME_INDEX in {item["name"] for item in inspector.get_indexes(TABLE)}
    if engine.dialect.name == "sqlite":
        if needs_nullable or "data_origin" not in columns:
            _sqlite_rebuild_archive(engine)
        elif has_name_index:
            with engine.begin() as connection:
                connection.execute(text(f"DROP INDEX {NAME_INDEX}"))
    elif engine.dialect.name == "mssql":
        if needs_nullable or "data_origin" not in columns or has_name_index:
            _mssql_upgrade_archive(engine, columns)
    else:
        raise RuntimeError(f"不支持的数据库方言: {engine.dialect.name}")
