"""Read the deployed build manifest, never infer a user version from schema/Git HEAD."""
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from functools import lru_cache
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.core.config import settings
from app.services.database_revision import CURRENT_DATABASE_REVISION

GUIDES = frozenset({'archive', 'archiveChanges', 'archiveDrafts', 'audit', 'feedback', 'inventory', 'purchase', 'stock', 'users', 'roles', 'enums', 'progress', 'tasks'})


class ReleaseChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['新增', '调整', '修复']
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=1000)
    guide: str

    @field_validator('guide')
    @classmethod
    def registered_guide(cls, value):
        if value not in GUIDES: raise ValueError('发布说明必须关联已登记页面')
        return value


class ReleaseManifest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: str = Field(pattern=r'^v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)$', max_length=32)
    title: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=500)
    build_id: str = Field(pattern=r'^[A-Za-z0-9_.-]{1,64}$')
    commit: str = Field(pattern=r'^[0-9a-f]{40}$')
    database_revision: str = Field(min_length=1, max_length=64)
    built_at: datetime
    changes: list[ReleaseChange] = Field(min_length=1, max_length=100)

    @field_validator('title')
    @classmethod
    def plain_subject(cls, value):
        if '\r' in value or '\n' in value or not value.strip(): raise ValueError('版本标题须为单行文字')
        return value


def validated_manifest(value):
    model = ReleaseManifest.model_validate(value)
    if model.built_at.tzinfo is None: raise ValueError('构建时间须包含时区')
    if model.database_revision != CURRENT_DATABASE_REVISION: raise ValueError('发布清单与程序数据库版本不匹配')
    return model.model_dump(mode='json')


def manifest_digest(value):
    # Canonicalize the raw manifest so JSON whitespace/key order cannot change identity.
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


@lru_cache(maxsize=4)
def _load_manifest(path_value, environment):
    path = Path(path_value)
    if not path.is_file():
        if environment == 'production': raise RuntimeError('正式部署缺少运行版本清单')
        return None
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
        validated_manifest(raw)
        return raw
    except (ValueError, OSError) as exc:
        raise RuntimeError('运行版本清单无效，请核对当前部署文件') from exc


def load_runtime_manifest():
    path = os.environ.get('PMS_RELEASE_MANIFEST') or settings.PMS_RELEASE_MANIFEST or str(Path(__file__).resolve().parents[3] / 'release.json')
    # Bind to the running process. Replacing a file cannot relabel already running code.
    value = _load_manifest(path, settings.PMS_ENV)
    return json.loads(json.dumps(value)) if value is not None else None


def runtime_info(context, manifest=None):
    manifest = manifest if manifest is not None else load_runtime_manifest()
    result = {'product': settings.APP_NAME, 'version': manifest['version'] if manifest else '开发中',
              'environment': '正式环境' if settings.PMS_ENV == 'production' else '开发环境'}
    if 'system:release:manage' in context.get('permissions', []):
        result['technical'] = {'commit': manifest.get('commit') if manifest else None,
            'build_id': manifest.get('build_id') if manifest else None, 'database_revision': CURRENT_DATABASE_REVISION}
    return result
