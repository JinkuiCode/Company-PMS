#!/usr/bin/env python3
"""Validate the active task ledger before ending an implementation turn.

This is a local workflow check, not a platform hook or runtime permission grant.
The ledger is deliberately excluded from Git and contains no credentials.
"""
import argparse
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path


def check_exit(tasks):
    reasons = []
    seen = set()
    if not isinstance(tasks, list) or not tasks:
        return False, ['任务台账为空或格式错误，无法判断总任务是否完成']
    for task in tasks:
        if not isinstance(task, dict):
            reasons.append('任务条目格式错误')
            continue
        key = task.get('id', '')
        if not key or key in seen:
            reasons.append('任务编号缺失或重复')
        seen.add(key)
        state = task.get('status')
        if state in ('ready', 'in_progress'):
            reasons.append(f'{key}：仍有可执行工作，不应结束')
        elif state == 'done':
            if not task.get('evidence'):
                reasons.append(f'{key}：完成状态缺少证据')
        elif state in ('blocked_approval', 'blocked_input'):
            if not task.get('blocker') or task.get('request_state') not in ('pending', 'already_requested', 'deferred_by_user'):
                reasons.append(f'{key}：阻塞缺少具体原因或请求状态')
            requested = task.get('question') or task.get('required_input')
            if not isinstance(requested, str) or len(requested.strip()) < 10 or not task.get('request_reference'):
                reasons.append(f'{key}：所有阻塞必须有具体问题/所需输入及请求引用，不能只等“继续”')
            if task.get('blocker', '').strip() in ('待批准', '待确认', '等待继续', '等回复', '继续'):
                reasons.append(f'{key}：空泛等待不构成真实阻塞')
            if task.get('request_state') == 'deferred_by_user' and not task.get('user_instruction_reference'):
                reasons.append(f'{key}：用户延期缺少其明确指示引用')
        else:
            reasons.append(f'{key}：未知状态，不能将未完成项静默推迟')
    return not reasons, reasons


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledger', type=Path, default=Path('.runtime/execution-continuity-audit/active-tasks.json'))
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    try:
        value = json.loads(args.ledger.read_text(encoding='utf-8'))
        allowed, reasons = check_exit(value['tasks'])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        allowed, reasons = False, [f'无法验证台账：{type(exc).__name__}']
    result = {'may_end': allowed, 'reasons': reasons, 'meaning': '只检查工作连续性，不授予正式操作权限，也不保证平台不会中断'}
    # Keep a minimal, local audit of each attempted end, including rejected ones.
    record = {'checked_at': datetime.now(timezone.utc).isoformat(), 'may_end': allowed,
              'reasons': reasons, 'active_ids': [], 'ledger_sha256': None}
    if args.ledger.is_file():
        record['ledger_sha256'] = hashlib.sha256(args.ledger.read_bytes()).hexdigest()
    if isinstance(locals().get('value'), dict) and isinstance(value.get('tasks'), list):
        record['active_ids'] = [t.get('id') for t in value['tasks'] if isinstance(t, dict) and t.get('status') != 'done']
    if args.ledger.parent.is_dir():
        try:
            with (args.ledger.parent/'exit-checks.jsonl').open('a', encoding='utf-8') as file:
                file.write(json.dumps(record, ensure_ascii=False)+'\n')
        except OSError:
            result['may_end'] = False
            result['reasons'].append('结束检查记录无法保存')
            allowed = False
    if args.report:
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if allowed else 2


if __name__ == '__main__':
    raise SystemExit(main())
