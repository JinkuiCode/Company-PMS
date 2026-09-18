"""Fixed read-only cross-database query; no OA write or configurable SQL."""
from fastapi import HTTPException
from sqlalchemy import text


OA_EMPLOYEES = """
WITH candidates AS (
  SELECT LTRIM(RTRIM([工号])) AS username, MIN([中文名]) AS real_name
  FROM ecology.dbo.Jinky_Employee
  WHERE [一级部门] = :department AND [工号] IS NOT NULL
    AND LTRIM(RTRIM([工号])) <> '' AND [中文名] IS NOT NULL
    AND (:keyword = '' OR [工号] LIKE :pattern ESCAPE '~' OR [中文名] LIKE :pattern ESCAPE '~')
    AND NOT EXISTS (SELECT 1 FROM sys_user u WHERE u.username COLLATE DATABASE_DEFAULT = LTRIM(RTRIM([工号])) COLLATE DATABASE_DEFAULT)
  GROUP BY LTRIM(RTRIM([工号]))
)
"""


def get_oa_options(db, keyword, page, page_size):
    if db.get_bind().dialect.name != "mssql":
        raise HTTPException(503, "OA 人员查询仅支持已连接 OA 数据库的 SQL Server 环境")
    escaped = keyword.replace("~", "~~").replace("%", "~%").replace("_", "~_").replace("[", "~[")
    params = {"department": "总经理", "keyword": keyword, "pattern": f"%{escaped}%",
              "offset": (page - 1) * page_size, "limit": page_size}
    try:
        total = db.execute(text(OA_EMPLOYEES + "SELECT COUNT(*) FROM candidates"), params).scalar_one()
        rows = db.execute(text(OA_EMPLOYEES + "SELECT username, real_name FROM candidates ORDER BY username OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY"), params).mappings().all()
    except Exception as exc:
        raise HTTPException(503, "OA 人员查询不可用，请检查只读查询权限和数据库连接") from exc
    return {"items": [dict(row) for row in rows], "total": total}
