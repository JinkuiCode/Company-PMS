from sqlalchemy import Engine, inspect, select

from app.models.database_revision import PmsDatabaseRevision


CURRENT_DATABASE_REVISION = "2026-09-23-01"
UPGRADE_IN_PROGRESS = "upgrading"


class DatabaseUpgradeRequired(RuntimeError):
    pass


def check_database_ready(engine: Engine) -> None:
    if not inspect(engine).has_table(PmsDatabaseRevision.__tablename__):
        raise DatabaseUpgradeRequired("数据库尚未升级，请先运行独立数据库升级命令")
    with engine.connect() as connection:
        revision = connection.execute(
            select(PmsDatabaseRevision.revision).where(PmsDatabaseRevision.id == 1)
        ).scalar_one_or_none()
    if revision != CURRENT_DATABASE_REVISION:
        raise DatabaseUpgradeRequired(
            f"数据库版本不匹配：当前 {revision or '未标记'}，需要 {CURRENT_DATABASE_REVISION}"
        )


def mark_database_upgrading(engine: Engine) -> None:
    PmsDatabaseRevision.__table__.create(bind=engine, checkfirst=True)
    _set_revision(engine, UPGRADE_IN_PROGRESS)


def mark_database_ready(engine: Engine) -> None:
    _set_revision(engine, CURRENT_DATABASE_REVISION)


def _set_revision(engine: Engine, revision: str) -> None:
    table = PmsDatabaseRevision.__table__
    with engine.begin() as connection:
        connection.execute(table.delete().where(table.c.id == 1))
        connection.execute(table.insert().values(id=1, revision=revision))
