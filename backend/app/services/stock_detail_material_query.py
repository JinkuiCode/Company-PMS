"""The same single material field bounds movements and opening snapshots."""
from sqlalchemy import literal_column
from app.services.query_conditions import build_query_clause
from app.services.report_filters import compile_predicate


def material_predicate(query):
    field = query.material_field
    columns = {'material_code': 'M.FNUMBER',
        'material_name': '(SELECT MAX(ML.FNAME) FROM dbo.T_BD_MATERIAL_L ML WHERE ML.FMATERIALID=M.FMATERIALID AND ML.FLOCALEID=2052)',
        'specification': '(SELECT MAX(ML.FSPECIFICATION) FROM dbo.T_BD_MATERIAL_L ML WHERE ML.FMATERIALID=M.FMATERIALID AND ML.FLOCALEID=2052)'}
    if field not in columns:
        raise ValueError('物料查询字段无效')
    return compile_predicate(build_query_clause(literal_column(columns[field]), 'text',
        dict(schemaVersion=2, operator=query.material_operator, value=query.material)))
