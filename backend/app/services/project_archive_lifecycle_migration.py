"""项目档案生命周期字段的幂等数据库兼容升级。"""
from sqlalchemy import Engine, inspect, text


def upgrade_project_archive_lifecycle(engine: Engine) -> None:
    """补齐项目档案启用状态字段和索引。"""
    inspector = inspect(engine)
    if not inspector.has_table("pms_project_archive"):
        return
    columns = {item["name"] for item in inspector.get_columns("pms_project_archive")}
    with engine.begin() as connection:
        if "is_enabled" not in columns:
            connection.execute(text(
                "ALTER TABLE pms_project_archive "
                "ADD is_enabled INT NOT NULL DEFAULT 1"
            ))
        indexes = {item["name"] for item in inspect(connection).get_indexes("pms_project_archive")}
        if "idx_project_archive_enabled" not in indexes:
            connection.execute(text(
                "CREATE INDEX idx_project_archive_enabled "
                "ON pms_project_archive (is_enabled)"
            ))
