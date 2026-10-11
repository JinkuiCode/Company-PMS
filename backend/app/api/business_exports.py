"""Business-only download endpoints, separate from queued ERP report exports."""
from pathlib import Path
from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.authorization import require_permission
from app.services.business_export import create_business_export

router = APIRouter(prefix='/api/projects', tags=['业务单据导出'])


class BusinessExportRequest(BaseModel):
    model_config = {'extra': 'forbid'}
    parameters: dict = Field(default_factory=dict)
    filters: list[dict] = Field(default_factory=list, max_length=50)
    column_filters: list[dict] = Field(default_factory=list, max_length=50)
    sort: list[dict] = Field(default_factory=list, max_length=50)
    columns: list[str] = Field(min_length=1, max_length=200)


class BusinessExportFileResponse(FileResponse):
    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            Path(self.path).unlink(missing_ok=True)


def download(db, kind, data, context, request, project_id=None):
    path, filename = create_business_export(db, kind, data, context, request, project_id=project_id)
    return BusinessExportFileResponse(path, filename=filename, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@router.post('/export')
def export_projects(data: BusinessExportRequest, request: Request, db: Session = Depends(get_db),
                    context=Depends(require_permission('project:list:export'))):
    return download(db, 'project', data, context, request)


@router.post('/archives/export')
def export_archives(data: BusinessExportRequest, request: Request, db: Session = Depends(get_db),
                    context=Depends(require_permission('project:archive:export'))):
    return download(db, 'archive', data, context, request)


@router.post('/{project_id}/tasks/export')
def export_tasks(project_id: int, data: BusinessExportRequest, request: Request, db: Session = Depends(get_db),
                 context=Depends(require_permission('project:list:export'))):
    return download(db, 'task', data, context, request, project_id)
