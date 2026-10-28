from sqlalchemy import Engine, inspect, select

from app.models.database_revision import PmsDatabaseRevision


CURRENT_DATABASE_REVISION = "2026-10-27-archive-notice-01"
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
    from app.services.governance_migration import verify_governance_structure
    try:
        with engine.connect() as connection:
            verify_governance_structure(connection)
            from app.services.form_draft_management_migration import verify_draft_management_structure
            verify_draft_management_structure(connection)
            from app.services.archive_policy_revision_migration import REVISION, verify_archive_policy
            verify_archive_policy(connection, strict_values=False)
            from app.services.business_notice_migration import REVISION as NOTICE_REVISION, verify_business_notice_structure
            if CURRENT_DATABASE_REVISION == NOTICE_REVISION:
                verify_business_notice_structure(connection)
    except RuntimeError as exc:
        raise DatabaseUpgradeRequired(str(exc)) from exc


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
