#!/usr/bin/env python3
"""Prepare SQLite upgrade/recovery evidence; never modifies the source database."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.form_draft_rehearsal import rehearse

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    result=rehearse(args.source,args.output)
    print('隔离副本升级及恢复核验通过；源库未修改。目标版本：' + result['revision'])
