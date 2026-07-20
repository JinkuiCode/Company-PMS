from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE_PROGRESS_FIELDS = [
    "design_progress",
    "order_progress",
    "kit_progress",
    "frame_progress",
    "dryer_progress",
    "assembly_progress",
    "test_progress",
]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_project_update_keeps_archive_product_category_read_only() -> None:
    schema = read("app/schemas/project.py")
    model = read("app/models/project.py")
    service = read("app/services/project.py")
    api = read("app/api/projects.py")
    init_db = read("app/models/init_db.py")

    assert "product_category: int | None = None" in schema
    assert 'product_category: Mapped[int | None] = mapped_column(Integer' in model
    assert 'if "product_category" in update_data' in service
    assert "产品类别来自项目档案，请在项目档案中维护" in service
    assert "PmsProjectArchive" in service
    assert "archive.product_category if archive and archive.product_category else p.product_category" in service
    assert "项目未关联档案，无法更新产品类别" not in service
    migration = read("app/services/project_archive_semantic_migration.py")
    assert '_add_column(connection, "pms_project", "product_category", "INT NULL")' in migration
    assert 'require_permission("project:list:edit")' in api
    assert 'scope_ctx["user_id"]' in api
    assert "scope_context=scope_ctx" in api


def test_project_update_can_save_stage_progress_fields() -> None:
    schema = read("app/schemas/project.py")
    model = read("app/models/project.py")
    service = read("app/services/project.py")
    init_db = read("app/models/init_db.py")

    for field in STAGE_PROGRESS_FIELDS:
        assert f"{field}: Mapped[int | None] = mapped_column(Integer" in model
        assert f"{field}: int | None = Field(default=None, ge=0, le=100)" in schema
        assert f"{field}=p.{field}" in service
        assert f"ALTER TABLE pms_project ADD {field} INT NULL" in init_db


if __name__ == "__main__":
    test_project_update_keeps_archive_product_category_read_only()
    test_project_update_can_save_stage_progress_fields()
    print("project update contract passed")
