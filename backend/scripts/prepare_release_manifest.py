#!/usr/bin/env python3
"""Prepare immutable user release metadata; this command never publishes or sends."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.runtime_release import validated_manifest
from app.services.database_revision import CURRENT_DATABASE_REVISION


def prepare(notes, commit, build_id):
    if set(notes) != {'version', 'title', 'summary', 'changes'}: raise ValueError('升级清单仅可包含版本、标题、摘要和变更项')
    raw = dict(notes, commit=commit, build_id=build_id, database_revision=CURRENT_DATABASE_REVISION,
        built_at=datetime.now(timezone.utc).isoformat())
    validated_manifest(raw)
    return raw


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--notes', required=True, type=Path)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--build-id', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    value = prepare(json.loads(args.notes.read_text(encoding='utf-8')), args.commit, args.build_id)
    args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('运行版本清单已生成；尚未发布通知')
