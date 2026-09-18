from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.authorization import require_permission
from app.services.parameter import list_parameters, update_parameter

router = APIRouter(prefix="/api/parameters", tags=["参数设置"])


class ParameterUpdate(BaseModel):
    model_config = {"extra": "forbid"}
    value: str = Field(max_length=16384)
    version: int = Field(ge=0, strict=True)


@router.get("")
def get_parameters(db: Session = Depends(get_db), context=Depends(require_permission("system:parameter:view"))):
    return list_parameters(db)


@router.put("/{code}")
def put_parameter(code: str, data: ParameterUpdate, request: Request, db: Session = Depends(get_db),
                  context=Depends(require_permission("system:parameter:edit"))):
    return update_parameter(db, code, data.value, data.version, context["user_id"], request)
