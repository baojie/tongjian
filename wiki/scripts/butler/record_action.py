#!/usr/bin/env python3
"""
追加一条 action 记录到 wiki/logs/butler/actions.jsonl。

用法:
    python3 wiki/scripts/butler/record_action.py \
        --round 1 \
        --type create-page \
        --page 史湘云 \
        --result accept \
        --instance 补天石 \
        --desc "从语料第037回提取史湘云基本信息，创建人物页" \
        --reflect "诗词类段落较难定位，以后优先搜人名+诗"
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lock_manager import LockManager, LockError


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--round', type=int, required=True)
    ap.add_argument('--type', required=True, dest='action_type',
                    choices=[
                        'create-page', 'enrich-page', 'enrich-quality', 'stub',
                        'fix-links', 'add-quote', 'add-pn-citations', 'fix-alias',
                        'discover', 'publish', 'housekeeping', 'reflect-w5',
                        'add-poem', 'add-family-tree', 'wikify-chapters',
                    ])
    ap.add_argument('--page', default='')
    ap.add_argument('--result', required=True, choices=['accept', 'fail', 'skip'])
    ap.add_argument('--instance', default='', help='命名实例')
    ap.add_argument('--desc', default='')
    ap.add_argument('--reflect', default='', help='一句话观察，供 W5 扫描')
    ap.add_argument('--log', default='wiki/logs/butler/actions.jsonl')
    ap.add_argument('--skip-lock-check', action='store_true',
                    help='跳过锁检查（仅限 W5/publish 等周期任务轮）')
    args = ap.parse_args()

    if not args.skip_lock_check:
        try:
            LockManager().assert_owner(args.round)
        except LockError as e:
            print(f"[record_action] 锁检查失败，拒绝写入：{e}", file=sys.stderr)
            sys.exit(1)

    record = {
        'round':  args.round,
        'type':   args.action_type,
        'page':   args.page,
        'result': args.result,
        'desc':   args.desc,
        'ts':     datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }
    if args.instance:
        record['instance'] = args.instance
    if args.reflect:
        record['reflect'] = args.reflect

    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')

    inst_tag = f" [{args.instance}]" if args.instance else ""
    print(f"[logged] R{args.round}{inst_tag} {args.action_type} | {args.page} | {args.result}")


if __name__ == '__main__':
    main()
