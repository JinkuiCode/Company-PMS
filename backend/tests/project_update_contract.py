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


def test_project_update_can_save_archive_product_line() -> None:
    schema = read("app/schemas/project.py")
    model = read("app/models/project.py")
    service = read("app/services/project.py")
    api = read("app/api/projects.py")
    init_db = read("app/models/init_db.py")

    assert "product_line: str | None = None" in schema
    assert 'product_line: Mapped[str | None] = mapped_column(NVARCHAR(32)' in model
    assert "product_line: str | None = Field(None, max_length=32)" in schema
    assert "proj.product_line = product_line_value" in service
    assert "PmsProjectArchive" in service
    assert "updated_by" in service
    assert "archive.product_line if archive and archive.product_line else p.product_line" in service
    assert "项目未关联档案，无法更新产品类" not in service
    assert "ALTER TABLE pms_project ADD product_line NVARCHAR(32) NULL" in init_db
    assert "user_id: int = Depends(get_current_user_id)" in api
    assert "project_service.update_project(db, project_id, data, user_id, request=request)" in api


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
    test_project_update_can_save_archive_product_line()
    test_project_update_can_save_stage_progress_fields()
    print("project update contract passed")
