#!/usr/bin/env python3
"""Default: read-only Chinese inspection. --apply requires an approved exact plan."""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))


def markdown_report(state):
    def cell(value):
        return str(value if value is not None else '未设置').replace('|', '\\|').replace('\n', ' ')
    output = ['# 产品线组织归属检查清单', '',
        '本文件仅为只读检查结果，未写入归属或角色授权。旧枚举编号不代表新产品线编号。', '',
        f"数据库版本：{state['source_revision']}", f"快照指纹：{state['source_fingerprint']}", '']
    columns = {
        '未归属档案': [('id', '档案编号'), ('project_code', '项目编码'), ('project_name', '项目名称'),
                      ('legacy_product_line_id', '历史产品线枚举值')],
        '项目编码冲突': [('id', '档案编号'), ('project_code', '项目编码'), ('project_name', '项目名称')],
        '进度缺少有效档案引用': [('id', '进度编号'), ('project_code', '项目编码'), ('archive_id', '引用档案编号')],
        '角色需明确产品线授权': [('id', '角色编号'), ('role_name', '角色名称'),
            ('product_category_ids', '旧产品类别范围（仅供核对，不自动转换）'), ('status', '启用状态（1启用/0禁用）')],
    }
    for group, rows in state['issues'].items():
        fields = columns[group]
        output += [f'## {group}（{len(rows)} 条）', '',
            '| ' + ' | '.join(label for _, label in fields) + ' |',
            '| ' + ' | '.join('---' for _ in fields) + ' |']
        output += ['| ' + ' | '.join(cell(row.get(key)) for key, _ in fields) + ' |' for row in rows]
        output.append('')
    output += ['## 需人工确认', '',
        '- 将哪些金蝶组织纳入产品线、各自使用什么显示名称。',
        '- 每个未归属档案属于哪一个已确认组织。',
        '- 每个角色明确授权哪些产品线；空列表表示无权。',
        '- 本工具不根据采购活动推断归属；单一候选或多组织冲突须另附业务核对证据。', '']
    return '\n'.join(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--plan', type=Path)
    mode.add_argument('--prepare-mapping', type=Path, help='只读：按已确认旧枚举编号与组织内码生成档案清单，不分配角色')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--operator-id', type=int)
    args = parser.parse_args()
    if args.apply and (not args.plan or not args.operator_id):
        parser.error('--apply requires --plan and --operator-id')
    from app.core.database import SessionLocal
    import app.models.init_db  # Register models only; do not call initialization.
    from app.services.product_line_assignments import snapshot, inspect_plan, apply_plan, prepare_archive_plan
    output = ROOT / '.runtime' / 'product-line-migration'
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    try:
        with SessionLocal() as db:
            if args.prepare_mapping:
                mappings = json.loads(args.prepare_mapping.read_text(encoding='utf-8'))
                result = prepare_archive_plan(db, mappings)
            elif args.plan:
                plan = json.loads(args.plan.read_text(encoding='utf-8'))
                result = apply_plan(db, plan, operator_id=args.operator_id) if args.apply else inspect_plan(db, plan)
            else:
                result = snapshot(db)
            files = [('.json', json.dumps(result, ensure_ascii=False, indent=2, default=str))]
            if args.prepare_mapping:
                if result['ready']:
                    files.append(('.plan.json', json.dumps(result['plan'], ensure_ascii=False, indent=2)))
                print(f"匹配档案：{result['archive_count']}；未匹配：{len(result['unmatched_archives'])}；角色授权不变。")
            elif not args.plan:
                files.append(('.md', markdown_report(result)))
            for suffix, content in files:
                path = output / (stamp + suffix)
                with path.open('x', encoding='utf-8') as handle:
                    path.chmod(0o600)
                    handle.write(content)
                print(f'结果文件：{path}')
            if not args.apply:
                print('只读检查完成，未修改数据库。')
            else:
                print('清单已应用。' if result['status'] == 'applied' else '该批次已经执行，未重复写入。')
            return 1 if result.get('ready') is False else 0
    except Exception as error:
        print(f'检查、应用或结果输出失败（{type(error).__name__}）。请核对配置、版本及清单；应用是否已提交以批次审计为准。', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
